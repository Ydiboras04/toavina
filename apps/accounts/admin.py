"""Administration du modèle Utilisateur."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.accounts.models import Utilisateur


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (
            "Informations E.F.F.M.",
            {"fields": ("role", "telephone", "creation_ia_autorisee")},
        ),
    )
    list_display = UserAdmin.list_display + (
        "role",
        "telephone",
        "creation_ia_autorisee",
    )
