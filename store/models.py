import json
import re
from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.text import slugify

from .domain_utils import host_key


def _unique_slug(klass, slug_field, slug):
    suffix = 1
    base_slug = slug[:50]
    while klass.objects.filter(**{slug_field: slug}).exists():
        suffix_str = f'-{suffix}'
        slug = f'{base_slug[:50-len(suffix_str)]}{suffix_str}'
        suffix += 1
    return slug


def generate_partner_slug(text):
    """Generate partner slug: take text before 'Upazila', lowercase, remove hyphens, append 'uddoktardokan'."""
    import re
    text = text.strip()
    match = re.split(r'-?[Uu]pazila', text, maxsplit=1)
    base = match[0].replace('-', '').replace(' ', '').replace(',', '').replace('.', '').replace("'", '')
    if not base:
        base = text.replace('-', '').replace(' ', '').replace(',', '').replace('.', '').replace("'", '')
    base = base.lower()
    slug = f'{base}uddoktardokan'
    return slug


class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    label = models.CharField(max_length=50, blank=True, help_text='e.g. Home, Office, Parents House')
    name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    street_address = models.CharField(max_length=300, blank=True)
    area = models.CharField(max_length=200, blank=True, help_text='Area / Thana / Upazila')
    district = models.CharField(max_length=200, blank=True)
    division = models.CharField(max_length=200, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)
    is_default = models.BooleanField(default=False, help_text='Use this address by default at checkout')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Address'
        verbose_name_plural = 'Addresses'
        ordering = ['-is_default', '-updated']

    def __str__(self):
        parts = [self.street_address, self.area, self.district, self.division]
        return ', '.join(p for p in parts if p) or f'Address #{self.id}'


def _sibling_unique_slug(parent_id, base_slug):
    """Generate a slug that is unique among the category's siblings only."""
    base = base_slug[:60] or 'category'
    slug = base
    n = 1
    while Category.objects.filter(parent_id=parent_id, slug=slug).exists():
        n += 1
        slug = f'{base[:55]}-{n}'
    return slug


class Category(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, blank=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    icon = models.CharField(max_length=100, blank=True, help_text='Optional icon class (e.g. "fa fa-mobile")')
    description = models.TextField(blank=True, help_text='Short description shown on category pages')
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    is_active = models.BooleanField(default=True, verbose_name='Active', help_text='Inactive categories are hidden from menus')
    sort_order = models.PositiveIntegerField(default=0, verbose_name='Sort order')
    meta_title = models.CharField(max_length=120, blank=True, help_text='SEO title (overrides category name)')
    meta_description = models.TextField(max_length=320, blank=True, help_text='Meta description for search results')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['sort_order', 'name']
        unique_together = ('parent', 'slug')

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _sibling_unique_slug(self.parent_id, slugify(self.name))
        super().save(*args, **kwargs)

    def slug_path(self):
        """List of slugs from root to this category (excludes trailing empty)."""
        slugs = []
        node = self
        while node is not None:
            slugs.insert(0, node.slug)
            node = node.parent
        return slugs

    def get_absolute_url(self):
        return '/category/' + '/'.join(self.slug_path()) + '/'

    def get_path_labels(self):
        """List of (name, url) from root to this category for breadcrumbs."""
        items = []
        node = self
        while node is not None:
            items.insert(0, (node.name, node.get_absolute_url()))
            node = node.parent
        return items

    def __str__(self):
        prefix = f'{self.parent.name} / ' if self.parent_id else ''
        return f'{prefix}{self.name}'


THEME_PRESETS = [
    ('default', 'Default Red', '#e74847', '#333333'),
    ('ocean_blue', 'Ocean Blue', '#2196F3', '#0D47A1'),
    ('forest_green', 'Forest Green', '#4CAF50', '#1B5E20'),
    ('royal_purple', 'Royal Purple', '#9C27B0', '#4A148C'),
    ('sunset_orange', 'Sunset Orange', '#FF5722', '#BF360C'),
    ('teal', 'Teal', '#009688', '#004D40'),
    ('dark_mode', 'Dark Mode', '#1E1E1E', '#424242'),
    ('rose_pink', 'Rose Pink', '#E91E63', '#880E4F'),
    ('amber', 'Amber', '#FFC107', '#FF6F00'),
    ('slate_gray', 'Slate Gray', '#607D8B', '#263238'),
]

THEME_CHOICES = [(t[0], t[1]) for t in THEME_PRESETS]


class Partner(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, blank=True, null=True)
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    logo = models.ImageField(upload_to='partner_logos/', blank=True, null=True)
    profile_image = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    banner = models.ImageField(upload_to='partner_banners/', blank=True, null=True)
    description = models.TextField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    domain_name = models.CharField(max_length=200, blank=True, verbose_name='Domain', help_text='Partner website domain (e.g. example.com)')
    address = models.CharField(max_length=300, blank=True)
    address_street = models.CharField(max_length=300, blank=True, verbose_name='Street / Village / House / Flat')
    address_division = models.CharField(max_length=100, blank=True, verbose_name='Division')
    address_district = models.CharField(max_length=100, blank=True, verbose_name='District')
    address_upazila = models.CharField(max_length=100, blank=True, verbose_name='Upazila')
    voter_id = models.ImageField(upload_to='voter_ids/', blank=True, null=True, verbose_name='Voter ID Card')
    is_dealer = models.BooleanField(default=False)
    is_seller = models.BooleanField(default=False)
    is_union_agent = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='sellers', verbose_name='Dealer (Parent)')
    meta_title = models.CharField(max_length=120, blank=True, help_text='SEO title (overrides store name)')
    meta_description = models.TextField(max_length=320, blank=True, help_text='Meta description for search results')
    show_products = models.BooleanField(default=True, verbose_name='Show Products on Website', help_text='Turn off to hide all your products from the public website')
    show_all_products_section = models.BooleanField(default=True, verbose_name='Show "All Over Available Product" section on store page')
    show_random_products_section = models.BooleanField(default=True, verbose_name='Show "Random product list" section on store page')
    show_slider = models.BooleanField(default=True, verbose_name='Show slider on store page')
    SHOP_STYLE_CHOICES = [
        ('general', 'General Shop'),
        ('shoe', 'Shoe Shop'),
        ('medicine', 'Medicine Shop'),
    ]
    shop_style = models.CharField(max_length=30, choices=SHOP_STYLE_CHOICES, default='general', blank=True)
    theme = models.CharField(max_length=30, choices=THEME_CHOICES, blank=True, default='', verbose_name='Store Theme', help_text='Override site theme for this store. Leave empty to use site default.')
    has_medicine_access = models.BooleanField(default=False, verbose_name='Medicine Catalog Access', help_text='Grant access to the global medicine product catalog for POS')
    medicine_pos_enabled = models.BooleanField(default=False, verbose_name='Medicine POS Enabled', help_text='Master switch — enables Medicine POS with subscription tracking')
    medicine_inventory_enabled = models.BooleanField(default=True, verbose_name='Medicine Inventory Enabled', help_text='When ON, POS tracks stock and deducts inventory. When OFF, POS works without stock tracking.')
    medicine_trial_consumed = models.BooleanField(default=False, verbose_name='Medicine Trial Consumed', help_text='True once the partner has claimed their one-time free 60-day trial. Never reset.')
    blocked = models.BooleanField(default=False, verbose_name='Block deletion', help_text='When blocked, this partner cannot be deleted from admin (prevents cascade delete through related medicine models)')
    custom_redirect_url = models.URLField(max_length=500, blank=True, verbose_name='Custom Logo Redirect URL', help_text='When someone clicks your store logo, they will be redirected to this URL. Leave blank to redirect to the homepage.')
    created = models.DateTimeField(default=timezone.now)
    updated = models.DateTimeField(auto_now=True)

    @property
    def formatted_address(self):
        parts = [p for p in [self.address_street, self.address_upazila, self.address_district, self.address_division] if p]
        if parts:
            return ', '.join(parts) + ', Bangladesh.'
        return self.address or ''

    def save(self, *args, **kwargs):
        if not self.slug:
            if self.address_upazila:
                base = self.address_upazila.strip().replace(' ', '').replace('-', '').replace(',', '').replace('.', '').replace("'", '').lower()
                raw_slug = f'{base}uddoktardokan'
            else:
                raw_slug = generate_partner_slug(self.name)
            self.slug = _unique_slug(Partner, 'slug', raw_slug)
        if not self.domain_name:
            self.domain_name = self.slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class CustomDomain(models.Model):
    """A custom domain a shop owner (Partner) connects to their store.

    A Partner is simultaneously a Seller, Partner or Dealer (role flags on the
    same model). The domain lifecycle is fully automated:

        1. seller/partner/dealer adds a domain        -> status=pending
        2. background DNS check confirms the record   -> dns_status=connected
        3. background certbot/ACME issues a certificate -> ssl_status=active
        4. routing middleware serves the store on the domain -> is_active=True

    Only one domain per owner may be ACTIVE + PRIMARY at a time; activating a
    new domain automatically demotes the previous one.
    """

    ACCOUNT_TYPE_CHOICES = [
        ('SELLER', 'Seller'),
        ('PARTNER', 'Partner'),
        ('DEALER', 'Dealer'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('dns_verified', 'DNS Verified'),
        ('ssl_provisioning', 'SSL Provisioning'),
        ('active', 'Active'),
        ('failed', 'Failed'),
        ('disconnected', 'Disconnected'),
    ]
    DNS_STATUS_CHOICES = [
        ('pending', 'Waiting for DNS'),
        ('connected', 'Connected'),
        ('failed', 'Failed'),
    ]
    SSL_STATUS_CHOICES = [
        ('waiting', 'Waiting'),
        ('provisioning', 'Provisioning'),
        ('active', 'Active'),
        ('failed', 'Failed'),
        ('not_configured', 'Not Configured'),
    ]

    owner = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name='custom_domains', verbose_name='Store / Account')
    domain = models.CharField(max_length=253, verbose_name='Custom Domain', help_text='e.g. mystore.com')
    normalized_domain = models.CharField(max_length=253, unique=True, db_index=True, editable=False)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES, blank=True, default='PARTNER')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    dns_status = models.CharField(max_length=20, choices=DNS_STATUS_CHOICES, default='pending')
    ssl_status = models.CharField(max_length=20, choices=SSL_STATUS_CHOICES, default='waiting')
    is_active = models.BooleanField(default=False, verbose_name='Active', help_text='When ON, requests to this domain are routed to the connected store.')
    is_primary = models.BooleanField(default=False, verbose_name='Primary domain')
    verification_method = models.CharField(max_length=20, default='dns', editable=False)
    dns_verified_at = models.DateTimeField(null=True, blank=True)
    ssl_issued_at = models.DateTimeField(null=True, blank=True)
    ssl_expires_at = models.DateTimeField(null=True, blank=True)
    last_dns_check = models.DateTimeField(null=True, blank=True)
    last_ssl_check = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_primary', '-created_at']
        verbose_name = 'Custom Domain'
        verbose_name_plural = 'Custom Domains'

    def __str__(self):
        return self.domain

    def save(self, *args, **kwargs):
        if self.normalized_domain:
            self.normalized_domain = self.normalized_domain.strip().lower()
        # Only one primary domain per store; activating one retires the others.
        if self.is_primary or self.is_active:
            CustomDomain.objects.filter(owner_id=self.owner_id).exclude(pk=self.pk).update(
                is_primary=False, is_active=False,
            )
        if self.status != 'active':
            self.is_active = False
        super().save(*args, **kwargs)

    def retire(self):
        """Disconnect the domain without deleting history."""
        self.is_active = False
        self.is_primary = False
        self.status = 'disconnected'
        self.ssl_status = 'not_configured'
        self.save(update_fields=['is_active', 'is_primary', 'status', 'ssl_status', 'updated_at'])


