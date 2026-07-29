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

        mandate = parliamentarian.get(
            "Mandato",
            {},
        )

        state = (
            mandate.get("UfParlamentar")
            or identification.get("UfParlamentar")
            or ""
        )

        if state.upper() != "SP":
            continue

        senators.append(
            {
                "id": identification.get("CodigoParlamentar"),
                "name": identification.get("NomeParlamentar"),
                "civil_name": identification.get("NomeCompletoParlamentar"),
                "party": identification.get("SiglaPartidoParlamentar"),
                "state": state,
                "photo_url": identification.get("UrlFotoParlamentar"),
                "profile_url": identification.get(
                    "UrlPaginaParlamentar"
                ),
                "email": identification.get("EmailParlamentar"),
            }
        )

    cache.set(
        SENATORS_CACHE_KEY,
        senators,
        SENATORS_CACHE_TIMEOUT,
    )

    return senators