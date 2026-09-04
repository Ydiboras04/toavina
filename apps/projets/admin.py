from django.contrib import admin

from apps.projets.models import Projet, TypeAction


@admin.register(TypeAction)
class TypeActionAdmin(admin.ModelAdmin):
    list_display = ["libelle"]
    search_fields = ["libelle"]


@admin.register(Projet)
class ProjetAdmin(admin.ModelAdmin):
    list_display = ["code", "titre", "type_action", "etat", "date_debut"]
    list_filter = ["etat", "type_action"]
    search_fields = ["code", "titre"]

    def has_delete_permission(self, request, obj=None):
        """Interdit la suppression physique, même au personnel de l'admin.

        `Projet` est une donnée historisée (elle hérite d'`Archivable`), au
        même titre que `CampagneAide` et `DistributionAide` : la
        spécification (§8 du MPD) interdit sa suppression. Le chemin prévu
        est l'archivage, pas `DELETE` — y compris depuis cette interface.
        """
        return False
