"""Modèle Utilisateur de l'ONG E.F.F.M."""
from django.contrib.auth.models import AbstractUser
from django.db import models

from core.models import Horodate
from core.roles import Role


class Utilisateur(AbstractUser, Horodate):
    """Utilisateur interne. Un utilisateur porte exactement un rôle (§5)."""

    role = models.CharField(
        "rôle", max_length=32, choices=Role.choices, default=Role.VISITEUR
    )
    telephone = models.CharField("téléphone", max_length=32, blank=True)
    creation_ia_autorisee = models.BooleanField(
        "création assistée par IA autorisée",
        default=True,
        help_text=(
            "Décoché, l'utilisateur peut interroger l'assistant mais ne peut "
            "plus lui demander de préparer des créations (§12)."
        ),
    )

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"

    def __str__(self):
        nom_complet = f"{self.first_name} {self.last_name}".strip()
        return f"{nom_complet or self.username} ({self.get_role_display()})"

    def save(self, *args, **kwargs):
        # Un superutilisateur Django est nécessairement super administrateur
        # métier : sans cela, il aurait tous les droits techniques et aucun
        # droit applicatif.
        if self.is_superuser:
            self.role = Role.SUPER_ADMIN
        super().save(*args, **kwargs)
