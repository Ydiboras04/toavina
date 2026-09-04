"""Règles métier des bénéficiaires.

Toute écriture passe par ce module. Les vues et, à partir du plan 5, les outils
de l'assistant IA appellent ces mêmes fonctions : une règle écrite ici
s'applique donc aux deux (§3 de la spécification).

Chaque fonction reçoit l'utilisateur en premier paramètre. Le contrôle de
droits porte aujourd'hui sur l'*accès au module* : `exiger` vérifie que
l'utilisateur a le niveau requis sur `Module.BENEFICIAIRES` (ou
`Module.DONNEES_SENSIBLES` pour les champs sensibles), puis, si l'accès est
accordé, `lister_beneficiaires` et `rechercher_doublons` renvoient tous les
enregistrements qui correspondent aux critères — il n'existe pas de filtrage
par périmètre d'objets. Cela ne pose pas de problème aujourd'hui parce
qu'aucun rôle de la matrice (§9.1) ne dispose du niveau `Acces.PROPRE` sur
`Module.BENEFICIAIRES` : ce niveau, quand il existe ailleurs dans la matrice,
signifie « restreint à ses propres objets », et aucun rôle ne l'atteint ici
sans avoir aussi `Acces.COMPLET`. Le jour où un rôle obtiendra `PROPRE` sur ce
module, ce module — comme tout autre dans le même cas — devra implémenter ce
filtrage par périmètre avant que ce niveau ne soit accordé, sous peine
d'exposer des enregistrements qui devraient rester hors de portée.

Le contrôle ne porte pas non plus sur les *champs* : les instances renvoyées
par `lister_beneficiaires` et `obtenir_beneficiaire` sont complètes.
`champs_visibles` se contente d'indiquer à l'appelant quels champs il a le
droit d'afficher ; c'est à la couche présentation de l'appliquer.
"""
from django.db.models import Q

from apps.beneficiaires.models import Beneficiaire
from core.exceptions import RegleMetierViolee
from core.permissions import Acces, Module, exiger
from core.services import (
    appliquer_validation,
    champs_visibles as champs_visibles_generique,
    obtenir_ou_introuvable,
    valider_champs,
)

# Champs jamais exposés à un utilisateur sans accès aux données sensibles (§12).
CHAMPS_SENSIBLES = frozenset({"numero_cin", "numero_passeport", "revenu"})

CHAMPS_COURANTS = frozenset({
    "id", "nom", "prenom", "sexe", "date_naissance", "telephone", "adresse",
    "village", "profession", "nombre_enfants", "situation_familiale", "photo",
    "statut",
})

# Champs qu'un appelant peut fixer via creer_beneficiaire()/modifier_beneficiaire().
# `archive`, `pk`/`id`, `date_creation` et `date_modification` en sont
# volontairement exclus : l'archivage a sa propre fonction, avec son propre
# niveau de droit (COMPLET) ; les autres sont gérés par Django ou par la base
# elle-même et ne doivent jamais être écrits via ces kwargs libres.
CHAMPS_MODIFIABLES = frozenset({
    "nom", "prenom", "sexe", "date_naissance", "telephone", "adresse",
    "village", "profession", "nombre_enfants", "situation_familiale",
    "revenu", "photo", "numero_cin", "numero_passeport", "statut",
})


def champs_visibles(utilisateur):
    """Champs de la fiche bénéficiaire visibles par cet utilisateur."""
    return champs_visibles_generique(
        utilisateur, CHAMPS_COURANTS, CHAMPS_SENSIBLES
    )


def lister_beneficiaires(utilisateur, recherche="", village=None):
    """Liste les bénéficiaires actifs visibles par l'utilisateur."""
    exiger(utilisateur, Module.BENEFICIAIRES, Acces.LECTURE)

    resultats = Beneficiaire.objects.select_related("village")

    if recherche:
        resultats = resultats.filter(
            Q(nom__icontains=recherche) | Q(prenom__icontains=recherche)
        )
    if village is not None:
        resultats = resultats.filter(village=village)

    return resultats


def obtenir_beneficiaire(utilisateur, identifiant):
    """Retourne un bénéficiaire actif, ou lève Introuvable."""
    exiger(utilisateur, Module.BENEFICIAIRES, Acces.LECTURE)
    return obtenir_ou_introuvable(
        Beneficiaire.objects.select_related("village"), pk=identifiant
    )


def rechercher_doublons(utilisateur, nom, prenom, date_naissance, village,
                        exclure=None):
    """Cherche des bénéficiaires ressemblant à ceux qu'on s'apprête à créer.

    La recherche est restreinte au même village : deux personnes portant les
    mêmes nom, prénom et date de naissance dans deux villages éloignés sont
    presque certainement deux personnes distinctes (§8.1).

    Elle porte aussi sur les bénéficiaires archivés (`Beneficiaire.tous`) :
    un archivage ne doit pas effacer le souvenir qu'une personne a déjà été
    enregistrée. Sans cela, la contrainte d'unicité du CIN, elle, indifférente
    à l'archivage, lèverait une erreur technique brute là où un simple
    avertissement aurait dû apparaître.

    Une fiche existante dont la date de naissance n'a jamais été relevée ne
    doit pas non plus être écartée du rapprochement : mieux vaut un
    avertissement en trop qu'un doublon manqué.

    Le résultat est un avertissement destiné à l'opérateur, jamais un blocage :
    l'homonymie réelle existe et ne doit pas empêcher un enregistrement.
    """
    exiger(utilisateur, Module.BENEFICIAIRES, Acces.LECTURE)

    resultats = Beneficiaire.tous.filter(
        nom__iexact=nom.strip(),
        prenom__iexact=prenom.strip(),
        village=village,
    )
    if date_naissance:
        resultats = resultats.filter(
            Q(date_naissance=date_naissance) | Q(date_naissance__isnull=True)
        )
    if exclure is not None:
        resultats = resultats.exclude(pk=exclure)

    return resultats


