from django import template
from mjml import mjml2html

register = template.Library()


class MjmlNode(template.Node):
    def __init__(self, nodelist: template.NodeList) -> None:
        self.nodelist = nodelist

    def render(self, context: template.Context) -> str:
        return mjml2html(self.nodelist.render(context))


@register.tag(name="mjml")
def mjml(parser: template.base.Parser, token: template.base.Token) -> MjmlNode:
    nodelist = parser.parse(("endmjml",))
    parser.delete_first_token()
    return MjmlNode(nodelist)
