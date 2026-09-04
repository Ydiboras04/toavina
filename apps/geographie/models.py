"""Référentiel géographique (décision D1 de la spécification).

Le cahier des charges plaçait village, commune, district et région comme
champs texte de la fiche bénéficiaire. En texte libre, l'agrégation par zone
exigée au §8.1 devient impossible : ces niveaux sont donc des entités.
"""
from django.db import models

from core.models import Horodate


class Pays(Horodate):
    libelle = models.CharField("libellé", max_length=100, unique=True)
    code_iso = models.CharField("code ISO", max_length=3, unique=True)

    class Meta:
        verbose_name = "pays"
        verbose_name_plural = "pays"
        ordering = ["libelle"]

    def __str__(self):
        return self.libelle


class Region(Horodate):
    libelle = models.CharField("libellé", max_length=100)
    pays = models.ForeignKey(
        Pays, on_delete=models.PROTECT, related_name="regions", verbose_name="pays"
    )

    class Meta:
        verbose_name = "région"
        verbose_name_plural = "régions"
        ordering = ["libelle"]
        constraints = [
            models.UniqueConstraint(
                fields=["libelle", "pays"], name="region_unique_dans_pays"
            )
        ]

    def __str__(self):
        return self.libelle


class District(Horodate):
    libelle = models.CharField("libellé", max_length=100)
    region = models.ForeignKey(
        Region,
        on_delete=models.PROTECT,
        related_name="districts",
        verbose_name="région",
    )

    class Meta:
        verbose_name = "district"
        verbose_name_plural = "districts"
        ordering = ["libelle"]
        constraints = [
            models.UniqueConstraint(
                fields=["libelle", "region"], name="district_unique_dans_region"
            )
        ]

    def __str__(self):
        return self.libelle


class Commune(Horodate):
    libelle = models.CharField("libellé", max_length=100)
    district = models.ForeignKey(
        District,
        on_delete=models.PROTECT,
        related_name="communes",
        verbose_name="district",
    )

    class Meta:
        verbose_name = "commune"
        verbose_name_plural = "communes"
        ordering = ["libelle"]
        constraints = [
            models.UniqueConstraint(
                fields=["libelle", "district"], name="commune_unique_dans_district"
            )
        ]

    def __str__(self):
        return self.libelle


class Village(Horodate):
    libelle = models.CharField("libellé", max_length=100)
    commune = models.ForeignKey(
        Commune,
        on_delete=models.PROTECT,
        related_name="villages",
        verbose_name="commune",
    )
    latitude = models.DecimalField(
        "latitude", max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        "longitude", max_digits=9, decimal_places=6, null=True, blank=True
    )

    class Meta:
        verbose_name = "village"
        verbose_name_plural = "villages"
        ordering = ["libelle"]
        constraints = [
            models.UniqueConstraint(
                fields=["libelle", "commune"], name="village_unique_dans_commune"
            )
        ]

    def __str__(self):
        return f"{self.libelle} ({self.commune.district.libelle})"

    @property
    def region(self):
        """Remonte la hiérarchie jusqu'à la région."""
        return self.commune.district.region
