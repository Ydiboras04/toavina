from django.contrib import admin

from apps.campagnes.models import CampagneAide, DistributionAide


@admin.register(CampagneAide)
class CampagneAideAdmin(admin.ModelAdmin):
    list_display = ["code", "libelle", "annee", "etat", "projet"]
    list_filter = ["etat", "annee"]
    search_fields = ["code", "libelle"]

    def has_delete_permission(self, request, obj=None):
        """Interdit la suppression physique, même au personnel de l'admin.

        La spécification (§8 du MPD) interdit la suppression des données
        historisées : une campagne effacée ferait disparaître, en cascade
        via `on_delete=models.PROTECT` sur `DistributionAide.campagne`, la
        trace des aides réellement remises à son titre — ou, si la
        protection l'empêchait, laisserait le compte du personnel face à une
        erreur au lieu du chemin prévu, l'archivage.
        """
        return False


@admin.register(DistributionAide)
class DistributionAideAdmin(admin.ModelAdmin):
    list_display = [
        "beneficiaire", "campagne", "village", "date_distribution", "archive",
    ]
    list_filter = ["campagne", "archive"]
    search_fields = ["beneficiaire__nom", "beneficiaire__prenom"]

    def has_delete_permission(self, request, obj=None):
        """Interdit la suppression physique, même au personnel de l'admin.

        La spécification (§8 du MPD) interdit la suppression des données
        historisées : « une distribution effacée ferait disparaître la trace
        d'une aide réellement remise ». La suppression prévue est
        l'archivage (voir `apps.campagnes.services.annuler_distribution`),
        pas `DELETE` — y compris depuis cette interface.
        """
        return False
