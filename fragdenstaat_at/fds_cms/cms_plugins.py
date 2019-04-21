from django.utils.translation import ugettext_lazy as _

from cms.plugin_base import CMSPluginBase
from cms.plugin_pool import plugin_pool

from froide.helper.utils import get_redirect_url

from froide.foirequest.models import FoiRequest
from froide.publicbody.models import PublicBody

from .models import (
    PageAnnotationCMSPlugin, DocumentPagesCMSPlugin, DocumentEmbedCMSPlugin,
    PrimaryLinkCMSPlugin, FoiRequestListCMSPlugin
)



@plugin_pool.register_plugin
class ContainerPlugin(CMSPluginBase):
    module = _("Structure")
    name = _("Container")
    render_template = "cms/plugins/container.html"
    allow_children = True


@plugin_pool.register_plugin
class ContainerGreyPlugin(CMSPluginBase):
    module = _("Structure")
    name = _("Container Grey")
    render_template = "cms/plugins/container_grey.html"
    allow_children = True


@plugin_pool.register_plugin
class RowPlugin(CMSPluginBase):
    module = _("Structure")
    name = _("Row")
    render_template = "cms/plugins/row.html"
    allow_children = True


class ColumnPlugin(CMSPluginBase):
    module = _("Structure")
    allow_children = True


# Generate Column Plugin classes and register them
COLUMNS = [
    (3, _('Three')),
    (4, _('Four')),
    (6, _('Six')),
    (8, _('Eight')),
    (9, _('Nine')),
    (12, _('Twelve')),
]

for col_count, col_name in COLUMNS:
    plugin_pool.register_plugin(
        type(
            'Column%sPlugin' % col_count,
            (ColumnPlugin,),
            {
                'name': _("Column " + str(col_name)),
                'render_template': "cms/plugins/col_%d.html" % col_count,
            }
        )
    )


@plugin_pool.register_plugin
class ColumnTeaserPlugin(CMSPluginBase):
    module = _("Structure")
    allow_children = True
    name = _('Column Teaser Three')
    render_template = 'cms/plugins/col_teaser.html'


@plugin_pool.register_plugin
class SubMenuPlugin(CMSPluginBase):
    module = _("Menu")
    name = _("Sub Menu")
    render_template = "cms/plugins/submenu.html"


@plugin_pool.register_plugin
class HomepageHeroPlugin(CMSPluginBase):
    module = _("Homepage")
    name = _("Homepage Hero")
    render_template = "snippets/homepage_hero.html"

    def render(self, context, instance, placeholder):
        context = super(HomepageHeroPlugin, self)\
            .render(context, instance, placeholder)
        context.update({
            'foicount': FoiRequest.objects.get_send_foi_requests().count(),
            'pbcount': PublicBody.objects.get_list().count()
        })
        return context


@plugin_pool.register_plugin
class HomepageHowPlugin(CMSPluginBase):
    module = _("Homepage")
    name = _("Homepage How")
    render_template = "snippets/homepage_how.html"







@plugin_pool.register_plugin
class PageAnnotationPlugin(CMSPluginBase):
    model = PageAnnotationCMSPlugin
    module = _("Document")
    name = _("Page Annotation")
    text_enabled = True
    render_template = "document/cms_plugins/page_annotation.html"
    raw_id_fields = ('page_annotation',)

    def render(self, context, instance, placeholder):
        context = super(PageAnnotationPlugin, self)\
            .render(context, instance, placeholder)

        context['object'] = instance.page_annotation

        return context


@plugin_pool.register_plugin
class DocumentPagesPlugin(CMSPluginBase):
    model = DocumentPagesCMSPlugin
    module = _("Document")
    name = _("Document pages")
    text_enabled = True
    render_template = "document/cms_plugins/document_pages.html"
    raw_id_fields = ('doc',)

    def render(self, context, instance, placeholder):
        context = super(DocumentPagesPlugin, self)\
            .render(context, instance, placeholder)

        context['object'] = instance
        context['pages'] = instance.get_pages()

        return context


@plugin_pool.register_plugin
class DocumentEmbedPlugin(CMSPluginBase):
    model = DocumentEmbedCMSPlugin
    module = _("Document")
    name = _("Document embed")
    text_enabled = True
    render_template = "document/cms_plugins/document_embed.html"
    raw_id_fields = ('doc',)

    def render(self, context, instance, placeholder):
        context = super(DocumentEmbedPlugin, self)\
            .render(context, instance, placeholder)

        context['object'] = instance.doc
        context['instance'] = instance
        return context


@plugin_pool.register_plugin
class PrimaryLinkPlugin(CMSPluginBase):
    module = _("Elements")
    name = _('Primary Link')
    default_template = "cms/plugins/primarylink/default.html"
    model = PrimaryLinkCMSPlugin

    def get_render_template(self, context, instance, placeholder):
        if instance.template:
            return instance.template
        return self.default_template

    def render(self, context, instance, placeholder):
        context = super(PrimaryLinkPlugin, self)\
            .render(context, instance, placeholder)
        context['object'] = instance
        return context


@plugin_pool.register_plugin
class ContinueLinkPlugin(CMSPluginBase):
    module = _("Elements")
    name = _('Continue Link')
    text_enabled = True
    cache = False
    render_template = "cms/plugins/continue_link.html"

    def render(self, context, instance, placeholder):
        context = super(ContinueLinkPlugin, self)\
            .render(context, instance, placeholder)
        request = context['request']
        context['title'] = request.GET.get('next_title', 'Zurück zu Ihrer Anfrage')
        next_url = get_redirect_url(request)
        context['next_url'] = next_url
        return context


@plugin_pool.register_plugin
class DropdownBannerPlugin(CMSPluginBase):
    module = _("Ads")
    name = _('Dropdown Banner')
    allow_children = True
    cache = True
    render_template = "cms/plugins/dropdown_banner.html"


@plugin_pool.register_plugin
class FoiRequestListPlugin(CMSPluginBase):
    """
    Plugin for including the latest entries filtered
    """
    model = FoiRequestListCMSPlugin
    name = _('Latest FOI requests')
    default_template = 'foirequest/cms_plugins/list.html'
    filter_horizontal = ['tags']
    text_enabled = True
    raw_id_fields = ['user', 'jurisdiction', 'category', 'project',
                     'classification', 'publicbody']

    def get_render_template(self, context, instance, placeholder):
        if instance.template:
            return instance.template
        return self.default_template

    def render(self, context, instance, placeholder):
        """
        Update the context with plugin's data
        """
        foirequests = FoiRequest.published.all()

        filters = {}

        tag_list = instance.tags.all().values_list('id', flat=True)
        if tag_list:
            filters['tags__in'] = tag_list

        if instance.user is not None:
            filters['user'] = instance.user

        if instance.jurisdiction_id:
            filters['jurisdiction_id'] = instance.jurisdiction_id

        if instance.category_id:
            filters['category_id'] = instance.category_id

        if instance.classification_id:
            filters['classification_id'] = instance.classification_id

        if instance.publicbody_id:
            filters['public_body_id'] = instance.publicbody_id

        if instance.status:
            filters['status'] = instance.status
        if instance.resolution:
            filters['resolution'] = instance.resolution

        foirequests = foirequests.filter(**filters)

        if instance.offset:
            foirequests = foirequests[instance.offset:]
        if instance.number_of_entries:
            foirequests = foirequests[:instance.number_of_entries]

        context = super(FoiRequestListPlugin, self).render(
            context, instance, placeholder)
        context['object_list'] = foirequests
        return context
