"""Exceptions métier communes.

Elles sont distinctes des exceptions techniques : la couche présentation les
affiche en langage clair à l'utilisateur, tandis qu'une erreur technique est
journalisée et présentée de façon générique (§13 de la spécification).
"""


class PermissionRefusee(Exception):
    """L'utilisateur n'a pas le droit d'effectuer cette opération."""


class RegleMetierViolee(Exception):
    """L'opération contredit une règle de gestion de l'ONG."""


class Introuvable(Exception):
    """La ressource demandée n'existe pas, ou est hors du périmètre visible
    de l'utilisateur.

    Une couche de service la lève à la place de toute exception `DoesNotExist`
    de l'ORM — aucune exception technique ne doit franchir la frontière du
    service — que la ressource n'existe tout simplement pas, ou qu'elle existe
    mais soit masquée à cet utilisateur (par exemple un enregistrement
    archivé). La couche présentation la traduit en réponse HTTP 404 : dans les
    deux cas, il n'y a rien à montrer, et rien à révéler sur la raison exacte
    de l'absence."""
