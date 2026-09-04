from django.urls import path

from apps.campagnes import views

app_name = "campagnes"

urlpatterns = [
    path("", views.campagnes, name="liste"),
    path("distributions/", views.distributions, name="distributions"),
    path("distributions/nouvelle/", views.enregistrer, name="enregistrer"),
    path(
        "distributions/<int:identifiant>/annuler/",
        views.annuler,
        name="annuler",
    ),
]
