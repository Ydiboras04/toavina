"""Vérifie les règles métier et le filtrage par rôle des projets."""
import pytest

from apps.projets.models import EtatProjet
from apps.projets.services import (
    creer_projet,
    lister_projets,
    modifier_projet,
    obtenir_projet,
)
from core.exceptions import Introuvable, PermissionRefusee, RegleMetierViolee
from core.roles import Role


@pytest.fixture
def coordinateur(creer_utilisateur):
    return creer_utilisateur(Role.COORDINATEUR)


@pytest.fixture
def responsable(creer_utilisateur):
    return creer_utilisateur(Role.RESPONSABLE_PROJET, nom="resp1")


def donnees_projet(type_action, responsable, code="PROJ-2026-001"):
    return {
        "code": code,
        "titre": "Distribution alimentaire",
        "budget_prevu": "1000000.00",
        "date_debut": "2026-01-15",
        "type_action": type_action,
        "responsable": responsable,
    }


def test_coordinateur_cree_un_projet(coordinateur, type_action, responsable):
    projet = creer_projet(
        coordinateur, **donnees_projet(type_action, responsable)
    )
    assert projet.pk is not None


def test_volontaire_ne_peut_pas_creer(
    creer_utilisateur, type_action, responsable
):
    volontaire = creer_utilisateur(Role.VOLONTAIRE)
    with pytest.raises(PermissionRefusee):
        creer_projet(volontaire, **donnees_projet(type_action, responsable))


def test_comptable_lit_sans_ecrire(
    creer_utilisateur, coordinateur, type_action, responsable
):
    comptable = creer_utilisateur(Role.COMPTABLE)
    creer_projet(coordinateur, **donnees_projet(type_action, responsable))
    assert lister_projets(comptable).count() == 1
    with pytest.raises(PermissionRefusee):
        creer_projet(comptable, **donnees_projet(type_action, responsable,
                                                 code="PROJ-2026-002"))


def test_responsable_ne_voit_que_ses_projets(
    coordinateur, responsable, creer_utilisateur, type_action
):
    """Le niveau « propre » de la matrice devient effectif ici."""
    autre = creer_utilisateur(Role.RESPONSABLE_PROJET, nom="resp2")
    creer_projet(coordinateur, **donnees_projet(type_action, responsable))
    creer_projet(
        coordinateur,
        **donnees_projet(type_action, autre, code="PROJ-2026-002"),
    )
    assert lister_projets(responsable).count() == 1
    assert lister_projets(coordinateur).count() == 2


def test_recherche_par_code(coordinateur, type_action, responsable):
    creer_projet(coordinateur, **donnees_projet(type_action, responsable))
    creer_projet(
        coordinateur,
        **donnees_projet(type_action, responsable, code="PROJ-2026-002"),
    )
    assert lister_projets(coordinateur, recherche="001").count() == 1


def test_filtre_par_etat(coordinateur, type_action, responsable):
    projet = creer_projet(
        coordinateur, **donnees_projet(type_action, responsable)
    )
    modifier_projet(coordinateur, projet.pk, etat=EtatProjet.EN_COURS)
    assert lister_projets(coordinateur, etat=EtatProjet.EN_COURS).count() == 1
    assert lister_projets(coordinateur, etat=EtatProjet.TERMINE).count() == 0


def test_code_duplique_refuse(coordinateur, type_action, responsable):
    creer_projet(coordinateur, **donnees_projet(type_action, responsable))
    with pytest.raises(RegleMetierViolee):
        creer_projet(coordinateur, **donnees_projet(type_action, responsable))


def test_budget_negatif_refuse(coordinateur, type_action, responsable):
    donnees = donnees_projet(type_action, responsable)
    donnees["budget_prevu"] = "-100.00"
    with pytest.raises(RegleMetierViolee):
        creer_projet(coordinateur, **donnees)


def test_date_fin_avant_date_debut_refusee(
    coordinateur, type_action, responsable
):
    donnees = donnees_projet(type_action, responsable)
    donnees["date_fin"] = "2026-01-01"
    with pytest.raises(RegleMetierViolee):
        creer_projet(coordinateur, **donnees)


def test_champ_inconnu_refuse(coordinateur, type_action, responsable):
    donnees = donnees_projet(type_action, responsable)
    donnees["archive"] = True
    with pytest.raises(RegleMetierViolee):
        creer_projet(coordinateur, **donnees)


def test_projet_inexistant(coordinateur):
    with pytest.raises(Introuvable):
        obtenir_projet(coordinateur, 999999)


def test_responsable_ne_peut_pas_ouvrir_le_projet_d_un_autre(
    coordinateur, responsable, creer_utilisateur, type_action
):
    autre = creer_utilisateur(Role.RESPONSABLE_PROJET, nom="resp2")
    projet = creer_projet(coordinateur, **donnees_projet(type_action, autre))
    with pytest.raises(Introuvable):
        obtenir_projet(responsable, projet.pk)


def test_responsable_se_designant_lui_meme_accepte(responsable, type_action):
    projet = creer_projet(
        responsable, **donnees_projet(type_action, responsable)
    )
    assert projet.pk is not None


def test_responsable_designant_un_autre_refuse(
    responsable, creer_utilisateur, type_action
):
    autre = creer_utilisateur(Role.RESPONSABLE_PROJET, nom="resp2")
    with pytest.raises(RegleMetierViolee):
        creer_projet(responsable, **donnees_projet(type_action, autre))


def test_coordinateur_designant_un_responsable_tiers_accepte(
    coordinateur, type_action, responsable
):
    projet = creer_projet(
        coordinateur, **donnees_projet(type_action, responsable)
    )
    assert projet.pk is not None