def _invalidate_custom_domain_cache(domain):
    key = f'custom_domain:map:{host_key(domain)}'
    cache.delete(key)


@receiver(post_save, sender=CustomDomain)
def _custom_domain_saved(sender, instance, **kwargs):
    _invalidate_custom_domain_cache(instance.normalized_domain)


@receiver(post_delete, sender=CustomDomain)
def _custom_domain_deleted(sender, instance, **kwargs):
    _invalidate_custom_domain_cache(instance.normalized_domain)


class Product(models.Model):
    LABEL_CHOICES = [
        ('new', 'New'),
        ('hot', 'Hot Item'),
        ('discounted', 'Discounted'),
        ('used', 'Used'),
    ]
    name = models.CharField(max_length=300)
    sku = models.CharField(max_length=100, blank=True, verbose_name='SKU (Stock Keeping Unit)', help_text='Unique product code for inventory tracking')
    barcode = models.CharField(max_length=100, blank=True, verbose_name='Barcode', help_text='UPC / EAN / QR code for POS scanning')
    slug = models.SlugField(unique=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    partner = models.ForeignKey(Partner, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    image = models.ImageField(upload_to='productImage/', blank=True, null=True)
    hover_image = models.ImageField(upload_to='Imagehover/', blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    old_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    label = models.CharField(max_length=20, choices=LABEL_CHOICES, blank=True, null=True)
    custom_label = models.CharField(max_length=50, blank=True, null=True, verbose_name='Custom Label')
    short_description = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)
    stock = models.IntegerField(default=0)
    available = models.BooleanField(default=True)
    is_published = models.BooleanField(default=True, verbose_name='Published', help_text='Unpublished products are hidden from the shop')
    trashed = models.BooleanField(default=False, help_text='Soft-deleted; moved to trash')
    trashed_at = models.DateTimeField(null=True, blank=True, help_text='When the product was trashed')
    video_url = models.URLField(max_length=500, blank=True, null=True, help_text="YouTube video URL (e.g. https://www.youtube.com/watch?v=...)")

    # Medicine-specific fields (populated from medicine CSV import or manual entry)
    medicine_brand_name = models.CharField(max_length=200, blank=True, verbose_name='Brand Name')
    medicine_generic_name = models.CharField(max_length=300, blank=True, verbose_name='Generic Name', help_text='Active ingredient / generic name for searching')
    medicine_strength = models.CharField(max_length=100, blank=True, verbose_name='Strength', help_text='e.g. "500 mg"')
    medicine_dosage_form = models.CharField(max_length=100, blank=True, verbose_name='Dosage Form', help_text='e.g. "Tablet", "Syrup", "Capsule"')

    # Weight & Dimensions
    weight = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    weight_unit = models.CharField(max_length=10, choices=[('kg', 'Kg'), ('g', 'Gram'), ('lb', 'Lb'), ('oz', 'Oz')], default='kg')
    length = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    width = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    height = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    dimension_unit = models.CharField(max_length=10, choices=[('cm', 'Cm'), ('inch', 'Inch'), ('m', 'M')], default='cm')

    # Sale unit
    sale_unit = models.CharField(max_length=20, choices=[
        ('piece', 'Piece'),
        ('kg', 'Kg'),
        ('liter', 'Liter'),
        ('dozen', 'Dozen'),
        ('pack', 'Pack'),
        ('box', 'Box'),
        ('custom', 'Custom'),
    ], default='piece')
    custom_unit_label = models.CharField(max_length=100, blank=True, help_text="Custom unit label (e.g. 'Sack', 'Bundle')")

    # Custom price
    price_on_request = models.BooleanField(default=False, help_text="Show 'Price on Request' instead of fixed price")

    # Cost / Wholesale price
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Cost Price (wholesale)')

    # Inventory alerts
    low_stock_threshold = models.IntegerField(default=5, verbose_name='Low Stock Threshold', help_text='Alert when stock falls below this number')

    # SEO
    meta_title = models.CharField(max_length=120, blank=True, help_text='SEO title (overrides product name)')
    meta_description = models.TextField(max_length=320, blank=True, help_text='Meta description for search results')
    og_image = models.ImageField(upload_to='seo/', blank=True, null=True, help_text='Open Graph image (overrides product image)')

    @property
    def profit(self):
        if self.cost_price is not None:
            return self.price - self.cost_price
        return None

    @property
    def margin_percent(self):
        if self.cost_price and self.cost_price > 0:
            return round((self.price - self.cost_price) / self.cost_price * 100, 2)
        return None

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _unique_slug(Product, 'slug', slugify(self.name)[:50])
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def video_embed_url(self):
        if not self.video_url:
            return None
        patterns = [
            r'(?:youtube\.com/watch\?v=)([\w-]+)',
            r'(?:youtu\.be/)([\w-]+)',
            r'(?:youtube\.com/embed/)([\w-]+)',
            r'(?:youtube\.com/shorts/)([\w-]+)',
            r'(?:youtube\.com/watch\?.*v=)([\w-]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, self.video_url)
            if match:
                return f'https://www.youtube.com/embed/{match.group(1)}'
        return None


class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    session_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, db_index=True)
    abandoned_reminder_sent = models.BooleanField(default=False)

    def total_amount(self):
        return sum(item.subtotal() for item in self.items.all())

    def total_items(self):
        return sum(item.quantity for item in self.items.all())

    def __str__(self):
        return f"Cart {self.id}"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    color_variant = models.ForeignKey('ProductColorVariant', on_delete=models.SET_NULL, null=True, blank=True)
    size_variant = models.ForeignKey('ProductSizeVariant', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ['cart', 'product', 'color_variant', 'size_variant']

    def subtotal(self):
        return self.product.price * self.quantity

    def __str__(self):
        s = f"{self.quantity} x {self.product.name}"
        if self.color_variant:
            s += f" ({self.color_variant.color_name})"
        if self.size_variant:
            s += f" [{self.size_variant.size_name}]"
        return s


class BlogPost(models.Model):
    title = models.CharField(max_length=300)
    slug = models.SlugField(unique=True, blank=True)
    image = models.ImageField(upload_to='blog/', blank=True, null=True)
    content = models.TextField()
    excerpt = models.TextField(blank=True)
    author = models.CharField(max_length=100, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    views = models.IntegerField(default=0)
    comments = models.IntegerField(default=0)
    meta_title = models.CharField(max_length=120, blank=True, help_text='SEO title (overrides blog title)')
    meta_description = models.TextField(max_length=320, blank=True, help_text='Meta description for search results')

    class Meta:
        ordering = ['-created']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _unique_slug(BlogPost, 'slug', slugify(self.title)[:50])
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class Contact(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True)
    subject = models.CharField(max_length=300, blank=True)
    message = models.TextField()
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return f"{self.name} - {self.subject}"


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    PAYMENT_STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('paid', 'Paid'),
        ('refunded', 'Refunded'),
    ]
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=50, db_index=True)
    address = models.TextField()
    shipping_address = models.TextField(blank=True, help_text='Separate shipping address if different')
    delivery_notes = models.TextField(blank=True, help_text='Customer delivery instructions')
    delivery_partner = models.ForeignKey('Partner', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Delivery from Partner')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text='Total before discount & fees')
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    fees_total = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text='Total server/COD fees')
    total = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=50, default='Cash on Delivery', choices=[
        ('Cash on Delivery', 'Cash on Delivery'),
        ('SSLCommerz', 'SSLCommerz'),
        ('bkash', 'bKash'),
        ('nagad', 'Nagad'),
        ('rocket', 'Rocket'),
        ('bank', 'Bank Transfer'),
        ('manual', 'Manual Payment'),
    ])
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='unpaid')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    coupon = models.ForeignKey('Coupon', on_delete=models.SET_NULL, null=True, blank=True)
    applied_fees = models.TextField(blank=True, help_text='JSON serialized applied fee data')
    tracking_id = models.CharField(max_length=100, blank=True, help_text='Courier tracking number / product code')
    courier_name = models.CharField(max_length=50, blank=True, choices=[
        ('steadfast', 'Steadfast'),
        ('pathao', 'Pathao'),
        ('sundarban', 'Sundarban'),
        ('ecourier', 'eCourier'),
        ('redx', 'RedX'),
        ('sa_paribahan', 'SA Paribahan'),
        ('other', 'Other'),
    ], help_text='Selected courier service')
    delivery_status = models.CharField(max_length=30, blank=True, choices=[
        ('pending', 'Pending'),
        ('picked_up', 'Picked Up'),
        ('in_transit', 'In Transit'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('failed', 'Delivery Failed'),
    ], default='pending', help_text='Current delivery status')
    estimated_delivery = models.DateField(null=True, blank=True)
    admin_notes = models.TextField(blank=True, help_text='Internal staff notes')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return f"Order #{self.id} - {self.name}"

    def get_applied_fees(self):
        if self.applied_fees:
            try:
                return json.loads(self.applied_fees)
            except (json.JSONDecodeError, TypeError):
                return []
        return []


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    product_name = models.CharField(max_length=300)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text='Cost price at time of order')
    color_name = models.CharField(max_length=100, blank=True, default='')
    color_code = models.CharField(max_length=7, blank=True, default='')
    size_name = models.CharField(max_length=50, blank=True, default='')

    class Meta:
        ordering = ['id']

    @property
    def profit(self):
        if self.cost_price is not None:
            return (self.price - self.cost_price) * self.quantity
        return None

    def __str__(self):
        s = f"{self.quantity} x {self.product_name}"
        if self.color_name:
            s += f" ({self.color_name})"
        if self.size_name:
            s += f" [{self.size_name}]"
        return s


