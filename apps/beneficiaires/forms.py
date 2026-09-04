"""Formulaires des bénéficiaires.

Le formulaire ne valide que la forme des données. Les règles métier — droits,
doublons, normalisation du CIN — appartiennent à la couche services.

Une exception délibérée à ce principe : le formulaire retire de lui-même les
champs sensibles (CIN, passeport, revenu) que l'utilisateur n'a pas le droit
de consulter. Sans cela, `{{ formulaire.as_p }}` en modification — le
formulaire est alors lié à l'instance existante — pré-remplirait les
attributs `value=""` du HTML avec ces valeurs réelles, y compris pour un
utilisateur qui n'a que le droit de lecture sur les bénéficiaires (volontaire,
responsable de projet) : la page fuiterait des données que la fiche de détail
masque correctement. Ce n'est pas un contrôle d'accès — `champs_visibles` le
fait déjà côté services — seulement l'application, côté présentation, d'une
information déjà calculée par la couche métier.
"""
from django import forms

from apps.beneficiaires.models import Beneficiaire
from apps.beneficiaires.services import CHAMPS_SENSIBLES, champs_visibles

# `CHAMPS_MODIFIABLES` (services.py) est l'ensemble de référence : c'est lui
# qui définit quels champs peuvent être écrits via la couche services. Cette
# liste doit contenir exactement les mêmes champs, mais dans un ordre pensé
# pour l'affichage plutôt que l'ordre alphabétique de l'ensemble — d'où la
# liste explicite plutôt que `sorted(CHAMPS_MODIFIABLES)`, qui séparerait par
# exemple « nom » de « prénom » et placerait « photo » avant « prénom ». Toute
# divergence entre les deux est détectée par
# test_meta_fields_couvre_exactement_champs_modifiables (test_forms.py).
_ORDRE_AFFICHAGE = [
    "nom", "prenom", "sexe", "date_naissance", "telephone", "adresse",
    "village", "profession", "nombre_enfants", "situation_familiale",
    "revenu", "photo", "numero_cin", "numero_passeport", "statut",
]


class FormulaireBeneficiaire(forms.ModelForm):
    class Meta:
        model = Beneficiaire
        fields = _ORDRE_AFFICHAGE
        widgets = {
            "date_naissance": forms.DateInput(attrs={"type": "date"}),
            "adresse": forms.TextInput(),
        }

    def __init__(self, *args, utilisateur=None, **kwargs):
        super().__init__(*args, **kwargs)
        visibles = champs_visibles(utilisateur)
        for champ in CHAMPS_SENSIBLES:
            if champ not in visibles and champ in self.fields:
                del self.fields[champ]
