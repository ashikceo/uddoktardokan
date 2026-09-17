"""User Profile & Account Center views (one view + URL per tab)."""
import base64
import hashlib
import io
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db.models import Sum
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

import pyotp
import qrcode

from .models import (
    AccountActivityLog,
    Address,
    Notification,
    Order,
    Partner,
    PartnerWallet,
    TwoFactorBackup,
    TwoFactorRecoveryCode,
    UserNotificationPreference,
    UserProfile,
    WalletTransaction,
    Wishlist,
)
from .sms_provider import send_otp_sms
from .views import BACKEND, MAX_UPLOAD_SIZE, validate_upload

OTP_TTL_MINUTES = 10
OTP_RESEND_COOLDOWN = 60
OTP_MAX_ATTEMPTS = 5
TWO_FACTOR_SECRET_BYTES = 20
RECOVERY_CODE_COUNT = 10


# ─── helpers ────────────────────────────────────────────────────────────────

def _profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def _prefs(user):
    prefs, _ = UserNotificationPreference.objects.get_or_create(user=user)
    return prefs


def _client_ip(request):
    fwd = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if fwd:
        return fwd.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def _ua(request):
    return request.META.get('HTTP_USER_AGENT', '')[:380]


def _log(user, action, detail='', request=None):
    AccountActivityLog.objects.create(
        user=user,
        action=action,
        detail=detail or '',
        ip=_client_ip(request) if request else None,
        user_agent=_ua(request) if request else '',
    )


def _hash_code(value):
    import hashlib as _hl
    salt = settings.SECRET_KEY
    return _hl.sha256(f'{salt}:{value}'.encode('utf-8')).hexdigest()


def _generate_otp():
    return f'{secrets.randbelow(10 ** 6):06d}'


def _send_email(subject, body, to_email):
    try:
        send_mail(
            subject,
            body,
            getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@uddoktardokan.com'),
            [to_email],
            fail_silently=False,
        )
        return True
    except Exception:  # noqa: BLE001
        return False


def _user_sessions(user):
    rows = []
    for s in Session.objects.all():
        try:
            data = s.get_decoded()
        except Exception:  # noqa: BLE001
            continue
        if str(data.get('_auth_user_id')) == str(user.pk):
            rows.append({'session': s, 'data': data})
    return rows


def _totp(user):
    backup = TwoFactorBackup.objects.filter(user=user).first()
    return backup.secret if backup else ''


def _totp_verify(secret, code):
    try:
        return pyotp.TOTP(secret).verify(code, valid_window=1)
    except Exception:  # noqa: BLE001
        return False


def _totp_provisioning_uri(user):
    secret = _totp(user) if TwoFactorBackup.objects.filter(user=user).exists() else ''
    issuer = 'Uddokta Dokan'
    return pyotp.TOTP(secret).provisioning_uri(name=user.email or user.username, issuer_name=issuer) if secret else ''


def _qr_data_uri(uri):
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    b64 = base64.b64encode(buf.getvalue()).decode('ascii')
    return f'data:image/png;base64,{b64}'


def _recovery_codes_hashed(codes):
    from django.contrib.auth.hashers import make_password
    return [make_password(c) for c in codes]


def _check_recovery_code(user, code):
    from django.contrib.auth.hashers import check_password
    candidate = code.strip().upper()
    matches = TwoFactorRecoveryCode.objects.filter(user=user, used=False)
    for row in matches:
        if check_password(candidate, row.code_hash):
            row.used = True
            row.save(update_fields=['used'])
            return True
    return False


def _address_book_data(user):
    return user.addresses.all()


def _orders_data(user, limit=20):
    return Order.objects.filter(user=user).prefetch_related('items__product').order_by('-created')[:limit]


def _wishlist_data(user):
    wl = Wishlist.objects.filter(user=user).select_related('user').first()
    if not wl:
        return [], None
    return wl.items.select_related('product'), wl


def _partner_for(user):
    try:
        return user.partner
    except Partner.DoesNotExist:
        return None


def _account_context(request):
    return {'profile': _profile(request.user), 'prefs': _prefs(request.user), 'partner': _partner_for(request.user)}


# ─── overview ───────────────────────────────────────────────────────────────

