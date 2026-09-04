"""Règles métier des projets.

Toute écriture passe par ce module. Chaque fonction reçoit l'utilisateur en
premier paramètre, contrôle son accès au module, puis restreint le résultat à
son périmètre : un responsable de projet ne voit que les projets qui lui sont
attribués, comme le prévoit le niveau « propre » de la matrice des droits.
"""
from django.db.models import Q

from apps.projets.models import Projet
from core.exceptions import RegleMetierViolee
from core.permissions import (
    Acces,
    Module,
    exiger,
    filtrer_perimetre,
    perimetre_restreint,
)
from core.services import (
    appliquer_validation,
    obtenir_ou_introuvable,
    valider_champs,
)

CHAMPS_MODIFIABLES = frozenset({
    "code", "titre", "description", "budget_prevu", "budget_consomme",
    "date_debut", "date_fin", "etat", "type_action", "responsable", "region",
})


def _perimetre(utilisateur, queryset):
    """Restreint aux projets dont l'utilisateur est responsable, si besoin."""
    return filtrer_perimetre(
        queryset, utilisateur, Module.PROJETS, champ="responsable"
    )


def _verifier_responsable_autorise(utilisateur, donnees, instance=None):
    """Empêche un périmètre restreint d'agir au nom d'un autre responsable.

    Sans ce contrôle, un responsable de projet — qui a l'accès « propre »,
    non « complet » — pourrait créer ou modifier un projet attribué à un
    collègue : un projet qu'il ne reverrait jamais lui-même, puisque le
    filtrage par périmètre l'en exclurait, ou un projet imposé à un tiers.
    """
    if not perimetre_restreint(utilisateur, Module.PROJETS):
        return
    responsable = donnees.get(
        "responsable", getattr(instance, "responsable", None)
    )
    if responsable is not None and responsable != utilisateur:
        raise RegleMetierViolee(
            "Un utilisateur au périmètre restreint ne peut créer ou "
            "modifier que des projets dont il est lui-même responsable."
        )


def _verifier_code_unique(code, exclure=None):
    existants = Projet.tous.filter(code=code)
    if exclure is not None:
        existants = existants.exclude(pk=exclure)
    if existants.exists():
        raise RegleMetierViolee(
            f"Le code « {code} » est déjà utilisé par un autre projet."
        )


def lister_projets(utilisateur, recherche="", etat=None):
    """Projets actifs visibles par l'utilisateur."""
    exiger(utilisateur, Module.PROJETS, Acces.LECTURE)

    resultats = Projet.objects.select_related(
        "type_action", "responsable", "region"
    )
    resultats = _perimetre(utilisateur, resultats)

    if recherche:
        resultats = resultats.filter(
            Q(code__icontains=recherche) | Q(titre__icontains=recherche)
        )
    if etat:
        resultats = resultats.filter(etat=etat)

    return resultats


def obtenir_projet(utilisateur, identifiant):
    """Retourne un projet actif du périmètre de l'utilisateur."""
    exiger(utilisateur, Module.PROJETS, Acces.LECTURE)
    return obtenir_ou_introuvable(
        _perimetre(utilisateur, Projet.objects), pk=identifiant
    )


def creer_projet(utilisateur, **donnees):
    exiger(utilisateur, Module.PROJETS, Acces.PROPRE)
    valider_champs(donnees, CHAMPS_MODIFIABLES)
    _verifier_responsable_autorise(utilisateur, donnees)
    _verifier_code_unique(donnees.get("code"))

    projet = Projet(**donnees)
    appliquer_validation(projet)
    projet.save()
    return projet


def modifier_projet(utilisateur, identifiant, **donnees):
    exiger(utilisateur, Module.PROJETS, Acces.PROPRE)
    valider_champs(donnees, CHAMPS_MODIFIABLES)

    projet = obtenir_ou_introuvable(
        _perimetre(utilisateur, Projet.objects), pk=identifiant
    )
    _verifier_responsable_autorise(utilisateur, donnees, instance=projet)
    if "code" in donnees:
        _verifier_code_unique(donnees["code"], exclure=identifiant)

    for champ, valeur in donnees.items():
        setattr(projet, champ, valeur)
    appliquer_validation(projet)
    projet.save()
    return projet
