"""Règles métier des campagnes et des distributions.

La règle centrale du projet vit ici : un bénéficiaire ne peut pas recevoir
deux fois la même campagne. Elle est appliquée à deux niveaux — une contrainte
du SGBD qui la rend structurellement vraie, et une vérification préalable dans
ce module qui produit un message compréhensible plutôt qu'une erreur technique.
"""
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.campagnes.models import CampagneAide, DistributionAide
from core.exceptions import RegleMetierViolee
from core.models import EtatCampagne
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

CHAMPS_CAMPAGNE = frozenset({
    "code", "libelle", "annee", "budget", "date_debut", "date_fin", "etat",
    "projet", "responsable",
})

CHAMPS_DISTRIBUTION = frozenset({
    "beneficiaire", "campagne", "village", "date_distribution", "quantite",
    "unite", "observation",
})

# Une campagne dans l'un de ces états ne reçoit plus de nouvelle distribution :
# elle est soit révolue (terminée), soit invalidée (annulée). Planifiée ou en
# cours restent seules ouvertes à la saisie.
ETATS_CAMPAGNE_FERMES = frozenset({EtatCampagne.ANNULEE, EtatCampagne.TERMINEE})

# Doit rester synchronisé avec `DistributionAide.Meta.constraints` : c'est ce
# nom que Django cite dans le message technique de `full_clean()` quand la
# contrainte est violée, et qu'`enregistrer_distribution` reconnaît pour
# reformuler ce message.
NOM_CONTRAINTE_DOUBLON = "distribution_unique_par_campagne"


# --- Campagnes -------------------------------------------------------------

def _perimetre_campagne(utilisateur, queryset):
    """Restreint aux campagnes visibles pour un accès « propre », si besoin.

    Calque le patron déjà posé par `apps.projets.services._perimetre` : le
    responsable de projet a le niveau « propre » sur `Module.PROJETS`, qui
    gouverne aussi bien les projets que les campagnes. Deux façons d'être
    concerné par une campagne : en être directement le responsable
    (`CampagneAide.responsable`), ou être responsable du projet auquel elle
    est rattachée (`CampagneAide.projet.responsable`) — un responsable de
    projet doit voir les campagnes de son projet même quand il n'en est pas
    lui-même le responsable nommé.
    """
    return filtrer_perimetre(
        queryset,
        utilisateur,
        Module.PROJETS,
        champ=["responsable", "projet__responsable"],
    )


def _verifier_responsable_autorise(utilisateur, donnees, instance=None):
    """Empêche un périmètre restreint de désigner un autre responsable.

    Sans ce contrôle, un responsable de projet — accès « propre », pas
    « complet » — pourrait créer une campagne attribuée à un collègue : une
    campagne qu'il ne reverrait jamais lui-même, le filtrage par périmètre
    l'en excluant.
    """
    if not perimetre_restreint(utilisateur, Module.PROJETS):
        return
    responsable = donnees.get(
        "responsable", getattr(instance, "responsable", None)
    )
    if responsable is not None and responsable != utilisateur:
        raise RegleMetierViolee(
            "Un utilisateur au périmètre restreint ne peut créer ou "
            "modifier que des campagnes dont il est lui-même responsable."
        )


def _verifier_code_unique_campagne(code, exclure=None):
    """Anticipe la violation de `campagne_code_unique_si_active`.

    Sans elle, un code dupliqué remonterait à l'opérateur sous la forme
    « Contrainte « campagne_code_unique_si_active » violée » — le message
    technique que la double application de la règle est censée éviter. La
    contrainte du SGBD ne portant que sur les campagnes actives,
    `CampagneAide.objects` (déjà filtré sur `archive=False`) est le bon
    ensemble à interroger, pas `CampagneAide.tous`.
    """
    existants = CampagneAide.objects.filter(code=code)
    if exclure is not None:
        existants = existants.exclude(pk=exclure)
    if existants.exists():
        raise RegleMetierViolee(
            f"Le code « {code} » est déjà utilisé par une autre campagne."
        )


def lister_campagnes(utilisateur, annee=None, etat=None):
    exiger(utilisateur, Module.PROJETS, Acces.LECTURE)

    resultats = CampagneAide.objects.select_related("projet", "responsable")
    resultats = _perimetre_campagne(utilisateur, resultats)

    if annee:
        resultats = resultats.filter(annee=annee)
    if etat:
        resultats = resultats.filter(etat=etat)
    return resultats


def obtenir_campagne(utilisateur, identifiant):
    exiger(utilisateur, Module.PROJETS, Acces.LECTURE)
    return obtenir_ou_introuvable(
        _perimetre_campagne(utilisateur, CampagneAide.objects), pk=identifiant
    )


