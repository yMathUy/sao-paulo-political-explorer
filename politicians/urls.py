from django.urls import path

from . import views


app_name = "politicians"

urlpatterns = [
    path("", views.politicians_list, name="list"),
    path(
        "politicians/<int:deputy_id>/",
        views.politician_detail,
        name="detail",
    ),
]