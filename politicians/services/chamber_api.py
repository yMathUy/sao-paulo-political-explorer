from typing import Any

import requests
from django.core.cache import cache


CHAMBER_API_URL = "https://dadosabertos.camara.leg.br/api/v2"

DEPUTIES_CACHE_KEY = "sao_paulo_federal_deputies"
DEPUTIES_CACHE_TIMEOUT = 60 * 30


class ChamberAPIError(Exception):
    """Raised when data cannot be retrieved from the Chamber API."""


def get_sao_paulo_deputies() -> list[dict[str, Any]]:
    """
    Return federal deputies elected by São Paulo.

    Data is cached for 30 minutes to avoid unnecessary requests
    to the external API.
    """

    cached_deputies = cache.get(DEPUTIES_CACHE_KEY)

    if cached_deputies is not None:
        return cached_deputies

    try:
        response = requests.get(
            f"{CHAMBER_API_URL}/deputados",
            params={
                "siglaUf": "SP",
                "itens": 100,
                "ordem": "ASC",
                "ordenarPor": "nome",
            },
            headers={
                "Accept": "application/json",
                "User-Agent": "SaoPauloPoliticalExplorer/1.0",
            },
            timeout=(3.05, 15),
        )

        response.raise_for_status()
        data = response.json()

    except (requests.RequestException, ValueError) as error:
        raise ChamberAPIError(
            "The Chamber of Deputies data is temporarily unavailable."
        ) from error

    deputies = data.get("dados", [])

    cache.set(
        DEPUTIES_CACHE_KEY,
        deputies,
        DEPUTIES_CACHE_TIMEOUT,
    )

    return deputies

def get_deputy_by_id(deputy_id: int) -> dict[str, Any]:
    cache_key = f"federal_deputy_{deputy_id}"

    cached_deputy = cache.get(cache_key)

    if cached_deputy is not None:
        return cached_deputy

    try:
        response = requests.get(
            f"{CHAMBER_API_URL}/deputados/{deputy_id}",
            headers={
                "Accept": "application/json",
                "User-Agent": "SaoPauloPoliticalExplorer/1.0",
            },
            timeout=(3.05, 15),
        )

        response.raise_for_status()
        data = response.json()

    except (requests.RequestException, ValueError) as error:
        raise ChamberAPIError(
            "The politician profile is temporarily unavailable."
        ) from error

    deputy = data.get("dados", {})

    cache.set(cache_key, deputy, DEPUTIES_CACHE_TIMEOUT)

    return deputy