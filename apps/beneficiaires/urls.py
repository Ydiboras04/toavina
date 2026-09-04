from django.urls import path

from apps.beneficiaires import views

app_name = "beneficiaires"

urlpatterns = [
    path("", views.liste, name="liste"),
    path("nouveau/", views.creer, name="creer"),
    path("<int:identifiant>/", views.detail, name="detail"),
    path("<int:identifiant>/modifier/", views.modifier, name="modifier"),
]
