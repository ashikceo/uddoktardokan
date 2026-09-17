"""SMS delivery abstraction for phone verification.

Only a gateway that is explicitly configured via environment variables will be
used. When no provider is configured the code is logged to the console/server
log so development flows keep working without faking delivery. A provider can
be added simply by implementing ``send_otp_sms`` below.
"""
import logging
import os

logger = logging.getLogger(__name__)


def send_otp_sms(phone, code):
    """Send a verification code via the configured provider.

    Returns True when a real gateway accepted the delivery, otherwise logs the
    code and returns False (no provider configured).
    """
    provider = os.getenv('SMS_PROVIDER', '').strip().lower()

    if provider == 'twilio':
        return _send_twilio(phone, code)
    if provider in ('msg91', 'nexmo', 'meta', 'somos'):
        return _send_generic(provider, phone, code)

    logger.info('[SMS] Verification code for %s: %s (no SMS_PROVIDER configured — set SMS_PROVIDER/SMS_* env vars)', phone, code)
    return False


def _send_twilio(phone, code):
    account_sid = os.getenv('SMS_TWILIO_SID', '')
    auth_token = os.getenv('SMS_TWILIO_TOKEN', '')
    from_number = os.getenv('SMS_TWILIO_FROM', '')
    if not (account_sid and auth_token and from_number):
        logger.warning('[SMS] Twilio selected but SMS_TWILIO_SID/SMS_TWILIO_TOKEN/SMS_TWILIO_FROM missing')
        return False
    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        client.messages.create(
            to=phone,
            from_=from_number,
            body=f'Your Uddokta Dokan verification code is {code}',
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.exception('Twilio SMS send failed: %s', exc)
        return False


def _send_generic(provider, phone, code):
    """Placeholder for other gateways. Implement per provider contract."""
    logger.warning('[SMS] Provider %r selected but not implemented — add a consumer in store/sms_provider.py', provider)
    return False