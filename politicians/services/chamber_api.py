from typing import Any

import requests
from django.core.cache import cache
from collections import defaultdict
from decimal import Decimal, InvalidOperation


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

EXPENSES_CACHE_TIMEOUT = 60 * 60


def get_deputy_expenses(
    deputy_id: int,
    year: int,
) -> list[dict[str, Any]]:
    """
    Retrieve all CEAP expenses for a deputy in a specific year.

    Results are cached for one hour.
    """

    cache_key = f"federal_deputy_{deputy_id}_expenses_{year}"

    cached_expenses = cache.get(cache_key)

    if cached_expenses is not None:
        return cached_expenses

    expenses: list[dict[str, Any]] = []
    page = 1

    try:
        while True:
            response = requests.get(
                f"{CHAMBER_API_URL}/deputados/{deputy_id}/despesas",
                params={
                    "ano": year,
                    "pagina": page,
                    "itens": 100,
                },
                headers={
                    "Accept": "application/json",
                    "User-Agent": "SaoPauloPoliticalExplorer/1.0",
                },
                timeout=(3.05, 15),
            )

            response.raise_for_status()
            data = response.json()

            page_expenses = data.get("dados", [])
            expenses.extend(page_expenses)

            if len(page_expenses) < 100:
                break

            page += 1

            # Prevent an unexpected infinite pagination loop.
            if page > 50:
                break

    except (requests.RequestException, ValueError) as error:
        raise ChamberAPIError(
            "Expense data is temporarily unavailable."
        ) from error

    cache.set(
        cache_key,
        expenses,
        EXPENSES_CACHE_TIMEOUT,
    )

    return expenses


def format_brl(value: Decimal) -> str:
    """Format a decimal value using Brazilian currency notation."""

    formatted_value = f"{value:,.2f}"

    formatted_value = (
        formatted_value
        .replace(",", "TEMP")
        .replace(".", ",")
        .replace("TEMP", ".")
    )

    return f"R$ {formatted_value}"


def summarize_expenses(
    expenses: list[dict[str, Any]],
) -> dict[str, Any]:
    """Calculate the total and the largest expense categories."""

    total = Decimal("0")
    totals_by_category: defaultdict[str, Decimal] = defaultdict(Decimal)

    for expense in expenses:
        try:
            amount = Decimal(
                str(expense.get("valorLiquido") or 0)
            )
        except InvalidOperation:
            continue

        category = expense.get("tipoDespesa") or "Other expenses"

        total += amount
        totals_by_category[category] += amount

    categories = [
        {
            "name": category,
            "amount": amount,
            "formatted_amount": format_brl(amount),
        }
        for category, amount in sorted(
            totals_by_category.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    ]

    return {
        "total": total,
        "formatted_total": format_brl(total),
        "records_count": len(expenses),
        "top_categories": categories[:6],
    }