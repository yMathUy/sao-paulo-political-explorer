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