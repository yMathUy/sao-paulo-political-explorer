from django.http import Http404
from django.shortcuts import render
from django.core.paginator import Paginator
from datetime import date

from .services.chamber_api import (
    ChamberAPIError,
    get_deputy_by_id,
    get_sao_paulo_deputies,
    get_deputy_expenses,
    summarize_expenses,
)

def politicians_list(request):
    searched_name = request.GET.get("name", "").strip()
    selected_party = request.GET.get("party", "").strip().upper()

    error_message = None

    try:
        all_deputies = get_sao_paulo_deputies()
    except ChamberAPIError as error:
        all_deputies = []
        error_message = str(error)

    parties = sorted(
        {
            deputy.get("siglaPartido")
            for deputy in all_deputies
            if deputy.get("siglaPartido")
        }
    )

    filtered_deputies = all_deputies

    if searched_name:
        normalized_name = searched_name.casefold()

        filtered_deputies = [
            deputy
            for deputy in filtered_deputies
            if normalized_name in deputy.get("nome", "").casefold()
        ]

    if selected_party:
        filtered_deputies = [
            deputy
            for deputy in filtered_deputies
            if deputy.get("siglaPartido", "").upper() == selected_party
        ]

    paginator = Paginator(filtered_deputies, 12)

    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "parties": parties,
        "searched_name": searched_name,
        "selected_party": selected_party,
        "results_count": len(filtered_deputies),
        "error_message": error_message,
    }

    return render(
        request,
        "politicians/politicians_list.html",
        context,
    )

def politician_detail(request, deputy_id):
    try:
        deputy = get_deputy_by_id(deputy_id)
    except ChamberAPIError as error:
        context = {
            "error_message": str(error),
        }

        return render(
            request,
            "politicians/politician_detail.html",
            context,
            status=503,
        )

    if not deputy:
        raise Http404("Politician not found.")

    current_year = date.today().year
    expense_error = None

    expense_summary = {
        "formatted_total": "Not available",
        "records_count": 0,
        "top_categories": [],
    }

    try:
        expenses = get_deputy_expenses(
            deputy_id=deputy_id,
            year=current_year,
        )

        expense_summary = summarize_expenses(expenses)

    except ChamberAPIError as error:
        expense_error = str(error)

    context = {
        "deputy": deputy,
        "current_year": current_year,
        "expense_summary": expense_summary,
        "expense_error": expense_error,
    }

    return render(
        request,
        "politicians/politician_detail.html",
        context,
    )