@login_required
def account_overview(request):
    user = request.user
    profile = _profile(user)
    all_orders = Order.objects.filter(user=user)
    orders = all_orders.prefetch_related('items__product').order_by('-created')[:20]
    wish_items, _wl = _wishlist_data(user)
    partner = _partner_for(user)
    wallet = PartnerWallet.objects.filter(partner=partner).first() if partner else None
    unread = Notification.objects.filter(user=user, is_read=False).count()
    recent_logs = user.activity_logs.all()[:8]
    address_count = user.addresses.count()
    has_default = user.addresses.filter(is_default=True).exists()
    return render(request, 'store/account/account_overview.html', {
        'account_page': 'account_overview',
        'profile': profile,
        'partner': partner,
        'wallet': wallet,
        'orders_count': all_orders.count(),
        'wishlist_count': len(wish_items),
        'address_count': address_count,
        'has_default_address': has_default,
        'total_order_value': all_orders.aggregate(t=Sum('total'))['t'] or 0,
        'unread_notifications': unread,
        'recent_logs': recent_logs,
        'completion': profile.completion_percentage(),
    })


# ─── personal info / avatar / verification ──────────────────────────────────

@login_required
def account_info(request):
    user = request.user
    profile = _profile(user)
    if request.method == 'POST':
        action = request.POST.get('action', 'update_info')
        if action == 'update_info':
            user.first_name = request.POST.get('first_name', '').strip()[:150]
            user.last_name = request.POST.get('last_name', '').strip()[:150]
            profile.bio = request.POST.get('bio', '').strip()
            gender = request.POST.get('gender', '')
            profile.gender = gender if gender in ('male', 'female', 'other') else ''
            dob = request.POST.get('date_of_birth', '').strip()
            profile.date_of_birth = dob if dob else None
            new_phone = request.POST.get('phone', '').strip()[:20]
            if new_phone != profile.phone:
                profile.phone = new_phone
                profile.phone_verified = False
            user.save(update_fields=['first_name', 'last_name'])
            profile.save()
            _log(user, 'profile_updated', 'Personal information updated', request)
            messages.success(request, 'Profile updated successfully.')
            return redirect('account_info')
        if action == 'upload_avatar':
            avatar = request.FILES.get('avatar')
            if avatar:
                try:
                    validate_upload(avatar)
                    from PIL import Image as PILImage
                    PILImage.open(avatar).verify()
                    profile.avatar = avatar
                    profile.save()
                    _log(user, 'avatar_updated', 'Avatar uploaded', request)
                    messages.success(request, 'Profile picture updated.')
                except (ValueError, Exception) as exc:  # noqa: BLE001
                    messages.error(request, str(exc) if isinstance(exc, ValueError) else 'Invalid image file.')
            return redirect('account_info')
        if action == 'delete_avatar':
            if profile.avatar:
                profile.avatar.delete(save=False)
                profile.avatar = None
                profile.save()
                _log(user, 'avatar_updated', 'Avatar removed', request)
                messages.success(request, 'Profile picture removed.')
            return redirect('account_info')
        _send_generic_post(request)
    return render(request, 'store/account/account_info.html', {
        'account_page': 'account_info',
        'profile': profile,
        'user': user,
        'otp_pending': _pending_otp(user),
    })


def _pending_otp(user):
    now = timezone.now()
    return list(user.otp_codes.filter(used=False, expires_at__gt=now)[:3])


def _send_generic_post(request):
    messages.error(request, 'Invalid action.')
    return redirect('account_info')


# ─── OTP request / verify ───────────────────────────────────────────────────

