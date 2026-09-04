"""Formulaires des distributions.

Le formulaire ne valide que la forme des données. Les règles métier — droits,
prévention des doublons, traçabilité de la saisie — appartiennent à la couche
de services.
"""
from django import forms

from apps.campagnes.models import CampagneAide, DistributionAide
from apps.campagnes.services import CHAMPS_DISTRIBUTION, ETATS_CAMPAGNE_FERMES

_ORDRE_AFFICHAGE = [
    "beneficiaire", "campagne", "village", "date_distribution",
    "quantite", "unite", "observation",
]


class FormulaireDistribution(forms.ModelForm):
    class Meta:
        model = DistributionAide
        # L'ordre est explicite pour la lisibilité du formulaire ;
        # un test vérifie que l'ensemble coïncide avec CHAMPS_DISTRIBUTION.
        fields = _ORDRE_AFFICHAGE
        widgets = {
            "date_distribution": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ne proposer que les campagnes sur lesquelles une saisie a une
        # chance d'aboutir. `enregistrer_distribution` refuse toute nouvelle
        # distribution sur une campagne archivée, annulée ou terminée
        # (`ETATS_CAMPAGNE_FERMES`) : sans ce filtre, le formulaire offrirait
        # un choix voué au refus. `CampagneAide.objects` exclut déjà les
        # campagnes archivées ; il ne reste qu'à écarter les états fermés,
        # en réutilisant l'ensemble déjà défini dans la couche services
        # plutôt que de le réécrire ici.
        #
        # Un filtrage fonctionnel, pas un contrôle de permission : une
        # campagne n'est pas une donnée personnelle, et le volontaire — qui
        # n'a aucun droit sur le module des projets — doit pouvoir en
        # choisir une pour saisir sa distribution.
        self.fields["campagne"].queryset = CampagneAide.objects.exclude(
            etat__in=ETATS_CAMPAGNE_FERMES
        )


class FormulaireAnnulation(forms.Form):
    motif = forms.CharField(
        label="Motif de l'annulation",
        max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "Erreur de saisie…"}),
    )