class ServerFee(models.Model):
    FEE_TYPE_CHOICES = [
        ('fixed', 'Fixed Amount'),
        ('percentage', 'Percentage'),
    ]
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    fee_type = models.CharField(max_length=20, choices=FEE_TYPE_CHOICES, default='fixed')
    value = models.DecimalField(max_digits=10, decimal_places=2, help_text='Amount or percentage value')
    min_order_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text='Only apply if order subtotal >= this amount')
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True, help_text='Internal notes about this fee')
    link_url = models.URLField(max_length=500, blank=True, help_text='Link to policy / info page')
    link_text = models.CharField(max_length=100, blank=True, help_text='Display text for the link (e.g. "See delivery policy")')
    order = models.IntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _unique_slug(ServerFee, 'slug', slugify(self.name))
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def calculate(self, subtotal):
        if self.fee_type == 'fixed':
            return self.value
        elif self.fee_type == 'percentage':
            return round(subtotal * self.value / 100, 2)
        return 0


class Coupon(models.Model):
    DISCOUNT_TYPE_CHOICES = [
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    ]
    SCOPE_CHOICES = [
        ('all', 'All Products'),
        ('specific', 'Specific Products'),
    ]
    code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, help_text='Percentage or fixed amount')
    min_order_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text='Minimum cart subtotal required')
    max_discount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text='Maximum discount amount (for percentage coupons)')
    max_uses = models.IntegerField(default=0, help_text='0 = unlimited')
    used_count = models.IntegerField(default=0, editable=False)
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default='all')
    products = models.ManyToManyField(Product, blank=True, help_text='Only applies to these products (if scope=specific)')
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return self.code

    def is_valid(self, user, subtotal, cart_products):
        from django.utils import timezone
        now = timezone.now()
        if not self.is_active:
            return False, 'Coupon is inactive'
        if now < self.valid_from or now > self.valid_to:
            return False, 'Coupon has expired'
        if self.max_uses > 0 and self.used_count >= self.max_uses:
            return False, 'Coupon usage limit reached'
        if self.min_order_amount and subtotal < self.min_order_amount:
            return False, f'Minimum order amount ৳{self.min_order_amount} required'
        if self.scope == 'specific' and self.products.exists():
            valid_product_ids = set(self.products.values_list('id', flat=True))
            cart_product_ids = {p.id for p in cart_products}
            if not cart_product_ids.intersection(valid_product_ids):
                return False, 'Coupon does not apply to items in your cart'
        return True, 'Coupon applied!'

    def calculate_discount(self, subtotal, cart_products):
        if self.discount_type == 'fixed':
            discount = self.discount_value
        else:
            applicable_subtotal = subtotal
            if self.scope == 'specific' and self.products.exists():
                valid_ids = set(self.products.values_list('id', flat=True))
                applicable_subtotal = sum(p.price for p in cart_products if p.id in valid_ids)
            discount = round(applicable_subtotal * self.discount_value / 100, 2)
            if self.max_discount:
                discount = min(discount, self.max_discount)
        return discount


class CouponUsage(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='usages')
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='coupon_usages')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Coupon Usages'
        unique_together = [('coupon', 'order')]

    def __str__(self):
        return f'{self.coupon.code} - Order #{self.order.id}'


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='extra_images')
    image = models.ImageField(upload_to='product_extra/')
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.product.name} image #{self.order}'


PRESET_COLORS = [
    ('#FF0000', 'Red'),
    ('#0000FF', 'Blue'),
    ('#00AA00', 'Green'),
    ('#FFD700', 'Yellow'),
    ('#000000', 'Black'),
    ('#FFFFFF', 'White'),
    ('#808080', 'Gray'),
    ('#FF8C00', 'Orange'),
    ('#800080', 'Purple'),
    ('#FF69B4', 'Pink'),
    ('#8B4513', 'Brown'),
    ('#000080', 'Navy'),
    ('#87CEEB', 'Sky Blue'),
    ('#32CD32', 'Lime'),
    ('#800000', 'Maroon'),
    ('#008080', 'Teal'),
    ('#EE82EE', 'Violet'),
    ('#DAA520', 'Gold'),
    ('#C0C0C0', 'Silver'),
    ('#FF7F50', 'Coral'),
]


class ProductColorVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='color_variants')
    color_name = models.CharField(max_length=100)
    color_code = models.CharField(max_length=7, help_text="Hex color code, e.g. #FF0000")
    image = models.ImageField(upload_to='color_variants/', blank=True, null=True)
    price_adjustment = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Extra price for this color variant")
    stock = models.IntegerField(default=0, help_text="Stock for this specific color (0 = use parent product stock)")
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.product.name} - {self.color_name}'


PRESET_SIZES = ['S', 'M', 'L', 'XL', '2XL', '3XL', 'Free Size']


class ProductSizeVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='size_variants')
    size_name = models.CharField(max_length=100)
    price_adjustment = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock = models.IntegerField(default=0, help_text="Stock for this specific size (0 = use parent product stock)")
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.product.name} - {self.size_name}'


class SiteLogo(models.Model):
    logo = models.ImageField(upload_to='site_logo/')
    favicon = models.ImageField(upload_to='site_favicon/', blank=True, null=True)
    site_name = models.CharField(max_length=200, default='Uddoktar Dokan')
    site_tagline = models.CharField(max_length=200, default='উদ্যোক্তার বাজার', blank=True)
    search_placeholder = models.CharField(max_length=300, default='পণ্যের নাম, কোড, ক্যাটাগরি ও সাব-ক্যাটাগরি লিখে সার্চ করুন', help_text='Placeholder text for the search bar')
    site_theme = models.CharField(max_length=30, choices=THEME_CHOICES, blank=True, default='', help_text='Site-wide theme (applies to homepage and all partner stores)')
    site_primary_color = models.CharField(max_length=20, blank=True, default='#e74847', help_text='Site-wide primary color (hex)')
    site_secondary_color = models.CharField(max_length=20, blank=True, default='#333333', help_text='Site-wide secondary color (hex)')
    partner_delivery_enabled = models.BooleanField(default=True, verbose_name='Allow Partner/Dealer address selection in checkout')
    site_phone = models.CharField(max_length=30, blank=True, default='01910422200', help_text='Contact number shown in the footer')
    site_whatsapp = models.CharField(max_length=30, blank=True, default='8801910422200', help_text='WhatsApp number (country code + number, no +) used in the floating bar & footer')
    site_email = models.EmailField(max_length=200, blank=True, default='', help_text='Contact email shown in the footer (optional)')
    site_address_bd = models.CharField(max_length=300, blank=True, default='144/G,Zigatola(Near BGB Pilkhana)Mirpur-1,Dhaka:1206', help_text='Local (Bangladesh) address shown in the footer')
    site_address_us = models.CharField(max_length=300, blank=True, default='Delwar,USA', help_text='Foreign address shown in the footer (optional)')
    footer_about = models.TextField(blank=True, default='', help_text='Short about text shown under the footer logo')
    newsletter_title = models.CharField(max_length=150, blank=True, default='Sign up for newsletter', help_text='Newsletter section title')
    newsletter_subtitle = models.CharField(max_length=250, blank=True, default='Get the latest deals and special offers', help_text='Newsletter section subtitle')
    footer_copyright = models.CharField(max_length=300, blank=True, default='Copyright © 2025-2026 Uddoktar Dokan. All Rights Reserved.', help_text='Copyright line shown at the bottom of the footer')
    show_newsletter_section = models.BooleanField(default=True, verbose_name='Show newsletter section')
    show_contact_section = models.BooleanField(default=True, verbose_name='Show contact info column')
    show_follow_us_section = models.BooleanField(default=True, verbose_name='Show follow-us (social) column')
    show_policy_buttons = models.BooleanField(default=True, verbose_name='Show policy buttons (Terms, Return & Refund, Company Policy)')
    show_copyright_bar = models.BooleanField(default=True, verbose_name='Show copyright bottom bar')
    show_payment_icons = models.BooleanField(default=True, verbose_name='Show payment card icons')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Site Settings'
        verbose_name_plural = 'Site Settings'

    def save(self, *args, **kwargs):
        if self.pk is None and SiteLogo.objects.exists():
            existing = SiteLogo.objects.first()
            existing.logo = self.logo or existing.logo
            existing.favicon = self.favicon or existing.favicon
            existing.site_name = self.site_name
            existing.site_tagline = self.site_tagline
            existing.search_placeholder = self.search_placeholder
            existing.site_theme = self.site_theme
            existing.site_primary_color = self.site_primary_color
            existing.site_secondary_color = self.site_secondary_color
            existing.partner_delivery_enabled = self.partner_delivery_enabled
            existing.site_phone = self.site_phone
            existing.site_whatsapp = self.site_whatsapp
            existing.site_email = self.site_email
            existing.site_address_bd = self.site_address_bd
            existing.site_address_us = self.site_address_us
            existing.footer_about = self.footer_about
            existing.newsletter_title = self.newsletter_title
            existing.newsletter_subtitle = self.newsletter_subtitle
            existing.footer_copyright = self.footer_copyright
            existing.show_newsletter_section = self.show_newsletter_section
            existing.show_contact_section = self.show_contact_section
            existing.show_follow_us_section = self.show_follow_us_section
            existing.show_policy_buttons = self.show_policy_buttons
            existing.show_copyright_bar = self.show_copyright_bar
            existing.show_payment_icons = self.show_payment_icons
            existing.save()
            return
        super().save(*args, **kwargs)

    def __str__(self):
        return self.site_name or 'Site Settings'


