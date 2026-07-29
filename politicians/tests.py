from unittest.mock import Mock, patch

import requests
from django.core.cache import cache
from django.template.loader import get_template
from django.test import SimpleTestCase

from .services.senate_api import (
    SenateAPIError,
    get_current_sao_paulo_senators,
    get_senator_by_id,
    parse_senator_authorships,
    parse_senator_committees,
    parse_senator_mandates,
    parse_senator_votes,
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


class SenateAuthorshipParserTests(SimpleTestCase):
    def test_parses_primary_and_shared_authorships(self):
        payload = {
            "MateriasAutoriaParlamentar": {
                "Parlamentar": {
                    "Autorias": {
                        "Autoria": [
                            {
                                "Materia": {
                                    "Codigo": "10",
                                    "DescricaoIdentificacao": "PL 1/2026",
                                    "Sigla": "PL",
                                    "Numero": "1",
                                    "Ano": "2026",
                                    "Ementa": "Primary matter",
                                    "Data": "2026-02-01",
                                },
                                "IndicadorAutorPrincipal": "Sim",
                            },
                            {
                                "Materia": {
                                    "Codigo": "11",
                                    "DescricaoIdentificacao": "PEC 2/2026",
                                    "Sigla": "PEC",
                                    "Numero": "2",
                                    "Ano": "2026",
                                    "Ementa": "Shared matter",
                                    "Data": "2026-01-01",
                                },
                                "IndicadorAutorPrincipal": "Não",
                            },
                        ]
                    }
                }
            }
        }

        authorships = parse_senator_authorships(payload)

        self.assertEqual(authorships[0]["description"], "PL 1/2026")
        self.assertTrue(authorships[0]["is_primary_author"])
        self.assertFalse(authorships[1]["is_primary_author"])


class SenateVoteParserTests(SimpleTestCase):
    def test_vote_year_comes_from_session_date(self):
        payload = {
            "VotacaoParlamentar": {
                "Parlamentar": {
                    "Votacoes": {
                        "Votacao": {
                            "SessaoPlenaria": {
                                "CodigoSessao": "100",
                                "NumeroSessao": "20",
                                "DataSessao": "2026-04-10",
                            },
                            "Materia": {
                                "Codigo": "200",
                                "DescricaoIdentificacao": "PL 1/2024",
                                "Ano": "2024",
                                "Ementa": "Matter summary",
                            },
                            "CodigoSessaoVotacao": "300",
                            "DescricaoVotacao": "Nominal vote",
                            "DescricaoResultado": "Approved",
                            "SiglaDescricaoVoto": "Sim",
                        }
                    }
                }
            }
        }

        votes = parse_senator_votes(payload)

        self.assertEqual(votes[0]["session_year"], "2026")
        self.assertEqual(votes[0]["matter"], "PL 1/2024")
        self.assertEqual(votes[0]["vote"], "Sim")
        self.assertEqual(votes[0]["result"], "Approved")


class SenateAPIIntegrationTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @staticmethod
    def response_with(payload):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = payload
        return response

    @patch("politicians.services.senate_api.requests.get")
    def test_current_senators_filters_sao_paulo_and_forces_https(
        self,
        mocked_get,
    ):
        mocked_get.return_value = self.response_with(
            {
                "ListaParlamentarEmExercicio": {
                    "Parlamentares": {
                        "Parlamentar": [
                            {
                                "IdentificacaoParlamentar": {
                                    "CodigoParlamentar": "1",
                                    "NomeParlamentar": "São Paulo Senator",
                                    "UrlFotoParlamentar": "http://example.test/photo.jpg",
                                },
                                "Mandato": {"UfParlamentar": "SP"},
                            },
                            {
                                "IdentificacaoParlamentar": {
                                    "CodigoParlamentar": "2",
                                    "NomeParlamentar": "Other Senator",
                                },
                                "Mandato": {"UfParlamentar": "RJ"},
                            },
                        ]
                    }
                }
            }
        )

        senators = get_current_sao_paulo_senators()

        self.assertEqual(len(senators), 1)
        self.assertEqual(senators[0]["id"], "1")
        self.assertEqual(
            senators[0]["photo_url"],
            "https://example.test/photo.jpg",
        )

    @patch("politicians.services.senate_api.requests.get")
    def test_current_senators_uses_cached_response(self, mocked_get):
        mocked_get.return_value = self.response_with(
            {
                "ListaParlamentarEmExercicio": {
                    "Parlamentares": {
                        "Parlamentar": {
                            "IdentificacaoParlamentar": {
                                "CodigoParlamentar": "1",
                                "NomeParlamentar": "Cached Senator",
                            },
                            "Mandato": {"UfParlamentar": "SP"},
                        }
                    }
                }
            }
        )

        first_result = get_current_sao_paulo_senators()
        second_result = get_current_sao_paulo_senators()

        self.assertEqual(first_result, second_result)
        mocked_get.assert_called_once()

    @patch("politicians.services.senate_api.requests.get")
    def test_senator_detail_accepts_missing_optional_fields(
        self,
        mocked_get,
    ):
        mocked_get.return_value = self.response_with(
            {
                "DetalheParlamentar": {
                    "Parlamentar": {
                        "IdentificacaoParlamentar": {
                            "CodigoParlamentar": "10",
                            "NomeParlamentar": "Minimal Senator",
                        }
                    }
                }
            }
        )

        senator = get_senator_by_id(10)

        self.assertEqual(senator["name"], "Minimal Senator")
        self.assertEqual(senator["photo_url"], "")
        self.assertEqual(senator["email"], "")

    @patch("politicians.services.senate_api.requests.get")
    def test_api_network_error_becomes_domain_error(self, mocked_get):
        mocked_get.side_effect = requests.Timeout("timeout")

        with self.assertRaises(SenateAPIError):
            get_senator_by_id(99)
