"""Category-tree helpers: builds a nested, cached category tree shared by the
mega menu, sidebar and category pages using only two queries."""
from django.core.cache import cache
from django.db.models import Count, Q
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from store.models import Category, Product

CACHE_KEY = 'category_tree_v3'
CACHE_TTL = 600


def _product_base_q():
    return Product.objects.filter(available=True, trashed=False, is_published=True).filter(
        Q(partner__isnull=True) | Q(partner__show_products=True))


def build():
    cats = Category.objects.filter(is_active=True).order_by('sort_order', 'name')
    nested = {c.id: {
        'id': c.id, 'name': c.name, 'slug': c.slug, 'parent_id': c.parent_id,
        'icon': c.icon or '',
        'image_url': c.image.url if c.image else '',
        'path': [], 'url': '', 'product_count': 0, 'children': [],
    } for c in cats}

    counts = dict(_product_base_q().exclude(category_id__isnull=True)
                  .values_list('category_id').annotate(n=Count('id')))
    for node in nested.values():
        node['product_count'] = counts.get(node['id'], 0)

    # compute root->this path & url for every node
    for node in nested.values():
        path = []
        cur = node
        seen = set()
        while cur is not None and cur['id'] not in seen:
            seen.add(cur['id'])
            path.insert(0, cur)
            cur = nested.get(cur['parent_id'])
        node['path'] = [n['slug'] for n in path]
        node['url'] = '/category/' + '/'.join(node['path']) + '/'

    roots = []
    for node in nested.values():
        parent = nested.get(node['parent_id'])
        (parent['children'] if parent else roots).append(node)
    return roots


def get_tree():
    roots = cache.get(CACHE_KEY)
    if roots is None:
        roots = build()
        cache.set(CACHE_KEY, roots, CACHE_TTL)
    return roots


def invalidate():
    cache.delete(CACHE_KEY)


def count_descendants(category_id, tree=None):
    """Total published products across a category and all its descendants."""
    tree = tree if tree is not None else get_tree()
    by_id = {}
    for root in tree:
        _collect(root, by_id)
    meta = by_id.get(category_id)
    if not meta:
        return 0
    total = 0
    stack = [meta]
    while stack:
        node = stack.pop()
        total += node['product_count']
        stack.extend(node['children'])
    return total


def _collect(node, by_id):
    by_id[node['id']] = node
    for child in node['children']:
        _collect(child, by_id)


def descendant_ids(category_id, tree=None):
    """Set of category ids under ``category_id`` (including itself)."""
    tree = tree if tree is not None else get_tree()
    by_id = {}
    for root in tree:
        _collect(root, by_id)
    start = by_id.get(category_id)
    if start is None:
        return {category_id}
    ids = []
    stack = [start]
    while stack:
        node = stack.pop()
        ids.append(node['id'])
        stack.extend(node['children'])
    return set(ids)


def resolve_path(path):
    """Resolve a list of URL slug segments to a Category or None."""
    tree = get_tree()
    by_id = {}
    for root in tree:
        _collect(root, by_id)
    by_slug = {}
    for node in by_id.values():
        by_slug.setdefault(node['slug'], []).append(node)

    if not path:
        return None
    first = path[0]
    candidates = [n for n in by_slug.get(first, []) if n['parent_id'] is None]
    node = None
    for segment in path:
        if node is None:
            node = next((n for n in by_slug.get(segment, []) if n['parent_id'] is None), None)
        else:
            node = next((n for n in node['children'] if n['slug'] == segment), None)
        if node is None:
            return None
    return node


@receiver([post_save, post_delete], sender=Category)
def _category_changed(sender, **kwargs):
    invalidate()