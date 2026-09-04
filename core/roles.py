"""Rôles de l'ONG et leur libellé (§5 du cahier des charges)."""
from django.db import models


class Role(models.TextChoices):
    SUPER_ADMIN = "super_admin", "Super administrateur"
    PRESIDENT = "president", "Président"
    COORDINATEUR = "coordinateur", "Coordinateur"
    COMPTABLE = "comptable", "Comptable"
    RESPONSABLE_PROJET = "responsable_projet", "Responsable de projet"
    VOLONTAIRE = "volontaire", "Volontaire"
    VISITEUR = "visiteur", "Visiteur"
