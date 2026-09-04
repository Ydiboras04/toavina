"""Vérifie la cohérence du formulaire bénéficiaire avec la couche services."""
from apps.beneficiaires.forms import FormulaireBeneficiaire
from apps.beneficiaires.services import CHAMPS_MODIFIABLES


def test_meta_fields_couvre_exactement_champs_modifiables():
    """`Meta.fields` est une liste explicite, réordonnée pour l'affichage,
    plutôt que `sorted(CHAMPS_MODIFIABLES)` — l'ordre alphabétique séparerait
    par exemple « nom » de « prénom ». Ce test garantit que cette liste reste
    malgré tout un simple réordonnancement de `CHAMPS_MODIFIABLES`, la
    référence unique côté services : toute divergence future (un champ ajouté
    à l'un et pas à l'autre) doit faire échouer un test plutôt que fuiter
    silencieusement au formulaire."""
    assert set(FormulaireBeneficiaire.Meta.fields) == CHAMPS_MODIFIABLES