def creer_campagne(utilisateur, **donnees):
    exiger(utilisateur, Module.PROJETS, Acces.PROPRE)
    valider_champs(donnees, CHAMPS_CAMPAGNE)
    _verifier_responsable_autorise(utilisateur, donnees)
    _verifier_code_unique_campagne(donnees.get("code"))

    campagne = CampagneAide(**donnees)
    appliquer_validation(campagne)
    campagne.save()
    return campagne


# --- Distributions ---------------------------------------------------------

def _perimetre(utilisateur, queryset):
    """Restreint aux distributions visibles pour un accès « propre », si besoin.

    Le responsable de projet et le volontaire ont tous deux le niveau
    « propre » sur ce module, mais pas pour la même raison. Un volontaire
    saisit lui-même les distributions : le limiter à `saisie_par` suffit.
    Un responsable de projet, lui, ne saisit typiquement rien — ce sont les
    volontaires de son projet qui le font — mais répond des campagnes de son
    projet ; le limiter à `saisie_par` le laisserait sans aucune
    distribution visible, alors que la matrice des droits définit « propre »
    comme « ses propres objets **ou son périmètre** ». Le périmètre retient
    donc les distributions saisies par l'utilisateur OU rattachées à une
    campagne d'un projet dont il est responsable
    (`campagne__projet__responsable`).
    """
    return filtrer_perimetre(
        queryset,
        utilisateur,
        Module.DISTRIBUTIONS,
        champ=["saisie_par", "campagne__projet__responsable"],
    )


def _message_doublon(beneficiaire, campagne):
    """Message partagé entre la vérification préalable et le rattrapage de
    l'`IntegrityError` : l'opérateur doit voir exactement la même chose, que
    le doublon soit détecté avant ou pendant l'écriture."""
    return (
        f"{beneficiaire} a déjà reçu une aide pour la campagne "
        f"« {campagne} »."
    )


def a_deja_recu(utilisateur, beneficiaire, campagne):
    """Ce bénéficiaire a-t-il déjà reçu une aide valide pour cette campagne ?

    Ne compte que les distributions actives : une aide annulée n'a pas été
    reçue. La question est posée sans restriction de périmètre — un volontaire
    doit savoir qu'une personne a déjà été servie, même par un collègue, sinon
    la prévention des doublons ne fonctionnerait plus.
    """
    exiger(utilisateur, Module.DISTRIBUTIONS, Acces.LECTURE)
    return DistributionAide.objects.filter(
        beneficiaire=beneficiaire, campagne=campagne
    ).exists()


def historique_beneficiaire(utilisateur, beneficiaire):
    """Distributions actives reçues par ce bénéficiaire, toutes saisies
    confondues, de la plus récente à la plus ancienne.

    S'écarte délibérément de `lister_distributions` : elle n'applique **pas**
    `_perimetre`, alors que c'est la règle partout ailleurs dans ce module.
    Ce n'est pas un oubli — c'est la même raison que celle documentée sur
    `a_deja_recu`, en plus grave : un volontaire ou un responsable de projet
    n'a le niveau « propre » sur `Module.DISTRIBUTIONS` que pour ses propres
    saisies ; filtrer par périmètre ici ferait apparaître un bénéficiaire
    servi par un collègue comme n'ayant « jamais reçu d'aide », ce qui est
    faux et dangereux — l'opérateur pourrait attribuer un doublon en toute
    confiance. `a_deja_recu` évite déjà ce piège pour une seule campagne à la
    fois ; cette fonction l'évite pour la vue d'ensemble. Si un futur
    changement réintroduit `_perimetre` ici « pour rester cohérent avec le
    reste du module », il rouvre ce piège : ne le fais pas.

    N'exige que la lecture, comme `a_deja_recu` : consulter l'historique d'un
    bénéficiaire ne modifie rien.
    """
    exiger(utilisateur, Module.DISTRIBUTIONS, Acces.LECTURE)
    return (
        DistributionAide.objects.select_related(
            "beneficiaire", "campagne", "village", "saisie_par"
        )
        .filter(beneficiaire=beneficiaire)
        .order_by("-date_distribution")
    )


def lister_distributions(utilisateur, campagne=None, village=None):
    exiger(utilisateur, Module.DISTRIBUTIONS, Acces.LECTURE)

    resultats = DistributionAide.objects.select_related(
        "beneficiaire", "campagne", "village", "saisie_par"
    )
    resultats = _perimetre(utilisateur, resultats)

    if campagne is not None:
        resultats = resultats.filter(campagne=campagne)
    if village is not None:
        resultats = resultats.filter(village=village)
    return resultats


