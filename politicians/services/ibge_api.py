from typing import Any

import requests


IBGE_MUNICIPALITIES_URL = (
    "https://servicodados.ibge.gov.br/api/v1/localidades/"
    "estados/35/municipios"
)
REQUEST_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "SaoPauloPoliticalExplorer/1.0",
}


class IBGEAPIError(Exception):
    """Raised when official municipality data cannot be retrieved."""


def normalize_municipalities(
    payload: Any,
) -> list[dict[str, Any]]:
    """Normalize the official IBGE municipality response."""

    if not isinstance(payload, list):
        raise IBGEAPIError(
            "The IBGE returned an unexpected municipality response."
        )

    municipalities = []

    for record in payload:
        if not isinstance(record, dict):
            continue

        immediate_region = record.get(
            "regiao-imediata",
            {},
        ) or {}
        intermediate_region = immediate_region.get(
            "regiao-intermediaria",
            {},
        ) or {}
        municipality_id = record.get("id")
        name = str(record.get("nome", "")).strip()

        if not municipality_id or not name:
            continue

        municipalities.append(
            {
                "ibge_code": int(municipality_id),
                "name": name,
                "state": "SP",
                "immediate_region": immediate_region.get(
                    "nome",
                    "",
                ),
                "intermediate_region": intermediate_region.get(
                    "nome",
                    "",
                ),
            }
        )

    municipalities.sort(
        key=lambda municipality: municipality["name"].casefold()
    )

    return municipalities


def get_sao_paulo_municipalities() -> list[dict[str, Any]]:
    """Download all official São Paulo municipalities from IBGE."""

    try:
        response = requests.get(
            IBGE_MUNICIPALITIES_URL,
            headers=REQUEST_HEADERS,
            timeout=(3.05, 30),
        )
        response.raise_for_status()
        payload = response.json()

    except (requests.RequestException, ValueError) as error:
        raise IBGEAPIError(
            "IBGE municipality data is temporarily unavailable."
        ) from error

    return normalize_municipalities(payload)