class NewsTicker(models.Model):
    TYPE_CHOICES = [
        ('ticker', 'News Ticker'),
        ('search_placeholder', 'Search Placeholder'),
    ]
    type = models.CharField(max_length=30, choices=TYPE_CHOICES, default='ticker')
    text = models.TextField(help_text='News ticker text. You can use emoji like 🚀 🎁 📦 📢')
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text='Lower numbers appear first')
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'[{self.get_type_display()}] {self.text[:50]}'


class ProductReview(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.PositiveIntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField()
    image = models.ImageField(upload_to='review_images/', blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return f'{self.user.username} - {self.product.name} ({self.rating}/5)'


class HomeBanner(models.Model):
    title = models.CharField(max_length=200, blank=True)
    image = models.ImageField(upload_to='home_banners/')
    link_url = models.CharField(max_length=500, blank=True, help_text='Optional URL the banner links to')
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title or f'Banner #{self.id}'


class Slider(models.Model):
    title = models.CharField(max_length=200, blank=True)
    subtitle = models.CharField(max_length=300, blank=True)
    image = models.ImageField(upload_to='sliders/')
    link_url = models.CharField(max_length=500, blank=True, help_text='Optional URL the slider links to')
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title or f'Slider #{self.id}'


class PartnerBanner(models.Model):
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name='extra_banners')
    image = models.ImageField(upload_to='partner_extra_banners/')
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'Banner for {self.partner.name}'


class PartnerSlider(models.Model):
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name='sliders')
    title = models.CharField(max_length=200, blank=True)
    subtitle = models.CharField(max_length=300, blank=True)
    image = models.ImageField(upload_to='partner_sliders/')
    link_url = models.CharField(max_length=500, blank=True, help_text='Optional URL the slider links to')
    button_text = models.CharField(max_length=100, blank=True, default='Click for Partner', help_text='Text shown on the slide button')
    max_height = models.PositiveIntegerField(default=400, help_text='Max slide height in pixels (max 500)')
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']

    def save(self, *args, **kwargs):
        if self.max_height > 500:
            self.max_height = 500
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title or f'Partner Slider #{self.id}'


class PartnerNavMenu(models.Model):
    URL_TYPE_CHOICES = [
        ('named_url', 'Named URL'),
        ('path', 'Path'),
    ]
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name='nav_menu_items')
    title = models.CharField(max_length=100)
    url = models.CharField(max_length=500, blank=True, help_text="URL or named URL (leave blank for parent items with sub-menus)")
    url_type = models.CharField(max_length=20, choices=URL_TYPE_CHOICES, default='named_url')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    login_required = models.BooleanField(default=False)
    logout_required = models.BooleanField(default=False)

    class Meta:
        ordering = ['order']
        verbose_name_plural = 'Partner Nav Menus'

    def __str__(self):
        return self.title


class SideBanner(models.Model):
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, null=True, blank=True, related_name='side_banners')
    title = models.CharField(max_length=200, blank=True)
    image = models.ImageField(upload_to='side_banners/')
    link_url = models.CharField(max_length=500, blank=True)
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title or f'Side Banner #{self.id}'


SECTION_CHOICES = [
    ('', 'All Sections (default)'),
    ('home_all', 'Homepage — All Over Available Product'),
    ('home_partner', 'Homepage — All Partner Product'),
    ('home_hot', 'Homepage — All Partner Hot Products'),
    ('shop', 'Shop Page'),
    ('partner', 'Partner Store'),
]


class ShopSidebarSlider(models.Model):
    image = models.ImageField(upload_to='shop_sidebar_sliders/')
    title = models.CharField(max_length=200, blank=True, help_text='Optional title overlay')
    link_url = models.CharField(max_length=500, blank=True, help_text='Link when clicked')
    section = models.CharField(max_length=30, choices=SECTION_CHOICES, blank=True, default='', help_text='Which section this slider appears in. Leave blank for all sections.')
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']
        verbose_name = 'Shop Sidebar Slider'
        verbose_name_plural = 'Shop Sidebar Sliders'

    def __str__(self):
        label = self.get_section_display() if self.section else 'All'
        return f'{self.title or f"Sidebar Slider #{self.id}"} [{label}]'


class ShopBanner(models.Model):
    image = models.ImageField(upload_to='shop_banners/')
    title = models.CharField(max_length=200, blank=True)
    link_url = models.CharField(max_length=500, blank=True)
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']
        verbose_name = 'Shop Banner'
        verbose_name_plural = 'Shop Banners'

    def __str__(self):
        return self.title or f'Shop Banner #{self.id}'


class ShopSidebarBottomBanner(models.Model):
    image = models.ImageField(upload_to='shop_sidebar_bottom/')
    title = models.CharField(max_length=200, blank=True)
    link_url = models.CharField(max_length=500, blank=True)
    section = models.CharField(max_length=30, choices=SECTION_CHOICES, blank=True, default='', help_text='Which section this banner appears in. Leave blank for all sections.')
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']
        verbose_name = 'Shop Sidebar Bottom Banner'
        verbose_name_plural = 'Shop Sidebar Bottom Banners'

    def __str__(self):
        label = self.get_section_display() if self.section else 'All'
        return f'{self.title or f"Sidebar Bottom Banner #{self.id}"} [{label}]'


SLIDER_AREA_CHOICES = [
    ('banner', 'Top Banner (Shop page)'),
    ('sidebar', 'Sidebar Slider (Shop page)'),
    ('sidebar_bottom', 'Sidebar Bottom Banner (Shop page)'),
]


class ShopSliderConfig(models.Model):
    """Per-area settings for the Shop page sliders (time, size, hide/show)."""
    area = models.CharField(max_length=30, choices=SLIDER_AREA_CHOICES, unique=True)
    autoplay_time = models.PositiveIntegerField(default=3, help_text='Seconds each slide stays on screen (slide changing time)')
    height = models.PositiveIntegerField(default=250, help_text='Slider container height in pixels')
    width = models.PositiveIntegerField(default=0, help_text='Slider container width in pixels. Leave 0 for full width (100%).')
    show_title = models.BooleanField(default=True, help_text='Show the title overlay on each slide')
    is_active = models.BooleanField(default=True, help_text='Uncheck to hide this slider on the page')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Shop Slider Setting'
        verbose_name_plural = 'Shop Slider Settings'

    def __str__(self):
        return f'{self.get_area_display()} — {self.autoplay_time}s | {self.height}px | {self.width or "full"}px | {"SHOW" if self.is_active else "HIDDEN"}'

    @classmethod
    def defaults(cls):
        return {
            'banner': dict(autoplay_time=3, height=200, width=0, show_title=True),
            'sidebar': dict(autoplay_time=3, height=250, width=0, show_title=True),
            'sidebar_bottom': dict(autoplay_time=3, height=250, width=0, show_title=True),
        }

    @classmethod
    def as_map(cls):
        """Dict {area: config} with a safe fallback row for any missing area."""
        missing = {a: False for a in [c[0] for c in SLIDER_AREA_CHOICES]}
        for c in cls.objects.all():
            missing[c.area] = c
        out = {}
        for area, defaults in cls.defaults().items():
            obj = missing.get(area) or cls(area=area, **defaults)
            out[area] = obj
        return out


class SocialMediaLink(models.Model):
    name = models.CharField(max_length=100)
    url = models.URLField(max_length=500)
    icon_class = models.CharField(
        max_length=100,
        choices=[
            ('fab fa-facebook-f', 'Facebook (f)'),
            ('fab fa-facebook', 'Facebook'),
            ('fab fa-square-facebook', 'Facebook Square'),
            ('fab fa-x-twitter', 'X / Twitter (bird)'),
            ('fab fa-twitter', 'Twitter (old bird)'),
            ('fab fa-instagram', 'Instagram'),
            ('fab fa-youtube', 'YouTube'),
            ('fab fa-whatsapp', 'WhatsApp'),
            ('fab fa-linkedin-in', 'LinkedIn'),
            ('fab fa-telegram', 'Telegram'),
            ('fab fa-pinterest-p', 'Pinterest'),
            ('fab fa-tiktok', 'TikTok'),
            ('fab fa-threads', 'Threads'),
            ('fab fa-snapchat', 'Snapchat'),
            ('fa fa-phone', 'Phone / Call'),
            ('fa fa-envelope', 'Email'),
        ],
        default='fab fa-facebook-f',
        help_text="Font Awesome icon class (brand icons start with 'fab', solid icons with 'fa')",
    )
    color = models.CharField(
        max_length=20,
        choices=[
            ('#25D366', 'WhatsApp Green'),
            ('#1877F2', 'Facebook Blue'),
            ('#FF0000', 'YouTube Red'),
            ('#E4405F', 'Instagram Pink'),
            ('#000000', 'X / Black'),
            ('#1DA1F2', 'Twitter Blue'),
            ('#0A66C2', 'LinkedIn Blue'),
            ('#0088CC', 'Telegram Blue'),
            ('#CB2027', 'Pinterest Red'),
            ('#010101', 'TikTok Black'),
            ('#28a745', 'Phone / Call Green'),
            ('#0ABF53', 'Generic Green'),
            ('#6f42c1', 'Generic Purple'),
            ('#3d73dd', 'Generic Blue'),
        ],
        default='#1877F2',
        help_text="Background color for the floating bar icon (hex).",
    )
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']
        verbose_name_plural = 'Social Media Links'

    def __str__(self):
        return self.name


