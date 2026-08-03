from django.urls import path

from . import views


app_name = "politicians"

urlpatterns = [
    path(
        "",
        views.politicians_list,
        name="list",
    ),
    path(
        "politicians/<int:deputy_id>/",
        views.politician_detail,
        name="detail",
    ),
    path(
        "senators/",
        views.senators_list,
        name="senators",
    ),
    path(
        "senators/<int:senator_id>/",
        views.senator_detail,
        name="senator_detail",
    ),
    path(
        "governor/",
        views.state_executive_list,
        name="state_executive",
    ),
    path(
        "governor/<slug:slug>/",
        views.state_officeholder_detail,
        name="state_officeholder_detail",
    ),
    path(
        "municipalities/",
        views.municipalities_list,
        name="municipalities",
    ),
    path(
        "municipalities/<slug:slug>/",
        views.municipality_detail,
        name="municipality_detail",
    ),
]