def _normaliser_cin(donnees):
    """Convertit un CIN vide en NULL, sans modifier le dictionnaire reçu.

    La contrainte d'unicité partielle porte sur les valeurs non nulles. Une
    chaîne vide serait une valeur comme une autre, et le deuxième bénéficiaire
    sans carte d'identité déclencherait un conflit.

    N'agit que si la clé « numero_cin » est présente dans `donnees` : à la
    création, l'appelant (`creer_beneficiaire`) s'assure au préalable que la
    clé existe toujours (None par défaut) ; en modification partielle, son
    absence signifie que ce champ n'est pas concerné par l'appel et ne doit
    surtout pas écraser un CIN déjà enregistré.
    """
    resultat = dict(donnees)
    if "numero_cin" in resultat and not resultat["numero_cin"]:
        resultat["numero_cin"] = None
    return resultat


def _verifier_cin_unique(numero_cin, exclure=None):
    """Lève RegleMetierViolee si ce CIN appartient déjà à un autre bénéficiaire.

    La base impose déjà une contrainte d'unicité partielle sur ce champ, mais
    il s'agit d'une règle métier : elle doit être vérifiée ici, pour produire
    un message clair plutôt que de laisser fuir une IntegrityError technique
    vers l'appelant. La recherche porte sur `Beneficiaire.tous`, archivés
    compris : un CIN attribué à une fiche archivée reste pris.
    """
    if not numero_cin:
        return
    doublons = Beneficiaire.tous.filter(numero_cin=numero_cin)
    if exclure is not None:
        doublons = doublons.exclude(pk=exclure)
    if doublons.exists():
        raise RegleMetierViolee(
            f"Le numéro CIN « {numero_cin} » est déjà attribué à un autre "
            "bénéficiaire."
        )


def creer_beneficiaire(utilisateur, **donnees):
    """Crée un bénéficiaire après vérification des droits et des données."""
    exiger(utilisateur, Module.BENEFICIAIRES, Acces.PROPRE)
    valider_champs(donnees, CHAMPS_MODIFIABLES)

    donnees.setdefault("numero_cin", None)
    donnees = _normaliser_cin(donnees)
    _verifier_cin_unique(donnees["numero_cin"])

    beneficiaire = Beneficiaire(**donnees)
    appliquer_validation(beneficiaire)
    beneficiaire.save()
    return beneficiaire


def modifier_beneficiaire(utilisateur, identifiant, **donnees):
    """Modifie un bénéficiaire existant après vérification des droits et des
    données."""
    exiger(utilisateur, Module.BENEFICIAIRES, Acces.PROPRE)
    valider_champs(donnees, CHAMPS_MODIFIABLES)

    donnees = _normaliser_cin(donnees)
    if "numero_cin" in donnees:
        _verifier_cin_unique(donnees["numero_cin"], exclure=identifiant)

    beneficiaire = obtenir_ou_introuvable(Beneficiaire.objects, pk=identifiant)

    for champ, valeur in donnees.items():
        setattr(beneficiaire, champ, valeur)
    appliquer_validation(beneficiaire)
    beneficiaire.save()
    return beneficiaire


def archiver_beneficiaire(utilisateur, identifiant):
    """Archive un bénéficiaire sans le supprimer.

    La suppression physique est interdite : elle effacerait l'historique des
    aides reçues (§8 du MPD).
    """
    exiger(utilisateur, Module.BENEFICIAIRES, Acces.COMPLET)

    beneficiaire = obtenir_ou_introuvable(Beneficiaire.tous, pk=identifiant)
    beneficiaire.archive = True
    beneficiaire.save(update_fields=["archive", "date_modification"])
    return beneficiaire


def historique_aides(utilisateur, identifiant_ou_beneficiaire):
    """Aides valides reçues par ce bénéficiaire, de la plus récente à la plus ancienne.

    Répond à l'exigence de vérifier si une personne a déjà été servie — colis
    Ramadan, viande Kurban, vêtements, forage ou bourse — avant de lui
    attribuer une nouvelle aide. Cette vérification doit rester fiable même
    pour un volontaire ou un responsable de projet — les rôles au niveau
    « propre » sur les distributions : voir `historique_beneficiaire` dans
    `apps.campagnes.services`, qui ne filtre délibérément pas par périmètre,
    pour la même raison que `a_deja_recu`.

    Accepte soit un identifiant (comme avant), soit une instance de
    `Beneficiaire` déjà chargée par l'appelant — la vue `detail` y a déjà
    accès via `obtenir_beneficiaire`, et une seconde requête pour le même
    enregistrement serait superflue sur la page la plus consultée du module.
    Passer directement un objet ne dispense d'aucun contrôle d'accès : le
    droit de lecture sur `Module.BENEFICIAIRES` est toujours vérifié ici, et
    `historique_beneficiaire` vérifie de son côté, dans tous les cas, le
    droit de lecture sur `Module.DISTRIBUTIONS`.

    L'import est local : le module des campagnes importe déjà celui des
    bénéficiaires pour son modèle, et un import croisé en tête de fichier
    empêcherait Django de démarrer.
    """
    from apps.campagnes.services import historique_beneficiaire

    if isinstance(identifiant_ou_beneficiaire, Beneficiaire):
        exiger(utilisateur, Module.BENEFICIAIRES, Acces.LECTURE)
        beneficiaire = identifiant_ou_beneficiaire
    else:
        beneficiaire = obtenir_beneficiaire(utilisateur, identifiant_ou_beneficiaire)

    return historique_beneficiaire(utilisateur, beneficiaire)