@login_required
@ratelimit(key='ip', rate='10/30m', method='POST')
def account_otp_request(request):
    user = request.user
    profile = _profile(user)
    if request.method != 'POST':
        return redirect('account_info')
    purpose = request.POST.get('purpose', '')
    if purpose not in ('email_verify', 'phone_verify', 'email_change'):
        messages.error(request, 'Invalid verification type.')
        return redirect('account_info')
    now = timezone.now()
    recent = user.otp_codes.filter(purpose=purpose, used=False).order_by('-created').first()
    if recent and (now - recent.created).total_seconds() < OTP_RESEND_COOLDOWN:
        wait = OTP_RESEND_COOLDOWN - int((now - recent.created).total_seconds())
        messages.error(request, f'Please wait {wait} seconds before requesting a new code.')
        return redirect('account_info')

    target = profile.phone if purpose == 'phone_verify' else user.email
    if purpose == 'email_change':
        new_email = request.POST.get('new_email', '').strip()
        try:
            validate_email(new_email)
        except Exception:  # noqa: BLE001
            messages.error(request, 'Please enter a valid email address.')
            return redirect('account_info')
        if User.objects.filter(email__iexact=new_email).exclude(pk=user.pk).exists():
            messages.error(request, 'That email address is already in use by another account.')
            return redirect('account_info')
        target = new_email
    if not target:
        messages.error(request, 'No contact method to send the code to.')
        return redirect('account_info')

    code = _generate_otp()
    user.otp_codes.filter(purpose=purpose, used=False).delete()
    user.otp_codes.create(
        purpose=purpose,
        code_hash=_hash_code(code),
        expires_at=now + timedelta(minutes=OTP_TTL_MINUTES),
        new_email=target if purpose == 'email_change' else '',
    )
    if purpose == 'email_change':
        _send_email(
            'Your Uddokta Dokan email verification code',
            f'Use {code} to confirm your new email address. It expires in 10 minutes.\nIf you did not request this, ignore this email.',
            target,
        )
    if purpose == 'phone_verify':
        delivered = send_otp_sms(target, code)
        if not delivered:
            messages.warning(request, 'No SMS gateway is configured yet — the code was logged to the server console.')
    else:
        _send_email('Your Uddokta Dokan verification code', f'Your verification code is {code}. It expires in 10 minutes.', target)
    messages.success(request, f'Verification code sent to {target}.')
    return redirect('account_info')


@login_required
@ratelimit(key='ip', rate='20/30m', method='POST')
def account_otp_verify(request):
    user = request.user
    profile = _profile(user)
    if request.method != 'POST':
        return redirect('account_info')
    purpose = request.POST.get('purpose', '')
    code = request.POST.get('code', '').strip()
    if purpose not in ('email_verify', 'phone_verify', 'email_change'):
        messages.error(request, 'Invalid verification type.')
        return redirect('account_info')
    otp = user.otp_codes.filter(purpose=purpose, used=False).order_by('-created').first()
    if not otp or otp.expires_at < timezone.now():
        messages.error(request, 'This code has expired. Request a new one.')
        return redirect('account_info')
    if otp.attempts >= OTP_MAX_ATTEMPTS:
        otp.used = True
        otp.save(update_fields=['used'])
        messages.error(request, 'Too many incorrect attempts. Request a new code.')
        return redirect('account_info')
    otp.attempts += 1
    otp.save(update_fields=['attempts'])
    if _hash_code(code) != otp.code_hash:
        messages.error(request, 'Incorrect code. Please try again.')
        return redirect('account_info')

    otp.used = True
    otp.save(update_fields=['used'])
    if purpose == 'email_verify':
        profile.email_verified = True
        profile.save(update_fields=['email_verified'])
        _log(user, 'email_verified', user.email or '', request)
    elif purpose == 'phone_verify':
        profile.phone_verified = True
        profile.save(update_fields=['phone_verified'])
        _log(user, 'phone_verified', profile.phone or '', request)
    elif purpose == 'email_change':
        user.email = otp.new_email
        user.save(update_fields=['email'])
        profile.email_verified = True
        profile.save(update_fields=['email_verified'])
        _log(user, 'email_changed', otp.new_email, request)
    messages.success(request, 'Verified successfully.')
    return redirect('account_info')


# ─── security (password / 2FA / sessions / activity) ────────────────────────

@login_required
def account_security(request):
    user = request.user
    two_factor = TwoFactorBackup.objects.filter(user=user).first()
    pending_secret = request.session.get('pending_2fa_secret', '')
    fresh_codes = request.session.pop('fresh_recovery_codes', None)
    sessions = _user_sessions(user)
    return render(request, 'store/account/account_security.html', {
        'account_page': 'account_security',
        'profile': _profile(user),
        'two_factor': two_factor,
        'pending_2fa_secret': pending_secret,
        'pending_2fa_uri': pyotp.TOTP(pending_secret).provisioning_uri(name=user.email or user.username, issuer_name='Uddokta Dokan') if pending_secret else '',
        'pending_2fa_qr': _qr_data_uri(pyotp.TOTP(pending_secret).provisioning_uri(name=user.email or user.username, issuer_name='Uddokta Dokan')) if pending_secret else '',
        'fresh_recovery_codes': fresh_codes,
        'sessions': sessions,
        'current_session_key': request.session.session_key,
        'activity_logs': user.activity_logs.all()[:20],
        'recovery_codes_configured': TwoFactorRecoveryCode.objects.filter(user=user).exists(),
    })


