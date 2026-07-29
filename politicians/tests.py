from django.template.loader import get_template
from django.test import SimpleTestCase

from .services.senate_api import (
    parse_senator_committees,
    parse_senator_mandates,
)


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


class SenateMandateParserTests(SimpleTestCase):
    def test_parses_single_mandate_and_substitute_objects(self):
        payload = {
            "MandatoParlamentar": {
                "Parlamentar": {
                    "Mandatos": {
                        "Mandato": {
                            "CodigoMandato": "617",
                            "UfParlamentar": "SP",
                            "DescricaoParticipacao": "Titular",
                            "PrimeiraLegislaturaDoMandato": {
                                "NumeroLegislatura": "57",
                                "DataInicio": "2023-02-01",
                                "DataFim": "2027-01-31",
                            },
                            "SegundaLegislaturaDoMandato": {
                                "NumeroLegislatura": "58",
                                "DataFim": "2031-01-31",
                            },
                            "Suplentes": {
                                "Suplente": {
                                    "CodigoParlamentar": "6385",
                                    "NomeParlamentar": "Test Substitute",
                                    "DescricaoParticipacao": "1st Substitute",
                                }
                            },
                            "Partidos": {
                                "Partido": {
                                    "Sigla": "PL",
                                    "Nome": "Partido Liberal",
                                }
                            },
                        }
                    }
                }
            }
        }

        mandates = parse_senator_mandates(payload)

        self.assertEqual(len(mandates), 1)
        self.assertEqual(mandates[0]["start_date"], "2023-02-01")
        self.assertEqual(mandates[0]["end_date"], "2031-01-31")
        self.assertEqual(mandates[0]["party"], "PL")
        self.assertEqual(
            mandates[0]["substitutes"][0]["name"],
            "Test Substitute",
        )


class SenateCommitteeParserTests(SimpleTestCase):
    def test_current_memberships_are_sorted_before_previous_ones(self):
        payload = {
            "MembroComissaoParlamentar": {
                "Parlamentar": {
                    "MembroComissoes": {
                        "Comissao": [
                            {
                                "IdentificacaoComissao": {
                                    "CodigoComissao": "1",
                                    "SiglaComissao": "OLD",
                                    "NomeComissao": "Previous Committee",
                                    "SiglaCasaComissao": "SF",
                                },
                                "DescricaoParticipacao": "Titular",
                                "DataInicio": "2023-01-01",
                                "DataFim": "2024-01-01",
                            },
                            {
                                "IdentificacaoComissao": {
                                    "CodigoComissao": "2",
                                    "SiglaComissao": "CUR",
                                    "NomeComissao": "Current Committee",
                                    "SiglaCasaComissao": "SF",
                                },
                                "DescricaoParticipacao": "Suplente",
                                "DataInicio": "2025-01-01",
                            },
                        ]
                    }
                }
            }
        }

        committees = parse_senator_committees(payload)

        self.assertEqual(committees[0]["abbreviation"], "CUR")
        self.assertTrue(committees[0]["is_current"])
        self.assertFalse(committees[1]["is_current"])
