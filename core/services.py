"""Primitives partagées par toutes les couches de services métier.

Ces fonctions n'ont rien de spécifique à un module : les recopier dans chaque
`services.py` les ferait diverger. Elles vivent donc ici, et chaque module les
paramètre avec ses propres listes de champs.

Règle que ce fichier fait respecter : aucune exception étrangère au contrat
métier ne franchit la frontière d'un service. Les erreurs de l'ORM et de la
validation Django sont converties en exceptions de `core.exceptions`.
"""
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError

from core.exceptions import Introuvable, RegleMetierViolee
from core.permissions import Module, peut_lire


def valider_champs(donnees, autorises):
    """Rejette toute clé absente de l'ensemble autorisé.

    Sans ce contrôle, un appel du type `modifier(u, pk, archive=True)`
    contournerait le niveau d'accès exigé par la fonction d'archivage, et une
    clé mal orthographiée serait silencieusement perdue à l'enregistrement.
    """
    for champ in donnees:
        if champ not in autorises:
            raise RegleMetierViolee(
                f"Le champ « {champ} » ne peut pas être modifié ici."
            )


def appliquer_validation(instance):
    """Valide l'instance et convertit l'erreur Django en erreur métier.

    Appelée avant chaque `save()` : le formulaire vérifie déjà les listes de
    choix et les longueurs, mais c'est précisément la couche qu'un assistant
    IA n'empruntera pas.
    """
    try:
        instance.full_clean()
    except ValidationError as erreur:
        messages = []
        for champ, erreurs in erreur.message_dict.items():
            if champ == NON_FIELD_ERRORS:
                messages.append(" ".join(erreurs))
            else:
                messages.append(f"{champ} : {' '.join(erreurs)}")
        raise RegleMetierViolee(" ; ".join(messages)) from erreur


def obtenir_ou_introuvable(gestionnaire, **criteres):
    """Retourne l'instance correspondante, ou lève `Introuvable`.

    Le gestionnaire est passé explicitement : `objets` masque les
    enregistrements archivés, `tous` les inclut. Le service choisit selon ce
    qu'il fait — on ne modifie pas une fiche archivée, mais on doit pouvoir
    l'archiver ou la consulter.

    Des critères qui ne garantissent pas l'unicité peuvent faire remonter
    plusieurs enregistrements : `MultipleObjectsReturned` est alors convertie
    en `RegleMetierViolee`, et non en `Introuvable`, car trouver plusieurs
    résultats là où un seul est attendu révèle une incohérence des données,
    pas une absence.
    """
    try:
        return gestionnaire.get(**criteres)
    except gestionnaire.model.DoesNotExist as erreur:
        raise Introuvable(
            f"{gestionnaire.model._meta.verbose_name} introuvable."
        ) from erreur
    except gestionnaire.model.MultipleObjectsReturned as erreur:
        raise RegleMetierViolee(
            f"Plusieurs enregistrements « {gestionnaire.model._meta.verbose_name} » "
            "correspondent au critère demandé."
        ) from erreur


def champs_visibles(utilisateur, courants, sensibles):
    """Retourne les champs que cet utilisateur a le droit de consulter.

    Le résultat indique à l'appelant ce qu'il peut afficher : cette fonction
    ne filtre aucune donnée par elle-même, c'est à la couche présentation de
    l'appliquer.
    """
    champs = set(courants)
    if peut_lire(utilisateur, Module.DONNEES_SENSIBLES):
        champs |= set(sensibles)
    return champs
