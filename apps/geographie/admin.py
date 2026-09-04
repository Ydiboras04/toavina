"""Administration du référentiel géographique."""
from django.contrib import admin

from apps.geographie.models import Commune, District, Pays, Region, Village


@admin.register(Pays)
class PaysAdmin(admin.ModelAdmin):
    list_display = ("libelle", "code_iso")
    search_fields = ("libelle", "code_iso")


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("libelle", "pays")
    search_fields = ("libelle",)
    list_filter = ("pays",)


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ("libelle", "region")
    search_fields = ("libelle",)
    list_filter = ("region",)


@admin.register(Commune)
class CommuneAdmin(admin.ModelAdmin):
    list_display = ("libelle", "district")
    search_fields = ("libelle",)
    list_filter = ("district",)


@admin.register(Village)
class VillageAdmin(admin.ModelAdmin):
    list_display = ("libelle", "commune", "latitude", "longitude")
    search_fields = ("libelle",)
    list_filter = ("commune",)
