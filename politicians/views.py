from django.shortcuts import render

from .services.chamber_api import get_sao_paulo_deputies


def politicians_list(request):
    deputies = get_sao_paulo_deputies()

    context = {
        "deputies": deputies,
    }

    return render(
        request,
        "politicians/politicians_list.html",
        context,
    )