class PaymentIcon(models.Model):
    name = models.CharField(max_length=100)
    image = models.ImageField(upload_to='payment_icons/', blank=True, null=True, help_text='Upload a payment card/brand logo')
    image_url = models.URLField(max_length=500, blank=True, default='', help_text='Or enter an external image URL (e.g. CDN) — used when no image is uploaded')
    link = models.URLField(max_length=500, blank=True, default='', verbose_name='Link (optional)')
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True, help_text='Show this icon in the footer')

    class Meta:
        ordering = ['order']
        verbose_name = 'Payment Icon'
        verbose_name_plural = 'Payment Icons'

    @property
    def display_url(self):
        return self.image.url if self.image else (self.image_url or '')

    def __str__(self):
        return self.name


class Page(models.Model):
    TEMPLATE_CHOICES = [
        ('default', 'Default Layout'),
        ('full_width', 'Full Width Layout'),
        ('landing', 'Landing Page'),
    ]
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    content = models.TextField(blank=True)
    meta_title = models.CharField(max_length=200, blank=True, help_text='Override title tag for SEO')
    meta_description = models.TextField(max_length=500, blank=True, help_text='Meta description for search engines')
    meta_keywords = models.CharField(max_length=300, blank=True, help_text='Comma-separated keywords')
    featured_image = models.ImageField(upload_to='pages/', blank=True, null=True)
    template_name = models.CharField(max_length=50, choices=TEMPLATE_CHOICES, default='default')
    show_in_header = models.BooleanField(default=False, help_text='Show link in header navigation')
    show_in_footer = models.BooleanField(default=False, help_text='Show link in footer')
    is_active = models.BooleanField(default=True)
    custom_css = models.TextField(blank=True, help_text='Custom CSS for this page only')
    custom_js = models.TextField(blank=True, help_text='Custom JavaScript for this page only')
    order = models.IntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title


class LandingPage(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)

    # Hero Section
    hero_title = models.CharField(max_length=300, blank=True)
    hero_subtitle = models.TextField(blank=True)
    hero_background = models.ImageField(upload_to='landing/hero/', blank=True, null=True, help_text='Background image for hero section')
    hero_overlay_color = models.CharField(max_length=20, blank=True, default='rgba(0,0,0,0.5)', help_text='CSS overlay color over hero background')
    hero_cta_text = models.CharField(max_length=100, blank=True, default='Shop Now')
    hero_cta_link = models.CharField(max_length=500, blank=True)

    # About Section
    about_heading = models.CharField(max_length=300, blank=True, default='About Us')
    about_content = models.TextField(blank=True)
    about_image = models.ImageField(upload_to='landing/about/', blank=True, null=True)

    # Featured Products
    featured_products_heading = models.CharField(max_length=300, blank=True, default='Featured Products')
    featured_products = models.ManyToManyField('Product', blank=True, related_name='landing_pages')

    # Featured Partners
    show_partners = models.BooleanField(default=True, help_text='Show partners/dealers section')
    partners_heading = models.CharField(max_length=300, blank=True, default='Our Partners')

    # Statistics / Counters
    show_stats = models.BooleanField(default=False)
    stat_1_label = models.CharField(max_length=100, blank=True, default='Products')
    stat_1_value = models.IntegerField(default=0)
    stat_2_label = models.CharField(max_length=100, blank=True, default='Partners')
    stat_2_value = models.IntegerField(default=0)
    stat_3_label = models.CharField(max_length=100, blank=True, default='Happy Customers')
    stat_3_value = models.IntegerField(default=0)
    stat_4_label = models.CharField(max_length=100, blank=True, default='Orders')
    stat_4_value = models.IntegerField(default=0)

    # Theme
    primary_color = models.CharField(max_length=20, blank=True, default='#e74847', help_text='Primary brand color (hex)')
    secondary_color = models.CharField(max_length=20, blank=True, default='#333333', help_text='Secondary color (hex)')
    custom_css = models.TextField(blank=True, help_text='Custom CSS for this landing page')

    # SEO
    meta_title = models.CharField(max_length=200, blank=True, help_text='Override title tag for SEO')
    meta_description = models.TextField(max_length=500, blank=True, help_text='Meta description for search engines')
    meta_keywords = models.CharField(max_length=300, blank=True, help_text='Comma-separated keywords')

    # Bottom CTA
    bottom_cta_heading = models.CharField(max_length=300, blank=True, default='Ready to Get Started?')
    bottom_cta_text = models.CharField(max_length=200, blank=True, default='Contact us today!')
    bottom_cta_link = models.CharField(max_length=500, blank=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title


class NavMenu(models.Model):
    URL_TYPE_CHOICES = [
        ('named_url', 'Named URL'),
        ('path', 'Path'),
    ]
    KIND_CHOICES = [
        ('link', 'Link'),
        ('categories', 'Categories menu'),
        ('account', 'Login / Signup / Dashboard'),
    ]
    title = models.CharField(max_length=100)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default='link', help_text="'Categories menu' renders the categories button + mega menu. 'Login / Signup / Dashboard' renders the account button (login/signup when logged out, dashboard when logged in).")
    url = models.CharField(max_length=200, blank=True, help_text="Named URL (e.g. 'home', 'shop_grid') or path (e.g. '/shop/'). Not used for Categories / Account buttons.")
    url_type = models.CharField(max_length=20, choices=URL_TYPE_CHOICES, default='named_url')
    open_new_tab = models.BooleanField(default=False, verbose_name='Open in new tab')
    match_startswith = models.BooleanField(default=False, help_text="Check if request path starts with this URL (for Dashboard sub-pages)")
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    show_desktop = models.BooleanField(default=True, verbose_name='Show in desktop menu')
    show_mobile = models.BooleanField(default=True, verbose_name='Show in mobile menu')
    login_required = models.BooleanField(default=False, help_text="Only show to logged-in users")
    logout_required = models.BooleanField(default=False, help_text="Only show to logged-out users")

    class Meta:
        ordering = ['order']
        verbose_name_plural = 'Nav Menu'

    def __str__(self):
        return self.title

    def get_url(self):
        """Return a safe, renderable URL for this item."""
        from django.urls import reverse, NoReverseMatch
        if self.kind == 'account':
            return '#'
        if self.url_type == 'named_url':
            try:
                return reverse(self.url)
            except (NoReverseMatch, TypeError):
                return '#'
        return self.url or '#'


class CustomOrder(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name='custom_orders')
    product_title = models.CharField(max_length=300)
    product_description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    buyer_name = models.CharField(max_length=200)
    buyer_phone = models.CharField(max_length=50)
    buyer_address = models.TextField(blank=True)
    buyer_email = models.EmailField(blank=True)
    seller_name = models.CharField(max_length=200, blank=True)
    seller_phone = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True, help_text='Internal admin notes')
    created_order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name='custom_order_source', help_text='Auto-created Order when approved')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']
        verbose_name_plural = 'Custom Orders'

    def __str__(self):
        return f'Custom Order #{self.id} - {self.product_title}'


class AdminCommission(models.Model):
    COMMISSION_ON_CHOICES = [
        ('profit', 'Partner Profit'),
        ('sale_price', 'Total Sale Price'),
    ]
    commission_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text='Percentage charged from partners on each sale')
    commission_on = models.CharField(max_length=20, choices=COMMISSION_ON_CHOICES, default='profit', verbose_name='Commission Basis')
    is_active = models.BooleanField(default=True, help_text='Apply this commission to all partner profit calculations')
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Admin Commission'
        verbose_name_plural = 'Admin Commission'

    def save(self, *args, **kwargs):
        if self.pk is None and AdminCommission.objects.exists():
            existing = AdminCommission.objects.first()
            existing.commission_percentage = self.commission_percentage
            existing.commission_on = self.commission_on
            existing.is_active = self.is_active
            existing.save()
            return
        super().save(*args, **kwargs)

    def calculate_commission(self, gross_profit, total_sale):
        if not self.is_active:
            return 0
        if self.commission_on == 'profit':
            return round(gross_profit * self.commission_percentage / 100, 2)
        else:
            return round(total_sale * self.commission_percentage / 100, 2)

    def __str__(self):
        return f'Commission: {self.commission_percentage}% on {self.get_commission_on_display()}'


def _generate_txn_ref():
    import secrets
    import string
    today = timezone.now().strftime('%Y%m%d')
    rand = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    return f'TXN-{today}-{rand}'


class PartnerWallet(models.Model):
    partner = models.OneToOneField(Partner, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    locked_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text='Bonus/referral money that cannot be withdrawn yet')
    total_admin_commission = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text='Cumulative admin commission earned from this partner')
    total_earned = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_withdrawn = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_fees_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_frozen = models.BooleanField(default=False, help_text='Prevents withdrawals when frozen')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Partner Wallet'
        verbose_name_plural = 'Partner Wallets'

    @property
    def available_balance(self):
        return self.balance - self.locked_balance

    def __str__(self):
        return f'{self.partner.name} — ৳{self.balance} (available: ৳{self.available_balance})'


