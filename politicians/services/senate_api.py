from typing import Any

import requests
from django.core.cache import cache


SENATE_API_URL = "https://legis.senado.leg.br/dadosabertos"

SENATORS_CACHE_KEY = "current_sao_paulo_senators"
SENATORS_CACHE_TIMEOUT = 60 * 30

REQUEST_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "SaoPauloPoliticalExplorer/1.0",
}


class SenateAPIError(Exception):
    """Raised when data cannot be retrieved from the Senate API."""


def force_https(url: str | None) -> str:
    """Convert official HTTP links to HTTPS."""

    if not url:
        return ""

    return url.replace("http://", "https://", 1)


def as_list(value: Any) -> list[Any]:
    """Normalize an API field that may be an object or a list."""

    if isinstance(value, list):
        return value

    if isinstance(value, dict):
        return [value]

    return []


def parse_senator_mandates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert the Senate mandate response into template-ready records."""

    raw_mandates = (
        payload
        .get("MandatoParlamentar", {})
        .get("Parlamentar", {})
        .get("Mandatos", {})
        .get("Mandato", [])
    )

    mandates = []

    for raw_mandate in as_list(raw_mandates):
        first_term = raw_mandate.get(
            "PrimeiraLegislaturaDoMandato",
            {},
        )
        second_term = raw_mandate.get(
            "SegundaLegislaturaDoMandato",
            {},
        )
        raw_parties = (
            raw_mandate
            .get("Partidos", {})
            .get("Partido", [])
        )
        parties = as_list(raw_parties)
        latest_party = parties[-1] if parties else {}

        substitutes = [
            {
                "id": substitute.get("CodigoParlamentar", ""),
                "name": substitute.get(
                    "NomeParlamentar",
                    "Name not available",
                ),
                "position": substitute.get(
                    "DescricaoParticipacao",
                    "Substitute",
                ),
            }
            for substitute in as_list(
                raw_mandate
                .get("Suplentes", {})
                .get("Suplente", [])
            )
        ]

        mandates.append(
            {
                "id": raw_mandate.get("CodigoMandato", ""),
                "state": raw_mandate.get("UfParlamentar", ""),
                "participation": raw_mandate.get(
                    "DescricaoParticipacao",
                    "",
                ),
                "start_date": first_term.get("DataInicio", ""),
                "end_date": (
                    second_term.get("DataFim")
                    or first_term.get("DataFim")
                    or ""
                ),
                "first_legislature": first_term.get(
                    "NumeroLegislatura",
                    "",
                ),
                "second_legislature": second_term.get(
                    "NumeroLegislatura",
                    "",
                ),
                "party": latest_party.get("Sigla", ""),
                "party_name": latest_party.get("Nome", ""),
                "substitutes": substitutes,
            }
        )

    mandates.sort(
        key=lambda mandate: mandate.get("start_date", ""),
        reverse=True,
    )

    return mandates


def parse_senator_committees(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Convert Senate committee memberships into normalized records."""

    raw_committees = (
        payload
        .get("MembroComissaoParlamentar", {})
        .get("Parlamentar", {})
        .get("MembroComissoes", {})
        .get("Comissao", [])
    )
    committees = []

    for raw_committee in as_list(raw_committees):
        identification = raw_committee.get(
            "IdentificacaoComissao",
            {},
        )
        end_date = raw_committee.get("DataFim", "")

        committees.append(
            {
                "id": identification.get("CodigoComissao", ""),
                "abbreviation": identification.get(
                    "SiglaComissao",
                    "",
                ),
                "name": identification.get(
                    "NomeComissao",
                    "Name not available",
                ),
                "house": identification.get(
                    "SiglaCasaComissao",
                    "",
                ),
                "participation": raw_committee.get(
                    "DescricaoParticipacao",
                    "",
                ),
                "start_date": raw_committee.get("DataInicio", ""),
                "end_date": end_date,
                "is_current": not bool(end_date),
            }
        )

    committees.sort(
        key=lambda committee: (
            not committee["is_current"],
            committee.get("name", "").casefold(),
            committee.get("start_date", ""),
        )
    )

    return committees


