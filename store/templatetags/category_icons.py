"""Lightweight presentation helper: map a category slug to a Font Awesome icon.

Icons are purely decorative and are never stored on the Category model. If an
admin sets ``Category.icon`` it takes precedence (handled in the template).
"""
from django import template

register = template.Library()

# Ordered keyword -> icon. First match wins, so more specific keywords go first.
_ICON_RULES = (
    ('womens', 'fa fa-female'),
    ('mens', 'fa fa-male'),
    ('electronic-device', 'fa fa-mobile'),
    ('electronic-accessor', 'fa fa-plug'),
    ('electronic', 'fa fa-microchip'),
    ('mobile', 'fa fa-mobile'),
    ('phone', 'fa fa-mobile'),
    ('laptop', 'fa fa-laptop'),
    ('computer', 'fa fa-desktop'),
    ('camera', 'fa fa-camera'),
    ('audio', 'fa fa-headphones'),
    ('gaming', 'fa fa-gamepad'),
    ('game', 'fa fa-gamepad'),
    ('watch', 'fa fa-clock-o'),
    ('jewellery', 'fa fa-diamond'),
    ('jewelry', 'fa fa-diamond'),
    ('bag', 'fa fa-shopping-bag'),
    ('fashion', 'fa fa-female'),
    ('clothing', 'fa fa-female'),
    ('wear', 'fa fa-female'),
    ('shoe', 'fa fa-shopping-bag'),
    ('beauty', 'fa fa-magic'),
    ('health', 'fa fa-heartbeat'),
    ('care', 'fa fa-heartbeat'),
    ('baby', 'fa fa-child'),
    ('mother', 'fa fa-child'),
    ('kid', 'fa fa-child'),
    ('toy', 'fa fa-child'),
    ('home', 'fa fa-home'),
    ('kitchen', 'fa fa-cutlery'),
    ('furniture', 'fa fa-home'),
    ('living', 'fa fa-home'),
    ('appliance', 'fa fa-desktop'),
    ('tv', 'fa fa-desktop'),
    ('grocery', 'fa fa-shopping-basket'),
    ('groceries', 'fa fa-shopping-basket'),
    ('food', 'fa fa-cutlery'),
    ('pet', 'fa fa-paw'),
    ('sport', 'fa fa-futbol-o'),
    ('outdoor', 'fa fa-futbol-o'),
    ('fitness', 'fa fa-futbol-o'),
    ('automotive', 'fa fa-car'),
    ('motorbike', 'fa fa-motorcycle'),
    ('vehicle', 'fa fa-car'),
    ('car', 'fa fa-car'),
    ('book', 'fa fa-book'),
    ('stationery', 'fa fa-pencil'),
    ('craft', 'fa fa-pencil'),
    ('health-beauty', 'fa fa-heartbeat'),
)

DEFAULT_ICON = 'fa fa-tag'


@register.filter
def category_icon(slug):
    slug = (slug or '').lower()
    for needle, icon in _ICON_RULES:
        if needle in slug:
            return icon
    return DEFAULT_ICON