class WalletTransaction(models.Model):
    TXN_TYPES = [
        ('order_credit', 'Order Credit'),
        ('manual_credit', 'Manual Credit'),
        ('manual_debit', 'Manual Debit'),
        ('withdrawal', 'Withdrawal'),
        ('withdrawal_fee', 'Withdrawal Fee'),
        ('commission_refund', 'Commission Refund'),
        ('signup_bonus', 'Signup Bonus'),
        ('bonus_release', 'Bonus Released'),
        ('subscription_payment', 'Subscription Payment'),
    ]
    wallet = models.ForeignKey(PartnerWallet, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_before = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)
    type = models.CharField(max_length=30, choices=TXN_TYPES)
    description = models.CharField(max_length=500)
    reference_id = models.CharField(max_length=50, unique=True, blank=True)
    order = models.ForeignKey('Order', on_delete=models.SET_NULL, null=True, blank=True)
    withdrawal = models.ForeignKey('WithdrawalRequest', on_delete=models.SET_NULL, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Wallet Transaction'
        verbose_name_plural = 'Wallet Transactions'
        ordering = ['-created']

    def save(self, *args, **kwargs):
        if not self.reference_id:
            self.reference_id = _generate_txn_ref()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.reference_id} — {self.get_type_display()} — ৳{self.amount}'


class WithdrawalRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
    ]
    METHOD_CHOICES = [
        ('bkash', 'bKash'),
        ('nagad', 'Nagad'),
        ('rocket', 'Rocket'),
        ('bank', 'Bank Transfer'),
    ]
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name='withdrawals')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, help_text='Amount after fee deduction')
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    account_number = models.CharField(max_length=100)
    account_holder = models.CharField(max_length=200, blank=True)
    bank_name = models.CharField(max_length=200, blank=True, help_text='Required for Bank Transfer')
    branch = models.CharField(max_length=200, blank=True)
    routing_number = models.CharField(max_length=50, blank=True)
    note = models.TextField(blank=True, help_text='Optional note from partner')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True, help_text='Internal admin notes')
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_withdrawals')
    processed_at = models.DateTimeField(null=True, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Withdrawal Request'
        verbose_name_plural = 'Withdrawal Requests'
        ordering = ['-requested_at']

    def __str__(self):
        return f'{self.partner.name} — ৳{self.amount} — {self.get_status_display()}'


class PayoutMethod(models.Model):
    METHOD_CHOICES = [
        ('bkash', 'bKash'),
        ('nagad', 'Nagad'),
        ('rocket', 'Rocket'),
        ('bank', 'Bank Transfer'),
    ]
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name='payout_methods')
    method_type = models.CharField(max_length=20, choices=METHOD_CHOICES)
    account_number = models.CharField(max_length=100)
    account_holder = models.CharField(max_length=200, blank=True)
    bank_name = models.CharField(max_length=200, blank=True)
    branch = models.CharField(max_length=200, blank=True)
    routing_number = models.CharField(max_length=50, blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Payout Method'
        verbose_name_plural = 'Payout Methods'
        ordering = ['-is_default', '-created']

    def save(self, *args, **kwargs):
        if self.is_default:
            PayoutMethod.objects.filter(partner=self.partner, is_default=True).update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.get_method_type_display()} — {self.account_number}'


class WalletSettings(models.Model):
    FEE_TYPE_CHOICES = [('fixed', 'Fixed Amount'), ('percentage', 'Percentage')]
    min_withdrawal = models.DecimalField(max_digits=12, decimal_places=2, default=500.00, help_text='Minimum withdrawal amount')
    max_withdrawal = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text='0 = unlimited')
    withdrawal_fee_type = models.CharField(max_length=20, choices=FEE_TYPE_CHOICES, default='percentage')
    withdrawal_fee_value = models.DecimalField(max_digits=10, decimal_places=2, default=1.00, help_text='Fee amount or percentage')
    auto_approve_withdrawals = models.BooleanField(default=False, help_text='Auto-approve withdrawals under min threshold')
    max_pending_withdrawals = models.IntegerField(default=3, help_text='Max concurrent pending withdrawals per partner')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Wallet Settings'
        verbose_name_plural = 'Wallet Settings'

    def save(self, *args, **kwargs):
        if self.pk is None and WalletSettings.objects.exists():
            existing = WalletSettings.objects.first()
            existing.min_withdrawal = self.min_withdrawal
            existing.max_withdrawal = self.max_withdrawal
            existing.withdrawal_fee_type = self.withdrawal_fee_type
            existing.withdrawal_fee_value = self.withdrawal_fee_value
            existing.auto_approve_withdrawals = self.auto_approve_withdrawals
            existing.max_pending_withdrawals = self.max_pending_withdrawals
            existing.save()
            return
        super().save(*args, **kwargs)

    def calculate_fee(self, amount):
        if self.withdrawal_fee_type == 'fixed':
            return min(self.withdrawal_fee_value, amount)
        return round(amount * self.withdrawal_fee_value / 100, 2)

    def __str__(self):
        return f'Wallet Settings (min ৳{self.min_withdrawal}, fee: {self.withdrawal_fee_value}% / {"fixed" if self.withdrawal_fee_type == "fixed" else "%"})'


class PlatformBalance(models.Model):
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text='Current platform balance')
    total_commission_collected = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text='Total admin commission earned')
    total_manual_credits_given = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text='Total manual credits given to partners')
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Platform Balance'
        verbose_name_plural = 'Platform Balance'

    def save(self, *args, **kwargs):
        if self.pk is not None and PlatformBalance.objects.exclude(pk=self.pk).exists():
            return
        if self.pk is None and PlatformBalance.objects.exists():
            return
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Platform Balance: ৳{self.balance}'


class DeliveryLog(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='delivery_logs')
    status = models.CharField(max_length=30, choices=[
        ('pending', 'Pending'),
        ('picked_up', 'Picked Up'),
        ('in_transit', 'In Transit'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('failed', 'Delivery Failed'),
    ])
    note = models.TextField(blank=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Delivery Log'
        verbose_name_plural = 'Delivery Logs'
        ordering = ['-created']

    def __str__(self):
        return f'Order #{self.order.id} — {self.get_status_display()} — {self.created.strftime("%d %b %Y %H:%M")}'


# ─── Feature 1: Wishlist ───

class Wishlist(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    session_id = models.CharField(max_length=100, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Wishlist'
        verbose_name_plural = 'Wishlists'

    @classmethod
    def get_or_create_for(cls, request):
        if request.user.is_authenticated:
            wishlist, _ = cls.objects.get_or_create(user=request.user)
        else:
            sid = request.session.session_key
            if not sid:
                request.session.save()
                sid = request.session.session_key
            wishlist, _ = cls.objects.get_or_create(session_id=sid, user__isnull=True)
        return wishlist

    def total_items(self):
        return self.items.count()

    def __str__(self):
        owner = self.user or self.session_id
        return f'Wishlist ({owner})'


class WishlistItem(models.Model):
    wishlist = models.ForeignKey(Wishlist, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    added = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Wishlist Item'
        verbose_name_plural = 'Wishlist Items'
        unique_together = ['wishlist', 'product']
        ordering = ['-added']

    def __str__(self):
        return str(self.product)


# ─── Feature 4: Notification ───

class Notification(models.Model):
    NOTIF_TYPES = [
        ('order_placed', 'Order Placed'),
        ('order_status', 'Order Status Changed'),
        ('payment_received', 'Payment Received'),
        ('wallet_credit', 'Wallet Credited'),
        ('withdrawal_status', 'Withdrawal Status'),
        ('new_review', 'New Review'),
        ('new_seller', 'New Seller Added'),
        ('admin_message', 'Admin Message'),
        ('ticket_update', 'Ticket Update'),
        ('low_stock', 'Low Stock Alert'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    type = models.CharField(max_length=30, choices=NOTIF_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    link = models.CharField(max_length=500, blank=True)
    is_read = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created']

    def __str__(self):
        return f'[{self.get_type_display()}] {self.title}'


# ─── Feature 5: Shipping Rule ───

class ShippingRule(models.Model):
    BASED_ON_CHOICES = [
        ('weight', 'Weight'),
        ('price', 'Order Price'),
        ('location', 'Location'),
    ]
    name = models.CharField(max_length=100)
    courier = models.CharField(max_length=50, blank=True, choices=[
        ('steadfast', 'Steadfast'), ('pathao', 'Pathao'), ('sundarban', 'Sundarban'),
        ('ecourier', 'eCourier'), ('redx', 'RedX'), ('sa_paribahan', 'SA Paribahan'),
        ('other', 'Other'), ('any', 'Any Courier'),
    ], default='any')
    based_on = models.CharField(max_length=20, choices=BASED_ON_CHOICES, default='weight')
    min_value = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Min weight/price for this rule')
    max_value = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='0 = unlimited')
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    free_above = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='0 = no free shipping threshold')
    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Shipping Rule'
        verbose_name_plural = 'Shipping Rules'

    def __str__(self):
        return f'{self.name} — ৳{self.cost}'


# ─── Feature 6: Refund Request ───

class RefundRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='refund_requests')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='refund_requests')
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, null=True, blank=True, related_name='refund_requests')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_refunds')
    processed_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Refund Request'
        verbose_name_plural = 'Refund Requests'
        ordering = ['-created']

    def __str__(self):
        return f'Refund #{self.id} — Order #{self.order.id} — ৳{self.amount} — {self.get_status_display()}'


class ManualPaymentMethod(models.Model):
    name = models.CharField(max_length=50, verbose_name='Method Name')
    account_number = models.CharField(max_length=50, verbose_name='Account Number')
    account_type = models.CharField(max_length=50, blank=True, default='Personal', verbose_name='Account Type')
    instructions = models.TextField(blank=True, help_text='Additional payment instructions shown to customer')
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0, help_text='Display order (lowest first)')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Manual Payment Method'
        verbose_name_plural = 'Manual Payment Methods'
        ordering = ['order', 'name']

    def __str__(self):
        return f'{self.name} - {self.account_number}'


class PosOrder(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('bkash', 'bKash'),
        ('nagad', 'Nagad'),
        ('rocket', 'Rocket'),
        ('card', 'Card'),
        ('other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('completed', 'Completed'),
        ('refunded', 'Refunded'),
        ('cancelled', 'Cancelled'),
    ]
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name='pos_orders', db_index=True)
    invoice_number = models.CharField(max_length=50, unique=True)
    customer_name = models.CharField(max_length=200, blank=True)
    customer_phone = models.CharField(max_length=50, blank=True)
    customer_email = models.EmailField(blank=True, verbose_name='Customer Email')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash')
    payment_status = models.CharField(max_length=20, choices=[('unpaid', 'Unpaid'), ('paid', 'Paid'), ('refunded', 'Refunded')], default='paid')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed')
    notes = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'POS Order'
        verbose_name_plural = 'POS Orders'
        ordering = ['-created']

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            today = timezone.now().strftime('%Y%m%d')
            last_today = PosOrder.objects.filter(invoice_number__startswith=f'POS-{today}').count()
            self.invoice_number = f'POS-{today}-{last_today + 1:04d}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f'POS #{self.invoice_number}'


# ─── Messaging System ───

class Conversation(models.Model):
    participants = models.ManyToManyField(User, related_name='conversations')
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, null=True, blank=True)
    product = models.ForeignKey('Product', on_delete=models.SET_NULL, null=True, blank=True)
    subject = models.CharField(max_length=200, blank=True)
    is_broadcast = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated']
        verbose_name = 'Conversation'
        verbose_name_plural = 'Conversations'

    def __str__(self):
        return self.subject or f'Conversation #{self.id}'


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    content = models.TextField()
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created']
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'

    def __str__(self):
        return f'Message by {self.sender.username} at {self.created}'


class ConversationReadStatus(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='read_statuses')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    last_read = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('conversation', 'user')
        verbose_name = 'Read Status'
        verbose_name_plural = 'Read Statuses'

    def __str__(self):
        return f'{self.user.username} in conversation #{self.conversation_id}'


# ─── Product Q&A (public) ───

class ProductQA(models.Model):
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='qa_pairs')
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    question = models.TextField()
    answer = models.TextField(blank=True)
    answered_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='qa_answers')
    created = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Product Q&A'
        verbose_name_plural = 'Product Q&A'
        ordering = ['-created']

    def __str__(self):
        return f'Q: {self.question[:50]}'


