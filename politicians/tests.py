from django.template.loader import get_template
from django.test import SimpleTestCase


class SharedTemplateArchitectureTests(SimpleTestCase):
    def test_public_templates_compile(self):
        template_names = [
            "base.html",
            "404.html",
            "500.html",
            "politicians/politicians_list.html",
            "politicians/politician_detail.html",
            "politicians/senators_list.html",
            "politicians/senator_detail.html",
        ]

        for template_name in template_names:
            with self.subTest(template_name=template_name):
                get_template(template_name)

    def test_base_template_uses_shared_layout_components(self):
        template = get_template("base.html")
        source = template.template.source

        self.assertIn('{% include "includes/header.html" %}', source)
        self.assertIn('{% include "includes/footer.html" %}', source)
