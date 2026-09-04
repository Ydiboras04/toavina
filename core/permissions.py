"""Matrice des droits par rôle (§9 de la spécification).

Cette matrice est l'unique source de vérité des permissions. Les vues et les
outils de l'assistant IA la consultent tous les deux : c'est ce qui garantit
que l'IA ne peut pas accéder à davantage que son utilisateur (§9.3).
"""
from enum import IntEnum
from types import MappingProxyType

from django.db import models

from core.exceptions import PermissionRefusee
from core.roles import Role


class Module(models.TextChoices):
    BENEFICIAIRES = "beneficiaires", "Bénéficiaires"
    DONNEES_SENSIBLES = "donnees_sensibles", "Données sensibles"
    PROJETS = "projets", "Projets et campagnes"
    DISTRIBUTIONS = "distributions", "Distributions"
    FINANCES = "finances", "Dons et finances"
    DOCUMENTS = "documents", "Documents"
    STATISTIQUES = "statistiques", "Statistiques et rapports"
    UTILISATEURS = "utilisateurs", "Utilisateurs"
    ASSISTANT_IA = "assistant_ia", "Assistant IA"
    ANALYSE_BESOINS = "analyse_besoins", "Analyse des besoins"
    VALIDATION_IA = "validation_ia", "Validation des propositions IA"


class Acces(IntEnum):
    """Niveaux d'accès, du plus faible au plus fort."""

    AUCUN = 0
    LECTURE = 1
    PROPRE = 2  # écriture limitée à ses propres objets
    COMPLET = 3


_A = Acces.AUCUN
_L = Acces.LECTURE
_P = Acces.PROPRE
_C = Acces.COMPLET

# Reproduit littéralement le tableau du §9.1 de la spécification.
#
# Enveloppée dans MappingProxyType (matrice et chaque ligne de rôle) : cette
# structure est la pièce de sécurité centrale du projet, elle ne doit pas
# pouvoir être modifiée après import par un code appelant, même par erreur.
MATRICE = MappingProxyType({
    Role.SUPER_ADMIN: MappingProxyType({module: _C for module in Module}),
    Role.PRESIDENT: MappingProxyType({
        Module.BENEFICIAIRES: _L,
        Module.DONNEES_SENSIBLES: _L,
        Module.PROJETS: _L,
        Module.DISTRIBUTIONS: _L,
        Module.FINANCES: _L,
        Module.DOCUMENTS: _L,
        Module.STATISTIQUES: _L,
        Module.UTILISATEURS: _L,
        Module.ASSISTANT_IA: _C,
        Module.ANALYSE_BESOINS: _C,
        Module.VALIDATION_IA: _C,
    }),
    Role.COORDINATEUR: MappingProxyType({
        Module.BENEFICIAIRES: _C,
        Module.DONNEES_SENSIBLES: _L,
        Module.PROJETS: _C,
        Module.DISTRIBUTIONS: _C,
        Module.FINANCES: _L,
        Module.DOCUMENTS: _C,
        Module.STATISTIQUES: _L,
        Module.UTILISATEURS: _A,
        Module.ASSISTANT_IA: _C,
        Module.ANALYSE_BESOINS: _C,
        Module.VALIDATION_IA: _C,
    }),
    Role.COMPTABLE: MappingProxyType({
        Module.BENEFICIAIRES: _A,
        Module.DONNEES_SENSIBLES: _A,
        Module.PROJETS: _L,
        Module.DISTRIBUTIONS: _A,
        Module.FINANCES: _C,
        Module.DOCUMENTS: _P,
        Module.STATISTIQUES: _L,
        Module.UTILISATEURS: _A,
        Module.ASSISTANT_IA: _C,
        Module.ANALYSE_BESOINS: _L,
        Module.VALIDATION_IA: _P,
    }),
    Role.RESPONSABLE_PROJET: MappingProxyType({
        Module.BENEFICIAIRES: _L,
        Module.DONNEES_SENSIBLES: _A,
        Module.PROJETS: _P,
        Module.DISTRIBUTIONS: _P,
        Module.FINANCES: _L,
        Module.DOCUMENTS: _P,
        Module.STATISTIQUES: _P,
        Module.UTILISATEURS: _A,
        Module.ASSISTANT_IA: _C,
        Module.ANALYSE_BESOINS: _L,
        Module.VALIDATION_IA: _P,
    }),
    Role.VOLONTAIRE: MappingProxyType({
        Module.BENEFICIAIRES: _L,
        Module.DONNEES_SENSIBLES: _A,
        Module.PROJETS: _A,
        Module.DISTRIBUTIONS: _P,
        Module.FINANCES: _A,
        Module.DOCUMENTS: _A,
        Module.STATISTIQUES: _A,
        Module.UTILISATEURS: _A,
        Module.ASSISTANT_IA: _P,
        Module.ANALYSE_BESOINS: _A,
        Module.VALIDATION_IA: _A,
    }),
    Role.VISITEUR: MappingProxyType({module: _A for module in Module}),
})


