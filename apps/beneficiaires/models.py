"""Fiche bénéficiaire (§4.1 du cahier des charges)."""
from django.db import models

from apps.geographie.models import Village
from core.models import Archivable, Horodate


class Sexe(models.TextChoices):
    MASCULIN = "M", "Masculin"
    FEMININ = "F", "Féminin"


class SituationFamiliale(models.TextChoices):
    CELIBATAIRE = "celibataire", "Célibataire"
    MARIE = "marie", "Marié(e)"
    VEUF = "veuf", "Veuf(ve)"
    DIVORCE = "divorce", "Divorcé(e)"


class StatutBeneficiaire(models.TextChoices):
    ACTIF = "actif", "Actif"
    INACTIF = "inactif", "Inactif"
    DECEDE = "decede", "Décédé(e)"
    DEMENAGE = "demenage", "Déménagé(e)"


class Beneficiaire(Horodate, Archivable):
    nom = models.CharField("nom", max_length=100)
    prenom = models.CharField("prénom", max_length=100)
    sexe = models.CharField("sexe", max_length=1, choices=Sexe.choices)
    date_naissance = models.DateField("date de naissance", null=True, blank=True)

    telephone = models.CharField("téléphone", max_length=32, blank=True)
    adresse = models.CharField("adresse", max_length=255, blank=True)
    village = models.ForeignKey(
        Village,
        on_delete=models.PROTECT,
        related_name="beneficiaires",
        verbose_name="village",
    )

    profession = models.CharField("profession", max_length=100, blank=True)
    nombre_enfants = models.PositiveSmallIntegerField("nombre d'enfants", default=0)
    situation_familiale = models.CharField(
        "situation familiale",
        max_length=20,
        choices=SituationFamiliale.choices,
        blank=True,
    )
    revenu = models.DecimalField(
        "revenu mensuel", max_digits=12, decimal_places=2, null=True, blank=True
    )

    photo = models.ImageField(
        "photo", upload_to="beneficiaires/photos/", blank=True
    )
    numero_cin = models.CharField(
        "numéro CIN", max_length=32, blank=True, null=True, db_index=True
    )
    numero_passeport = models.CharField(
        "numéro de passeport", max_length=32, blank=True
    )

    statut = models.CharField(
        "statut",
        max_length=20,
        choices=StatutBeneficiaire.choices,
        default=StatutBeneficiaire.ACTIF,
    )

    class Meta:
        verbose_name = "bénéficiaire"
        verbose_name_plural = "bénéficiaires"
        ordering = ["nom", "prenom"]
        indexes = [
            models.Index(fields=["nom", "prenom"], name="beneficiaire_nom_prenom"),
        ]
        constraints = [
            # Unicité partielle : le CIN identifie de façon fiable, mais tous
            # les bénéficiaires n'en possèdent pas (§8.1).
            models.UniqueConstraint(
                fields=["numero_cin"],
                condition=models.Q(numero_cin__isnull=False),
                name="cin_unique_si_renseigne",
            ),
        ]

    def __str__(self):
        return f"{self.nom} {self.prenom}"