# ─── POS Order Items ───

class PosOrderItem(models.Model):
    pos_order = models.ForeignKey(PosOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    product_name = models.CharField(max_length=300)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    @property
    def total_price(self):
        return (self.price - self.discount) * self.quantity

    class Meta:
        verbose_name = 'POS Order Item'
        verbose_name_plural = 'POS Order Items'

    def __str__(self):
        return f'{self.quantity} x {self.product_name}'


# ─── Feature: Support Tickets ───

class SupportTicket(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name='tickets')
    subject = models.CharField(max_length=200)
    description = models.TextField()
    image = models.ImageField(upload_to='tickets/%Y/%m/%d/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Support Ticket'
        verbose_name_plural = 'Support Tickets'
        ordering = ['-created']

    def __str__(self):
        return f'[{self.get_status_display()}] {self.subject}'

    @property
    def last_reply(self):
        return self.replies.order_by('-created').first()


class TicketReply(models.Model):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='replies')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.TextField()
    attachment = models.FileField(upload_to='ticket_replies/%Y/%m/%d/', null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ticket Reply'
        verbose_name_plural = 'Ticket Replies'
        ordering = ['created']

    def __str__(self):
        return f'Reply by {self.user.username} on {self.ticket.subject}'


# ─── Medicine System ───

def _medicine_sku():
    from django.db.models import Max
    max_sku = MedicineProduct.objects.filter(sku__startswith='MED-').aggregate(Max('sku'))['sku__max']
    if max_sku:
        num = int(max_sku.split('-')[1]) + 1
    else:
        num = 1
    return f'MED-{num:05d}'


class MedicineProduct(models.Model):
    brand_name = models.CharField(max_length=200, verbose_name='Brand Name')
    generic_name = models.CharField(max_length=300, blank=True, verbose_name='Generic Name', help_text='Active ingredient / generic name')
    strength = models.CharField(max_length=100, blank=True, verbose_name='Strength', help_text='e.g. "500 mg"')
    dosage_form = models.CharField(max_length=100, blank=True, verbose_name='Dosage Form', help_text='e.g. "Tablet", "Syrup"')
    manufacturer = models.CharField(max_length=300, blank=True, verbose_name='Manufacturer', help_text='Pharmaceutical company name')
    pack_size = models.CharField(max_length=200, blank=True, verbose_name='Pack Size', help_text='e.g. 30s pack, 5s pack, 1s pack')
    sku = models.CharField(max_length=50, unique=True, blank=True, verbose_name='SKU')
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text='Unit / piece price')
    pack_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text='Pack / box price (total)')
    stock = models.IntegerField(default=0)
    image = models.ImageField(upload_to='medicine_products/', blank=True, null=True)
    description = models.TextField(blank=True)
    is_approved = models.BooleanField(default=False, verbose_name='Approved', help_text='Approved products appear in Medicine POS')
    requested_by = models.ForeignKey(Partner, on_delete=models.SET_NULL, null=True, blank=True, related_name='medicine_requests', verbose_name='Requested By')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Medicine Product'
        verbose_name_plural = 'Medicine Products'
        ordering = ['-created']

    def save(self, *args, **kwargs):
        if not self.sku:
            self.sku = _medicine_sku()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.brand_name} {self.strength} {self.dosage_form}'.strip()


class MedicinePosOrder(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('bkash', 'bKash'),
        ('nagad', 'Nagad'),
        ('rocket', 'Rocket'),
        ('card', 'Card'),
        ('other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('completed', 'Completed'),
        ('refunded', 'Refunded'),
        ('cancelled', 'Cancelled'),
    ]
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name='medicine_pos_orders', db_index=True)
    invoice_number = models.CharField(max_length=50, unique=True)
    customer_name = models.CharField(max_length=200, blank=True)
    customer_phone = models.CharField(max_length=50, blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash')
    payment_status = models.CharField(max_length=20, choices=[('unpaid', 'Unpaid'), ('paid', 'Paid'), ('refunded', 'Refunded')], default='paid')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed')
    notes = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Medicine POS Order'
        verbose_name_plural = 'Medicine POS Orders'
        ordering = ['-created']

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            today = timezone.now().strftime('%Y%m%d')
            last_today = MedicinePosOrder.objects.filter(invoice_number__startswith=f'MPOS-{today}').count()
            self.invoice_number = f'MPOS-{today}-{last_today + 1:04d}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f'MPOS #{self.invoice_number}'


class MedicinePosOrderItem(models.Model):
    pos_order = models.ForeignKey(MedicinePosOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(MedicineProduct, on_delete=models.SET_NULL, null=True, blank=True)
    product_name = models.CharField(max_length=300)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    @property
    def total_price(self):
        return (self.price - self.discount) * self.quantity

    class Meta:
        verbose_name = 'Medicine POS Order Item'
        verbose_name_plural = 'Medicine POS Order Items'

    def __str__(self):
        return f'{self.quantity} x {self.product_name}'


class MedicineSubscription(models.Model):
    STATUS_CHOICES = [
        ('inactive', 'Inactive'),
        ('trial', 'Trial'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]
    partner = models.OneToOneField(Partner, on_delete=models.CASCADE, related_name='medicine_subscription')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='inactive')
    trial_started_at = models.DateTimeField(null=True, blank=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    last_payment_at = models.DateTimeField(null=True, blank=True)
    next_payment_due = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Medicine Subscription'
        verbose_name_plural = 'Medicine Subscriptions'

    def __str__(self):
        return f'{self.partner.name} — {self.get_status_display()}'

    @property
    def is_locked(self):
        return self.status in ('inactive', 'expired', 'cancelled')

    @property
    def is_accessible(self):
        return self.status in ('trial', 'active')

    @property
    def trial_days_remaining(self):
        if self.status == 'trial' and self.trial_ends_at:
            return max(0, (self.trial_ends_at - timezone.now()).days)
        if self.status == 'active' and self.current_period_end:
            return max(0, (self.current_period_end - timezone.now()).days)
        return 0


class SubscriptionPackage(models.Model):
    name = models.CharField(max_length=100, help_text='e.g. "Monthly", "Quarterly", "Yearly"')
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text='Price in BDT')
    duration_days = models.IntegerField(help_text='Number of days the subscription lasts')
    is_active = models.BooleanField(default=True, help_text='Show this package to partners')
    sort_order = models.IntegerField(default=0, help_text='Display order')
    description = models.TextField(blank=True, help_text='Short description/features of this package')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Subscription Package'
        verbose_name_plural = 'Subscription Packages'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return f'{self.name} — ৳{int(self.price)} / {self.duration_days}d'


class WalletRechargeInstruction(models.Model):
    title = models.CharField(max_length=200, help_text='e.g. "bKash Payment", "Bank Transfer"')
    instruction_text = models.TextField(help_text='Full payment instructions shown to partners')
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0, help_text='Display order')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Wallet Recharge Instruction'
        verbose_name_plural = 'Wallet Recharge Instructions'
        ordering = ['order', 'title']

    def __str__(self):
        return self.title


# ─── Medicine Inventory ───

class MedicineInventory(models.Model):
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name='medicine_inventory')
    product = models.ForeignKey(MedicineProduct, on_delete=models.CASCADE, related_name='inventory_entries')
    stock = models.IntegerField(default=0, help_text='Current stock count for this partner')
    low_stock_threshold = models.IntegerField(default=5, help_text='Alert when stock falls below this number')
    is_active = models.BooleanField(default=True, help_text='Show this product in Medicine POS')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('partner', 'product')
        verbose_name = 'Medicine Inventory'
        verbose_name_plural = 'Medicine Inventories'
        ordering = ['product__brand_name']

    def __str__(self):
        return f'{self.partner.name} — {self.product.brand_name} ({self.stock})'

    @property
    def is_low_stock(self):
        return self.stock <= self.low_stock_threshold


