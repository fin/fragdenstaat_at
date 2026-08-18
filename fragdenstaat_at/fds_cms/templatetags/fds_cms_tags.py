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