def get_current_sao_paulo_senators() -> list[dict[str, Any]]:
    """Return senators currently serving for São Paulo."""

    cached_senators = cache.get(SENATORS_CACHE_KEY)

    if cached_senators is not None:
        return cached_senators

    try:
        response = requests.get(
            f"{SENATE_API_URL}/senador/lista/atual",
            headers=REQUEST_HEADERS,
            timeout=(3.05, 20),
        )

        response.raise_for_status()
        payload = response.json()

    except (requests.RequestException, ValueError) as error:
        raise SenateAPIError(
            "Senate data is temporarily unavailable."
        ) from error

    parliamentarians = (
        payload
        .get("ListaParlamentarEmExercicio", {})
        .get("Parlamentares", {})
        .get("Parlamentar", [])
    )

    if isinstance(parliamentarians, dict):
        parliamentarians = [parliamentarians]

    senators = []

    for parliamentarian in parliamentarians:
        identification = parliamentarian.get(
            "IdentificacaoParlamentar",
            {},
        )

        mandate = parliamentarian.get("Mandato", {})

        state = (
            mandate.get("UfParlamentar")
            or identification.get("UfParlamentar")
            or ""
        )

        if state.upper() != "SP":
            continue

        senator_id = identification.get("CodigoParlamentar")

        if not senator_id:
            continue

        senators.append(
            {
                "id": senator_id,
                "name": identification.get(
                    "NomeParlamentar",
                    "Name not available",
                ),
                "civil_name": identification.get(
                    "NomeCompletoParlamentar",
                    "",
                ),
                "party": identification.get(
                    "SiglaPartidoParlamentar",
                    "",
                ),
                "state": state.upper(),
                "photo_url": force_https(
                    identification.get("UrlFotoParlamentar")
                ),
                "profile_url": force_https(
                    identification.get("UrlPaginaParlamentar")
                ),
                "email": identification.get(
                    "EmailParlamentar",
                    "",
                ),
            }
        )

    senators.sort(
        key=lambda senator: senator.get("name", "").casefold()
    )

    cache.set(
        SENATORS_CACHE_KEY,
        senators,
        SENATORS_CACHE_TIMEOUT,
    )

    return senators


def get_senator_by_id(senator_id: int) -> dict[str, Any]:
    """Return detailed information about a senator."""

    cache_key = f"senator_{senator_id}"

    cached_senator = cache.get(cache_key)

    if cached_senator is not None:
        return cached_senator

    try:
        response = requests.get(
            f"{SENATE_API_URL}/senador/{senator_id}",
            headers=REQUEST_HEADERS,
            timeout=(3.05, 20),
        )

        response.raise_for_status()
        payload = response.json()

    except (requests.RequestException, ValueError) as error:
        raise SenateAPIError(
            "The senator profile is temporarily unavailable."
        ) from error

    details = payload.get("DetalheParlamentar", {})
    parliamentarian = details.get("Parlamentar", details)

    identification = parliamentarian.get(
        "IdentificacaoParlamentar",
        {},
    )

    basic_data = parliamentarian.get(
        "DadosBasicosParlamentar",
        {},
    )

    mandate = (
        parliamentarian.get("MandatoAtual")
        or parliamentarian.get("Mandato")
        or {}
    )

    senator = {
        "id": (
            identification.get("CodigoParlamentar")
            or senator_id
        ),
        "name": identification.get(
            "NomeParlamentar",
            "Name not available",
        ),
        "civil_name": identification.get(
            "NomeCompletoParlamentar",
            "",
        ),
        "party": identification.get(
            "SiglaPartidoParlamentar",
            "",
        ),
        "state": (
            mandate.get("UfParlamentar")
            or identification.get("UfParlamentar")
            or ""
        ).upper(),
        "photo_url": force_https(
            identification.get("UrlFotoParlamentar")
        ),
        "profile_url": force_https(
            identification.get("UrlPaginaParlamentar")
        ),
        "email": identification.get(
            "EmailParlamentar",
            "",
        ),
        "gender": basic_data.get("SexoParlamentar", ""),
        "birth_date": basic_data.get("DataNascimento", ""),
        "birthplace": (
            basic_data.get("Naturalidade")
            or basic_data.get("MunicipioNaturalidade")
            or ""
        ),
        "office": identification.get("FormaTratamento", ""),
    }

    cache.set(
        cache_key,
        senator,
        SENATORS_CACHE_TIMEOUT,
    )

    return senator


def get_senator_mandates(senator_id: int) -> list[dict[str, Any]]:
    """Return current and previous mandates with their substitutes."""

    cache_key = f"senator_{senator_id}_mandates"
    cached_mandates = cache.get(cache_key)

    if cached_mandates is not None:
        return cached_mandates

    try:
        response = requests.get(
            f"{SENATE_API_URL}/senador/{senator_id}/mandatos",
            headers=REQUEST_HEADERS,
            timeout=(3.05, 20),
        )
        response.raise_for_status()
        payload = response.json()

    except (requests.RequestException, ValueError) as error:
        raise SenateAPIError(
            "Senator mandate data is temporarily unavailable."
        ) from error

    mandates = parse_senator_mandates(payload)
    cache.set(cache_key, mandates, SENATORS_CACHE_TIMEOUT)

    return mandates


def get_senator_committees(senator_id: int) -> list[dict[str, Any]]:
    """Return current and previous committee memberships."""

    cache_key = f"senator_{senator_id}_committees"
    cached_committees = cache.get(cache_key)

    if cached_committees is not None:
        return cached_committees

    try:
        response = requests.get(
            f"{SENATE_API_URL}/senador/{senator_id}/comissoes",
            headers=REQUEST_HEADERS,
            timeout=(3.05, 20),
        )
        response.raise_for_status()
        payload = response.json()

    except (requests.RequestException, ValueError) as error:
        raise SenateAPIError(
            "Senator committee data is temporarily unavailable."
        ) from error

    committees = parse_senator_committees(payload)
    cache.set(cache_key, committees, SENATORS_CACHE_TIMEOUT)

    return committees