@login_required
@require_POST
@ratelimit(key='ip', rate='10/10m', method='POST')
def account_password_change(request):
    user = request.user
    form = PasswordChangeForm(user, request.POST)
    if form.is_valid():
        form.save()
        update_session_auth_hash(request, user)
        _log(user, 'password_change', '', request)
        messages.success(request, 'Your password was changed successfully.')
    else:
        for field, errors in form.errors.items():
            for err in errors:
                messages.error(request, err)
    return redirect('account_security')


@login_required
@require_POST
@ratelimit(key='ip', rate='6/10m', method='POST')
def account_2fa_setup_start(request):
    user = request.user
    password = request.POST.get('password', '')
    if not user.check_password(password):
        _log(user, 'security_failed', '2FA setup: wrong password', request)
        messages.error(request, 'Your password is required to enable two-factor authentication.')
        return redirect('account_security')
    if TwoFactorBackup.objects.filter(user=user).exists():
        messages.info(request, 'Two-factor authentication is already enabled.')
        return redirect('account_security')
    secret = pyotp.random_base32()
    request.session['pending_2fa_secret'] = secret
    messages.info(request, 'Scan the QR code with your authenticator app, then confirm with a code.')
    return redirect('account_security')


@login_required
@require_POST
@ratelimit(key='ip', rate='6/10m', method='POST')
def account_2fa_setup_verify(request):
    user = request.user
    secret = request.session.get('pending_2fa_secret', '')
    code = request.POST.get('code', '').strip()
    if not secret:
        messages.error(request, 'Start 2FA setup first.')
        return redirect('account_security')
    if not _totp_verify(secret, code):
        messages.error(request, 'Incorrect code. Please try again.')
        return redirect('account_security')
    TwoFactorBackup.objects.filter(user=user).delete()
    TwoFactorBackup.objects.create(user=user, secret=secret)
    TwoFactorRecoveryCode.objects.filter(user=user).delete()
    codes = [f'{secrets.token_hex(5).upper()[:5]}-{secrets.token_hex(5).upper()[:5]}-{secrets.token_hex(5).upper()[:5]}' for _ in range(RECOVERY_CODE_COUNT)]
    for hashed in _recovery_codes_hashed(codes):
        TwoFactorRecoveryCode.objects.create(user=user, code_hash=hashed)
    request.session.pop('pending_2fa_secret', None)
    request.session['fresh_recovery_codes'] = codes
    _log(user, '2fa_enabled', 'Two-factor authentication enabled', request)
    messages.success(request, 'Two-factor authentication is now enabled. Save your recovery codes!')
    return redirect('account_security')


@login_required
@require_POST
@ratelimit(key='ip', rate='6/10m', method='POST')
def account_2fa_disable(request):
    user = request.user
    password = request.POST.get('password', '')
    otp_code = request.POST.get('code', '').strip()
    backup = TwoFactorBackup.objects.filter(user=user).first()
    if not backup:
        messages.info(request, 'Two-factor authentication is not enabled.')
        return redirect('account_security')
    ok = user.check_password(password) or _totp_verify(backup.secret, otp_code)
    if not ok:
        _log(user, 'security_failed', '2FA disable: wrong password/code', request)
        messages.error(request, 'Your password or a valid authenticator code is required to disable 2FA.')
        return redirect('account_security')
    backup.delete()
    TwoFactorRecoveryCode.objects.filter(user=user).delete()
    _log(user, '2fa_disabled', 'Two-factor authentication disabled', request)
    messages.success(request, 'Two-factor authentication has been disabled.')
    return redirect('account_security')


@login_required
@require_POST
def account_sessions_revoke(request):
    user = request.user
    current = request.session.session_key
    revoked = 0
    for row in _user_sessions(user):
        if row['session'].session_key != current:
            row['session'].delete()
            revoked += 1
    if revoked > 0:
        _log(user, 'sessions_revoked', f'{revoked} session(s) signed out', request)
        messages.success(request, f'Successfully signed out {revoked} other device(s). Your current session stays active.')
    else:
        messages.info(request, 'No other active sessions were found.')
    return redirect('account_security')


# ─── addresses ──────────────────────────────────────────────────────────────

@login_required
def account_addresses(request):
    return render(request, 'store/account/account_addresses.html', {
        'account_page': 'account_addresses',
        'profile': _profile(request.user),
        'addresses': _address_book_data(request.user),
    })


# ─── notifications ──────────────────────────────────────────────────────────

