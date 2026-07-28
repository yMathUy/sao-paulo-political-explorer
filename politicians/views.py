from django.core.paginator import Paginator
from django.shortcuts import render

from .services.chamber_api import (
    ChamberAPIError,
    get_sao_paulo_deputies,
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