"""Outils partagés par les vues.

Les vues ne contiennent aucune règle métier : elles appellent un service et
traduisent ses exceptions en réponses HTTP. Cette traduction étant identique
partout, elle vit ici.
"""
from functools import wraps

from django.core.exceptions import PermissionDenied
from django.http import Http404

from core.exceptions import Introuvable, PermissionRefusee


def traduire_erreurs_metier(vue):
    """Convertit les exceptions de la couche de services en réponses HTTP.

    `PermissionRefusee` devient un 403, `Introuvable` un 404.

    `RegleMetierViolee` est délibérément laissée passer : c'est une erreur de
    saisie, pas un refus d'accès. La vue doit la rattacher au formulaire pour
    que l'opérateur voie ce qui ne va pas et puisse corriger — le décorateur ne
    peut pas le faire à sa place.
    """

    @wraps(vue)
    def enveloppe(requete, *args, **kwargs):
        try:
            return vue(requete, *args, **kwargs)
        except PermissionRefusee as erreur:
            raise PermissionDenied(str(erreur)) from erreur
        except Introuvable as erreur:
            raise Http404(str(erreur)) from erreur

    return enveloppe