@login_required
def account_notifications(request):
    prefs = _prefs(request.user)
    if request.method == 'POST':
        prefs.order_updates = request.POST.get('order_updates') == 'on'
        prefs.review_replies = request.POST.get('review_replies') == 'on'
        prefs.promotions = request.POST.get('promotions') == 'on'
        prefs.security_alerts = request.POST.get('security_alerts') == 'on'
        prefs.save()
        _log(request.user, 'preferences_updated', 'Notification preferences updated', request)
        messages.success(request, 'Notification preferences saved.')
        return redirect('account_notifications')
    return render(request, 'store/account/account_notifications.html', {
        'account_page': 'account_notifications',
        'profile': _profile(request.user),
        'prefs': prefs,
    })


# ─── wallet / payments ──────────────────────────────────────────────────────

@login_required
def account_wallet(request):
    user = request.user
    partner = _partner_for(user)
    wallet = PartnerWallet.objects.filter(partner=partner).first() if partner else None
    transactions = wallet.transactions.all().select_related('wallet')[:20] if wallet else []
    return render(request, 'store/account/account_wallet.html', {
        'account_page': 'account_wallet',
        'profile': _profile(user),
        'partner': partner,
        'wallet': wallet,
        'transactions': transactions,
    })


# ─── orders ─────────────────────────────────────────────────────────────────

@login_required
def account_orders(request):
    return render(request, 'store/account/account_orders.html', {
        'account_page': 'account_orders',
        'profile': _profile(request.user),
        'orders': _orders_data(request.user),
    })


# ─── wishlist ───────────────────────────────────────────────────────────────

@login_required
def account_wishlist(request):
    items, wl = _wishlist_data(request.user)
    return render(request, 'store/account/account_wishlist.html', {
        'account_page': 'account_wishlist',
        'profile': _profile(request.user),
        'items': items,
        'wishlist': wl,
    })


# ─── settings (preferences + deactivate) ────────────────────────────────────

@login_required
def account_settings(request):
    prefs = _prefs(request.user)
    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'save_prefs':
            prefs.order_updates = request.POST.get('order_updates') == 'on'
            prefs.review_replies = request.POST.get('review_replies') == 'on'
            prefs.promotions = request.POST.get('promotions') == 'on'
            prefs.security_alerts = request.POST.get('security_alerts') == 'on'
            prefs.save()
            _log(request.user, 'preferences_updated', 'Notification preferences updated', request)
            messages.success(request, 'Notification preferences saved.')
            return redirect('account_settings')
        if action == 'deactivate':
            password = request.POST.get('password', '')
            if not request.user.check_password(password):
                messages.error(request, 'Your password is required to deactivate the account.')
                return redirect('account_settings')
            _log(request.user, 'account_deactivated', '', request)
            user = request.user
            user.is_active = False
            user.save(update_fields=['is_active'])
            logout(request)
            return HttpResponseRedirect(reverse('home'))
    return render(request, 'store/account/account_settings.html', {
        'account_page': 'account_settings',
        'profile': _profile(request.user),
        'prefs': prefs,
        'address_count': request.user.addresses.count(),
    })


# ─── 2FA login challenge ────────────────────────────────────────────────────

@ratelimit(key='ip', rate='8/10m', method='POST', block=True)
def login_2fa(request):
    pending = request.session.get('pending_2fa_user')
    if not pending:
        return redirect('login')
    user = None
    try:
        user = User.objects.get(pk=pending)
    except User.DoesNotExist:
        request.session.pop('pending_2fa_user', None)
        return redirect('login')
    two_factor = TwoFactorBackup.objects.filter(user=user).first()
    if not two_factor:
        request.session.pop('pending_2fa_user', None)
        return redirect('login')
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        recovery = request.POST.get('recovery_code', '').strip()
        ok = bool(code and _totp_verify(two_factor.secret, code))
        if not ok and recovery:
            ok = _check_recovery_code(user, recovery)
        if ok:
            login(request, user, backend=BACKEND)
            request.session.pop('pending_2fa_user', None)
            _log(user, 'login_2fa', 'Signed in with two-factor', request)
            nxt = request.session.pop('next_after_2fa', '')
            if nxt and nxt.startswith('/') and not nxt.startswith('//'):
                return redirect(nxt)
            return redirect('account_overview')
        messages.error(request, 'That code was incorrect. Please try again.')
    return render(request, 'store/login_2fa.html', {
        'user': user,
        'next': request.GET.get('next', ''),
    })