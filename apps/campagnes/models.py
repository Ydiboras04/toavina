"""Campagnes d'aide et distributions aux bénéficiaires."""
from django.conf import settings
from django.db import models

from apps.beneficiaires.models import Beneficiaire
from apps.geographie.models import Village
from apps.projets.models import Projet
from core.models import Archivable, Campagne, Distribution, Horodate, SaisiPar


class CampagneAide(Campagne, Horodate, Archivable):
    """Campagne concrète rattachée à un projet — parent concret des futures
    campagnes spécialisées.

    Hérite du tronc commun défini dans `core` : code, libellé, année, budget,
    dates et état. Les campagnes spécialisées d'un lot ultérieur — Ramadan avec
    la composition de ses colis, Kurban avec ses zébus — hériteront de CE
    modèle, `CampagneAide`, et non de l'abstrait `core.models.Campagne` : il
    s'agit d'héritage multi-table Django, la table fille partageant la clé
    primaire de cette table-ci.

    Pourquoi c'est essentiel : `DistributionAide.campagne` est une clé
    étrangère vers `CampagneAide`, et l'index unique partiel qui interdit les
    doublons (`distribution_unique_par_campagne`) ne porte que sur cette
    table. Parce que la clé primaire est partagée, une distribution peut
    référencer indifféremment une campagne Ramadan, Kurban ou tout autre type
    futur — via cette même clé étrangère — et l'index unique partiel les
    couvre alors toutes automatiquement, sans rien dupliquer.

    Faire hériter une campagne spécialisée de l'abstrait `core.models.Campagne`
    à la place créerait une table sœur de celle-ci, hors de portée de
    `DistributionAide.campagne` : aucune distribution ne pourrait la
    référencer, et la règle anti-doublon ne s'appliquerait ni aux colis
    Ramadan ni à la viande Kurban — précisément les cas où elle est le plus
    nécessaire.
    """

    projet = models.ForeignKey(
        Projet,
        on_delete=models.PROTECT,
        related_name="campagnes",
        verbose_name="projet",
    )
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="campagnes_animees",
        verbose_name="responsable",
    )

    class Meta:
        verbose_name = "campagne"
        verbose_name_plural = "campagnes"
        ordering = ["-annee", "libelle"]
        # Redéclaré explicitement ici : `Archivable.Meta` ne porte PAS
        # `base_manager_name` (cette option en a été retirée, car elle n'y
        # aurait de toute façon aucun effet — voir la docstring d'`Archivable`).
        # `Options.base_manager` ne remonte que le tout premier parent de la
        # MRO possédant un `_meta` (ici `Campagne`, listé avant `Archivable`
        # dans les bases de cette classe) et s'arrête là, qu'il porte ou non
        # un gestionnaire de base personnalisé — l'attribut d'`Archivable`
        # ne serait donc jamais atteint. C'est pourquoi ce modèle concret
        # déclare lui-même `base_manager_name = "tous"`, pour rendre explicite
        # le comportement non filtrant que Django adopte déjà par défaut sur
        # les traversées de clé étrangère (voir la docstring d'`Archivable`).
        base_manager_name = "tous"
        constraints = [
            models.UniqueConstraint(
                fields=["code"],
                condition=models.Q(archive=False),
                name="campagne_code_unique_si_active",
            )
        ]


class DistributionAide(Distribution, Horodate, Archivable, SaisiPar):
    """Aide effectivement remise à un bénéficiaire au titre d'une campagne.

    Une seule entité pour toutes les formes d'aide. Le cahier des charges
    demande de vérifier si une personne a déjà reçu un colis Ramadan, de la
    viande Kurban, des vêtements, un forage ou une bourse : cinq vérifications
    réparties sur cinq tables offriraient cinq occasions de laisser passer un
    doublon. Ici la règle est portée une fois, par le SGBD.
    """

    beneficiaire = models.ForeignKey(
        Beneficiaire,
        on_delete=models.PROTECT,
        related_name="distributions",
        verbose_name="bénéficiaire",
    )
    campagne = models.ForeignKey(
        CampagneAide,
        on_delete=models.PROTECT,
        related_name="distributions",
        verbose_name="campagne",
    )
    village = models.ForeignKey(
        Village,
        on_delete=models.PROTECT,
        related_name="distributions",
        verbose_name="village de distribution",
        help_text=(
            "Lieu où l'aide a été remise, qui peut différer du village de "
            "résidence du bénéficiaire."
        ),
    )
    annulee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="distributions_annulees",
        verbose_name="annulée par",
        help_text="Renseigné uniquement si cette distribution a été annulée.",
    )
    date_annulation = models.DateTimeField(
        "date d'annulation", null=True, blank=True
    )

    class Meta:
        verbose_name = "distribution"
        verbose_name_plural = "distributions"
        ordering = ["-date_distribution"]
        # Voir le commentaire équivalent sur `CampagneAide.Meta` : redéclaré
        # ici pour la même raison. `Archivable.Meta` ne porte pas
        # `base_manager_name` (option retirée, sans effet à ce niveau), donc
        # ce modèle concret le déclare lui-même pour rendre explicite le
        # comportement non filtrant que Django adopte déjà par défaut.
        base_manager_name = "tous"
        indexes = [
            models.Index(
                fields=["campagne", "village"],
                name="distribution_campagne_village",
            ),
        ]
        constraints = [
            # Un bénéficiaire ne peut recevoir qu'une fois la même campagne.
            # La condition sur l'archivage est essentielle : sans elle, une
            # distribution saisie par erreur puis annulée bloquerait
            # définitivement la distribution réelle.
            models.UniqueConstraint(
                fields=["beneficiaire", "campagne"],
                condition=models.Q(archive=False),
                name="distribution_unique_par_campagne",
            ),
        ]

    def __str__(self):
        return f"{self.beneficiaire} — {self.campagne}"