def enregistrer_distribution(utilisateur, **donnees):
    """Enregistre une aide remise, après vérification du doublon et de l'état
    de la campagne.

    La règle anti-doublon est appliquée à deux niveaux. D'abord une
    vérification préalable (`a_deja_recu`), qui donne le message le plus
    rapide et le plus clair dans le cas courant. Ensuite, parce que deux
    volontaires peuvent servir le même bénéficiaire au même instant et
    franchir tous les deux cette vérification avant que l'un des deux
    n'enregistre, l'écriture elle-même est protégée : elle a lieu dans une
    transaction, et une violation de la contrainte du SGBD
    (`distribution_unique_par_campagne`) est rattrapée et reformulée dans le
    même message que la vérification préalable — jamais laissée fuir comme
    `IntegrityError`, ce qui romprait le contrat de `core.services` interdisant
    à toute exception étrangère de franchir la frontière d'un service.
    """
    exiger(utilisateur, Module.DISTRIBUTIONS, Acces.PROPRE)
    valider_champs(donnees, CHAMPS_DISTRIBUTION)

    beneficiaire = donnees.get("beneficiaire")
    campagne = donnees.get("campagne")

    if campagne is not None and (
        campagne.archive or campagne.etat in ETATS_CAMPAGNE_FERMES
    ):
        raise RegleMetierViolee(
            f"La campagne « {campagne} » est close : aucune nouvelle "
            "distribution ne peut y être enregistrée."
        )

    if a_deja_recu(utilisateur, beneficiaire, campagne):
        raise RegleMetierViolee(_message_doublon(beneficiaire, campagne))

    try:
        with transaction.atomic():
            distribution = DistributionAide(saisie_par=utilisateur, **donnees)
            appliquer_validation(distribution)
            distribution.save()
    except IntegrityError as erreur:
        # Le conflit a échappé à la fois à `a_deja_recu` et à la validation :
        # c'est la contrainte du SGBD elle-même, au moment de l'écriture, qui
        # l'a arrêté.
        raise RegleMetierViolee(
            _message_doublon(beneficiaire, campagne)
        ) from erreur
    except RegleMetierViolee as erreur:
        # `appliquer_validation` (donc `full_clean`) vérifie elle-même les
        # contraintes du modèle avant l'écriture (Django >= 4.1) : dans la
        # course la plus probable, c'est ici, pas dans le bloc précédent, que
        # le conflit est rattrapé — avec le message technique de Django
        # (« La contrainte « … » n'est pas respectée. ») plutôt que le
        # nôtre. On le reconnaît par le nom de la contrainte et on le
        # reformule, pour que l'opérateur voie exactement le même message
        # qu'au chemin normal, que le conflit soit détecté avant ou pendant
        # l'écriture. Toute autre erreur de validation continue de remonter
        # telle quelle.
        if NOM_CONTRAINTE_DOUBLON in str(erreur):
            raise RegleMetierViolee(
                _message_doublon(beneficiaire, campagne)
            ) from erreur
        raise
    return distribution


def annuler_distribution(utilisateur, identifiant, motif):
    """Annule une distribution sans l'effacer.

    L'enregistrement est archivé et le motif conservé : l'historique de ce qui
    a été saisi, puis annulé, reste consultable. La place se libère pour une
    nouvelle distribution, la contrainte d'unicité ne portant que sur les
    lignes actives. Qui a annulé, et quand, sont conservés séparément de
    `saisie_par` — qui continue de désigner l'auteur de la saisie d'origine.

    Comme les cinq autres écritures du module, elle passe par
    `appliquer_validation` avant `save()` — y compris ici, où l'écriture ne
    porte que sur quelques champs via `update_fields` : `full_clean()` valide
    l'instance entière, pas seulement les champs modifiés, mais une
    distribution par ailleurs valide n'a aucune raison d'être rejetée pour un
    champ que cet appel ne touche pas.
    """
    exiger(utilisateur, Module.DISTRIBUTIONS, Acces.PROPRE)
    if not motif or not motif.strip():
        raise RegleMetierViolee("Une annulation doit être motivée.")

    distribution = obtenir_ou_introuvable(
        _perimetre(utilisateur, DistributionAide.objects), pk=identifiant
    )
    distribution.archive = True
    distribution.annulee_par = utilisateur
    distribution.date_annulation = timezone.now()
    distribution.observation = (
        f"{distribution.observation}\nAnnulée : {motif}".strip()
    )
    appliquer_validation(distribution)
    distribution.save(
        update_fields=[
            "archive",
            "observation",
            "date_modification",
            "annulee_par",
            "date_annulation",
        ]
    )
    return distribution