class MedicineInventoryLog(models.Model):
    ADJUSTMENT_TYPES = [
        ('sale', 'Sale'),
        ('refund', 'Refund'),
        ('stock_in', 'Stock In'),
        ('stock_out', 'Stock Out'),
        ('adjustment', 'Manual Adjustment'),
        ('initial', 'Initial Stock'),
    ]
    inventory = models.ForeignKey(MedicineInventory, on_delete=models.CASCADE, related_name='logs')
    adjustment_type = models.CharField(max_length=20, choices=ADJUSTMENT_TYPES)
    quantity = models.IntegerField(help_text='Positive for in, negative for out')
    balance_after = models.IntegerField(help_text='Stock count after this change')
    reason = models.CharField(max_length=300, blank=True)
    reference = models.CharField(max_length=200, blank=True, help_text='e.g. order number')
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Medicine Inventory Log'
        verbose_name_plural = 'Medicine Inventory Logs'
        ordering = ['-created']

    def __str__(self):
        return f'{self.adjustment_type}: {self.quantity:+d} — {self.inventory}'


# ─── Medicine Company Order Draft ───

class MedicineOrderDraft(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('exported', 'Exported'),
        ('sent', 'Sent'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled'),
    ]
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name='medicine_order_drafts')
    product = models.ForeignKey(MedicineProduct, on_delete=models.CASCADE, related_name='medicine_order_drafts')
    order_date = models.DateField(db_index=True, help_text='Date this order applies to (stock-out date)')
    quantity = models.PositiveIntegerField(default=0, help_text='Manual ORDER quantity entered by the shopkeeper. 0 = not entered.')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    exported_at = models.DateTimeField(null=True, blank=True)
    exported_filename = models.CharField(max_length=255, blank=True)
    note = models.CharField(max_length=300, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Medicine Order Draft'
        verbose_name_plural = 'Medicine Order Drafts'
        unique_together = ('partner', 'product', 'order_date')
        ordering = ['-order_date', '-updated']

    @property
    def manufacturer(self):
        return self.product.manufacturer if self.product else ''

    def __str__(self):
        return f'{self.partner.name} — {self.product} — {self.order_date} ({self.quantity})'


class DiscountCardContent(models.Model):
    title = models.CharField(max_length=300, blank=True)
    content = models.TextField(blank=True, help_text='Main body text/HTML for the discount card page')
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Discount Card Content'
        verbose_name_plural = 'Discount Card Contents'
        ordering = ['sort_order', '-created']

    def __str__(self):
        return self.title or f'Content #{self.pk}'


class HomepageSettings(models.Model):
    """Singleton — one page to control every homepage / page section: on-off, edit text, links."""

    # ─── Homepage: B2B / B2C buttons ───
    show_b2b_b2c_buttons = models.BooleanField(default=True, verbose_name='Show B2B / B2C buttons')
    b2b_icon = models.CharField(max_length=60, default='fas fa-building', verbose_name='B2B icon (Font Awesome class)')
    b2b_button_text = models.CharField(max_length=60, default='B2B Product', verbose_name='B2B button text')
    b2b_url = models.CharField(max_length=300, default='/shop_grid/', blank=True, verbose_name='B2B button link', help_text='e.g. /shop_grid/ or a full URL')
    b2c_icon = models.CharField(max_length=60, default='fas fa-shopping-cart', verbose_name='B2C icon (Font Awesome class)')
    b2c_button_text = models.CharField(max_length=60, default='B2C Product', verbose_name='B2C button text')
    b2c_url = models.CharField(max_length=300, default='/shop_grid/', blank=True, verbose_name='B2C button link', help_text='e.g. /shop_grid/ or a full URL')

    # ─── Homepage: tabbed products (All Over Available Product) ───
    show_tabbed_products = models.BooleanField(default=True, verbose_name='Show "All Over Available Product" section')
    products_heading = models.CharField(max_length=200, default='All Over Available Product', verbose_name='Section heading')
    tab_all_label = models.CharField(max_length=40, default='All', verbose_name='"All" tab label')
    tab_new_label = models.CharField(max_length=40, default='New', verbose_name='"New" tab label')
    tab_discounted_label = models.CharField(max_length=40, default='Discounted', verbose_name='"Discounted" tab label')
    tab_hot_label = models.CharField(max_length=40, default='Hot Item', verbose_name='"Hot" tab label')

    # ─── Homepage: random product sidebar ───
    show_random_product = models.BooleanField(default=True, verbose_name='Show "Random Product List" sidebars')
    random_list_heading = models.CharField(max_length=200, default='Random Product List', verbose_name='Sidebar heading')

    # ─── Homepage: partner products ───
    show_partner_products = models.BooleanField(default=True, verbose_name='Show "All Partner Product" section')
    partner_products_heading = models.CharField(max_length=200, default='All Partner Product', verbose_name='Section heading')
    show_partner_hot_products = models.BooleanField(default=True, verbose_name='Show "All Partner Hot Products" section')
    partner_hot_products_heading = models.CharField(max_length=200, default='All Partner Hot Products', verbose_name='Section heading')

    # ─── Homepage: blog marquee + video ───
    show_blog_marquee = models.BooleanField(default=True, verbose_name='Show "New Arrival Product" blog marquee')
    new_arrival_heading = models.CharField(max_length=200, default='New Arrival Product', verbose_name='Blog marquee heading')
    show_videos = models.BooleanField(default=True, verbose_name='Show "Our Videos" section')
    videos_heading = models.CharField(max_length=200, default='Our Videos', verbose_name='Video section heading')
    home_video_embed = models.CharField(max_length=500, default='https://www.youtube.com/embed/q73R90FJZdQ?rel=0', blank=True, verbose_name='YouTube video embed URL', help_text='Embed URL from "Share -> Embed" (https://www.youtube.com/embed/...)')

    # ─── Homepage: promo cards + brands ───
    show_promo_cards = models.BooleanField(default=True, verbose_name='Show promo cards (Buy 2 items, Daily Sales, ...)')
    show_brand_marquee = models.BooleanField(default=True, verbose_name='Show "Our Partner Brands" marquee')
    brands_heading = models.CharField(max_length=200, default='Our Partner Brands', verbose_name='Brands marquee heading')

    # ─── Homepage: HomeBanner strip ───
    show_home_banner = models.BooleanField(default=False, verbose_name='Show home banner strip', help_text='Render the "Home Banner" images as a full-width strip above the promo cards. Manage images under Home Banner.')

    # ─── Shop grid ───
    shop_heading = models.CharField(max_length=200, default='ALL PRODUCTS', verbose_name='Shop page title')
    show_shop_labels = models.BooleanField(default=True, verbose_name='Show the Labels filter list (All / New / Hot / Discounted)')
    shop_label_all = models.CharField(max_length=40, default='All', verbose_name='Labels list "All" caption')
    shop_label_new = models.CharField(max_length=40, default='New', verbose_name='Labels list "New" caption')
    shop_label_hot = models.CharField(max_length=40, default='Hot', verbose_name='Labels list "Hot" caption')
    shop_label_discounted = models.CharField(max_length=40, default='Discounted', verbose_name='Labels list "Discounted" caption')

    # ─── Product detail page ───
    show_share_buttons = models.BooleanField(default=True, verbose_name='Show social share buttons on product page')
    shipping_delivery_title = models.CharField(max_length=100, default='Delivery', verbose_name='Delivery card title')
    shipping_delivery_text = models.CharField(max_length=300, default='Nationwide delivery across Bangladesh. Delivered within 3-7 business days.', verbose_name='Delivery card text')
    shipping_return_title = models.CharField(max_length=100, default='Return Policy', verbose_name='Return card title')
    shipping_return_text = models.CharField(max_length=300, default='Return within 7 days for a full refund or exchange. Unused, original packaging.', verbose_name='Return card text')
    shipping_payment_title = models.CharField(max_length=100, default='Payment', verbose_name='Payment card title')
    shipping_payment_text = models.CharField(max_length=300, default='Cash on Delivery (COD) available for all orders within Bangladesh.', verbose_name='Payment card text')

    # ─── Other page headings ───
    contact_heading = models.CharField(max_length=200, default='Contact Us', verbose_name='Contact page title')
    discount_heading = models.CharField(max_length=200, default='Discount Card', verbose_name='Discount Card page title')

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Homepage & Page Settings'
        verbose_name_plural = 'Homepage & Page Settings'

    def __str__(self):
        return 'Homepage & Page Settings'

    @classmethod
    def load(cls):
        obj = cls._default_manager.first()
        if obj:
            return obj
        return cls()

    def save(self, *args, **kwargs):
        if self.pk is None and HomepageSettings.objects.exists():
            existing = HomepageSettings.objects.first()
            for field in self._meta.fields:
                if field.name in ('id', 'created', 'updated'):
                    continue
                setattr(existing, field.name, getattr(self, field.name))
            existing.save()
            return
        super().save(*args, **kwargs)


class PromoCard(models.Model):
    title = models.CharField(max_length=100, verbose_name='Card title')
    description = models.CharField(max_length=200, blank=True, verbose_name='Card subtitle')
    icon = models.CharField(max_length=60, default='fa fa-gift', verbose_name='Icon (Font Awesome class)')
    link = models.CharField(max_length=300, blank=True, verbose_name='Link (optional)', help_text='e.g. /shop_grid/ or a full URL')
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']
        verbose_name = 'Promo Card'
        verbose_name_plural = 'Promo Cards'

    def __str__(self):
        return self.title


class BrandLogo(models.Model):
    name = models.CharField(max_length=100, verbose_name='Brand name')
    image = models.ImageField(upload_to='brands/', verbose_name='Brand logo image')
    link = models.CharField(max_length=300, blank=True, verbose_name='Link (optional)', help_text='e.g. /shop_grid/ or a full URL')
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']
        verbose_name = 'Brand Logo'
        verbose_name_plural = 'Brand Logos'

    def __str__(self):
        return self.name
