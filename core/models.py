"""Classes abstraites partagées par tous les modules métier."""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class Horodate(models.Model):
    """Trace la création et la dernière modification d'un enregistrement."""

    date_creation = models.DateTimeField("date de création", auto_now_add=True)
    date_modification = models.DateTimeField("date de modification", auto_now=True)

    class Meta:
        abstract = True


class GestionnaireActifs(models.Manager):
    """Ne retourne que les enregistrements non archivés."""

    def get_queryset(self):
        return super().get_queryset().filter(archive=False)


class Archivable(models.Model):
    """Remplace la suppression physique par un archivage.

    La spécification (§8 du MPD) interdit la suppression des données
    historisées : une distribution effacée ferait disparaître la trace d'une
    aide réellement remise.

    Déclarer `objects` (filtrant) avant `tous` ne pose pas le piège qu'on
    pourrait craindre pour les accès internes de Django (traversée de clé
    étrangère, suppression en cascade, etc.). En l'absence de
    `Meta.base_manager_name` explicite, Django n'utilise jamais un
    gestionnaire déclaré comme gestionnaire de base par défaut : il crée à la
    place un `Manager()` non filtrant dédié. C'est ce filet qui protège,
    par exemple, `distribution.beneficiaire` après l'archivage du
    bénéficiaire — vérifié empiriquement, y compris sur les modèles de ce
    projet qui n'ont jamais rien déclaré à ce sujet (`Beneficiaire`,
    `Projet`).

    Un `Meta.base_manager_name` déclaré ici, sur cette classe abstraite, ne se
    propagerait de toute façon à aucun modèle concret : la résolution de
    Django (`Options.base_manager`) ne consulte que le tout premier parent de
    la MRO possédant un `_meta`, qui n'est jamais `Archivable` dans ce
    projet — toujours un autre abstrait (`Horodate`, `Distribution`,
    `Campagne`) listé avant elle dans les bases de la classe concrète.

    Un modèle qui veut rendre ce comportement explicite plutôt que de
    compter sur le filet par défaut de Django doit donc déclarer
    `base_manager_name = "tous"` lui-même, dans son propre `Meta` — c'est ce
    que font `CampagneAide` et `DistributionAide`.
    """

    archive = models.BooleanField("archivé", default=False)

    objects = GestionnaireActifs()
    tous = models.Manager()

    class Meta:
        abstract = True


class SaisiPar(models.Model):
    """Conserve qui a enregistré la donnée.

    Deux usages. D'abord la traçabilité, exigée par l'association SAISIE_PAR
    du modèle conceptuel : savoir qui a enregistré quelle aide, et quand.
    Ensuite le contrôle d'accès : c'est ce champ qui permet de restreindre un
    rôle à ses propres enregistrements, comme le prévoit le niveau « propre »
    de la matrice des droits.

    `PROTECT` est délibéré : supprimer un utilisateur effacerait la trace de
    ce qu'il a saisi.
    """

    saisie_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="%(class)ss",
        verbose_name="saisi par",
    )

    class Meta:
        abstract = True


class EtatCampagne(models.TextChoices):
    PLANIFIEE = "planifiee", "Planifiée"
    EN_COURS = "en_cours", "En cours"
    TERMINEE = "terminee", "Terminée"
    ANNULEE = "annulee", "Annulée"


class Campagne(models.Model):
    """Tronc commun des campagnes d'aide.

    Ramadan, Kurban, les bourses et les forages suivent tous le même patron :
    une campagne dotée d'un budget, de dates, d'un responsable et d'un état,
    qui produit des distributions vers des bénéficiaires. Écrire ce patron
    quatre fois multiplierait par quatre les occasions d'erreur — en
    particulier sur la règle anti-doublon, qui est un critère de réception.

    Chaque module concret hérite d'ici et n'ajoute que ce qui lui est propre :
    la composition du colis pour Ramadan, le nombre de zébus pour Kurban.

    Attention : un modèle concret destiné à recevoir des distributions (via
    `DistributionAide.campagne`) doit hériter de `apps.campagnes.models.
    CampagneAide`, le parent concret, et non directement de cet abstrait —
    voir la docstring de `CampagneAide` pour la raison (règle anti-doublon).
    """

    code = models.CharField("code", max_length=32)
    libelle = models.CharField("libellé", max_length=150)
    annee = models.PositiveSmallIntegerField("année")
    budget = models.DecimalField(
        "budget",
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    date_debut = models.DateField("date de début")
    date_fin = models.DateField("date de fin", null=True, blank=True)
    etat = models.CharField(
        "état",
        max_length=20,
        choices=EtatCampagne.choices,
        default=EtatCampagne.PLANIFIEE,
    )

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.libelle} {self.annee}"

    def clean(self):
        """Valide les invariantes du modèle.

        La validation des dates vit ici, pas en services, car elle est vraie
        pour toute campagne quel que soit le module qui hérite de cette classe.
        `full_clean()` l'appliquera sur tous les chemins d'écriture — interface
        administrative Django incluse — tandis qu'une vérification en services
        ne porterait que sur l'API métier, laissant l'admin accepter les
        incohérences.
        """
        if self.date_fin and self.date_debut and self.date_fin < self.date_debut:
            raise ValidationError(
                "La date de fin ne peut pas précéder la date de début."
            )


class Distribution(models.Model):
    """Tronc commun des distributions d'aide à un bénéficiaire.

    La quantité et son unité sont génériques : un colis pour Ramadan, des
    kilogrammes de viande pour Kurban.
    """

    date_distribution = models.DateField("date de distribution")
    quantite = models.DecimalField(
        "quantité",
        max_digits=10,
        decimal_places=2,
        default=1,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    unite = models.CharField("unité", max_length=32, default="unité")
    observation = models.TextField("observation", blank=True)

    class Meta:
        abstract = True