def acces(utilisateur, module):
    """Retourne le niveau d'accès de l'utilisateur sur le module."""
    role = getattr(utilisateur, "role", None)
    if role is None:
        return Acces.AUCUN
    return MATRICE.get(role, {}).get(module, Acces.AUCUN)


def peut_lire(utilisateur, module):
    return acces(utilisateur, module) >= Acces.LECTURE


def peut_ecrire(utilisateur, module):
    return acces(utilisateur, module) >= Acces.PROPRE


def perimetre_restreint(utilisateur, module):
    """Vrai si l'utilisateur ne voit que ses propres objets sur ce module.

    Attention : cette fonction n'autorise rien par elle-même, elle affine un
    périmètre déjà autorisé. Elle renvoie `False` aussi bien pour `AUCUN` que
    pour `COMPLET` : un appelant qui filtrerait un queryset uniquement
    `if perimetre_restreint(...)`, sans avoir d'abord vérifié l'accès avec
    `exiger` ou `peut_lire`, exposerait tout le module à un utilisateur sans
    aucun droit. Un contrôle d'accès (`exiger` ou `peut_lire`) doit donc
    toujours précéder son appel.
    """
    return acces(utilisateur, module) == Acces.PROPRE


def exiger(utilisateur, module, minimum):
    """Lève PermissionRefusee si l'accès est inférieur au minimum requis.

    Le message d'erreur est construit de façon défensive : si `module` n'est
    pas une valeur valide de `Module`, `Module(module).label` lèverait
    `ValueError` et transformerait un refus d'accès (403) en erreur technique
    (500). On retombe alors sur une représentation textuelle brute.
    """
    if acces(utilisateur, module) < minimum:
        try:
            nom_module = Module(module).label
        except ValueError:
            nom_module = str(module)
        raise PermissionRefusee(f"Accès refusé au module « {nom_module} ».")


def filtrer_perimetre(queryset, utilisateur, module, champ="saisie_par"):
    """Restreint un queryset aux objets de l'utilisateur si son accès est « propre ».

    À appeler systématiquement **après** `exiger`, jamais à sa place : cette
    fonction affine un périmètre déjà autorisé, elle n'autorise rien par
    elle-même. Sans elle, un rôle au niveau « propre » obtiendrait la totalité
    du module — le niveau ne serait qu'un décor.

    `champ` accepte trois formes, pour que ce périmètre puisse être aussi bien
    un simple champ qu'une union de conditions :

    - une chaîne (comportement historique, et la forme la plus fréquente) :
      équivaut à `queryset.filter(**{champ: utilisateur})` — un seul champ
      comparé à l'utilisateur.
    - un `django.db.models.Q` déjà construit par l'appelant, passé tel quel à
      `.filter()`. Nécessaire dès que « propre » ne se réduit pas à un champ
      unique — par exemple « les objets que j'ai saisis OU ceux rattachés à un
      projet dont je suis responsable ».
    - une liste ou un tuple de chemins de champs, combinés par OU (chaque
      chemin comparé à `utilisateur`) : raccourci pour ce même besoin de
      condition multiple, sans obliger chaque appelant à importer `Q` pour un
      cas aussi simple.
    """
    if not perimetre_restreint(utilisateur, module):
        return queryset
    if isinstance(champ, str):
        return queryset.filter(**{champ: utilisateur})
    if isinstance(champ, models.Q):
        condition = champ
    else:
        condition = models.Q()
        for chemin in champ:
            condition |= models.Q(**{chemin: utilisateur})
    return queryset.filter(condition)
