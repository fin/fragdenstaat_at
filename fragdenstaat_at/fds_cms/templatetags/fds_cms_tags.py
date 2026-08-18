from django import template


register = template.Library()


@register.filter
def is_campaign(obj, campaign):
    return obj.reference.startswith(campaign)



@register.filter
def thumbnail_dims(instance, default_width=768):
    if instance.width and instance.height:
        return "%dx%d" % (instance.width, instance.height)
    elif instance.height:
        return "0x%d" % instance.height
    elif instance.width:
        return "%dx0" % instance.width
    return "%dx0" % default_width


def get_soft_root(page):
    """Nearest ancestor marked as a soft root, else the tree root.

    Ported from DE. Used by the CMS search apphook to scope a search to the
    section it is attached to.
    """
    if page.soft_root:
        return page
    soft_root = (
        page.get_ancestor_pages()
        .filter(pagecontent_set__soft_root=True)
        .reverse()
        .first()
    )
    if soft_root:
        return soft_root
    return page.get_root()
