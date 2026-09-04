"""Projets et actions de l'ONG."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.geographie.models import Region
from core.models import Archivable, Horodate


class TypeAction(Horodate):
    """Nature de l'action menée.

    Alimente le référentiel des douze types prévus par le cahier des charges :
    distribution alimentaire, distribution de vêtements, kurban, forage d'eau,
    construction de mosquées, construction d'écoles, bourses d'étude,
    parrainage d'orphelins, urgences humanitaires, santé, éducation,
    développement rural.
    """

    libelle = models.CharField("libellé", max_length=100, unique=True)
    description = models.TextField("description", blank=True)

    class Meta:
        verbose_name = "type d'action"
        verbose_name_plural = "types d'action"
        ordering = ["libelle"]

    def __str__(self):
        return self.libelle


class EtatProjet(models.TextChoices):
    PLANIFIE = "planifie", "Planifié"
    EN_COURS = "en_cours", "En cours"
    TERMINE = "termine", "Terminé"
    SUSPENDU = "suspendu", "Suspendu"


class Projet(Horodate, Archivable):
    """Projet humanitaire ou social de l'ONG."""

    code = models.CharField("code", max_length=32, unique=True)
    titre = models.CharField("titre", max_length=200)
    description = models.TextField("description", blank=True)

    budget_prevu = models.DecimalField(
        "budget prévu",
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    budget_consomme = models.DecimalField(
        "budget consommé",
        max_digits=14,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )

    date_debut = models.DateField("date de début")
    date_fin = models.DateField("date de fin", null=True, blank=True)
    etat = models.CharField(
        "état",
        max_length=20,
        choices=EtatProjet.choices,
        default=EtatProjet.PLANIFIE,
    )

    type_action = models.ForeignKey(
        TypeAction,
        on_delete=models.PROTECT,
        related_name="projets",
        verbose_name="type d'action",
    )
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="projets_diriges",
        verbose_name="responsable",
    )
    region = models.ForeignKey(
        Region,
        on_delete=models.PROTECT,
        related_name="projets",
        verbose_name="région",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "projet"
        verbose_name_plural = "projets"
        ordering = ["-date_debut", "code"]

    def __str__(self):
        return f"{self.code} — {self.titre}"

    def clean(self):
        """Valide les invariantes du modèle.

        Vraie de tout projet quel que soit le chemin d'écriture emprunté,
        cette règle vit ici plutôt qu'en services : `full_clean()` l'applique
        sur tous ces chemins, l'interface d'administration Django comprise,
        qui ne passe pas par `apps.projets.services`.
        """
        if self.date_fin and self.date_debut and self.date_fin < self.date_debut:
            raise ValidationError(
                "La date de fin ne peut pas précéder la date de début."
            )

    @property
    def budget_restant(self):
        """Part du budget prévu encore disponible."""
        return self.budget_prevu - self.budget_consomme
