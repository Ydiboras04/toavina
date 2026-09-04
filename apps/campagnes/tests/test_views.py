"""Vérifie que les vues des distributions appliquent les droits des services."""
import pytest
from django.urls import reverse

from apps.campagnes.models import DistributionAide
from apps.campagnes.services import creer_campagne, enregistrer_distribution
from apps.projets.models import Projet
from core.models import EtatCampagne
from core.roles import Role


@pytest.fixture
def coordinateur(creer_utilisateur):
    return creer_utilisateur(Role.COORDINATEUR)


@pytest.fixture
def campagne(coordinateur, type_action, creer_utilisateur):
    projet = Projet.objects.create(
        code="PROJ-2026-001", titre="Distribution", budget_prevu="1000.00",
        date_debut="2026-01-15", type_action=type_action,
        responsable=creer_utilisateur(Role.RESPONSABLE_PROJET, nom="respv"),
    )
    return creer_campagne(
        coordinateur, code="RAM-2026", libelle="Ramadan", annee=2026,
        budget="500.00", date_debut="2026-02-18", projet=projet,
        responsable=coordinateur,
    )


def connecter(client, creer_utilisateur, role, nom="agent"):
    utilisateur = creer_utilisateur(role, nom=nom)
    client.force_login(utilisateur)
    return utilisateur


def test_liste_refusee_a_l_anonyme(client, db):
    reponse = client.get(reverse("campagnes:distributions"), follow=True)
    assert reponse.status_code == 200
    assert b"csrfmiddlewaretoken" in reponse.content


def test_liste_accessible_au_coordinateur(client, creer_utilisateur, campagne):
    connecter(client, creer_utilisateur, Role.COORDINATEUR, nom="c2")
    assert client.get(reverse("campagnes:distributions")).status_code == 200


def test_liste_refusee_au_comptable(client, creer_utilisateur, campagne):
    connecter(client, creer_utilisateur, Role.COMPTABLE, nom="cp2")
    assert client.get(reverse("campagnes:distributions")).status_code == 403


def test_enregistrement_par_un_volontaire(
    client, creer_utilisateur, campagne, beneficiaire, village
):
    connecter(client, creer_utilisateur, Role.VOLONTAIRE, nom="v2")
    reponse = client.post(
        reverse("campagnes:enregistrer"),
        {
            "beneficiaire": beneficiaire.pk, "campagne": campagne.pk,
            "village": village.pk, "date_distribution": "2026-02-20",
            "quantite": "1", "unite": "colis",
        },
    )
    assert reponse.status_code == 302
    assert DistributionAide.objects.count() == 1


def test_doublon_affiche_une_erreur_sans_erreur_serveur(
    client, creer_utilisateur, campagne, beneficiaire, village
):
    """Le doublon doit produire un message lisible, pas une erreur 500."""
    volontaire = connecter(client, creer_utilisateur, Role.VOLONTAIRE, nom="v3")
    enregistrer_distribution(
        volontaire, beneficiaire=beneficiaire, campagne=campagne,
        village=village, date_distribution="2026-02-20",
    )
    reponse = client.post(
        reverse("campagnes:enregistrer"),
        {
            "beneficiaire": beneficiaire.pk, "campagne": campagne.pk,
            "village": village.pk, "date_distribution": "2026-02-25",
            "quantite": "1", "unite": "colis",
        },
    )
    assert reponse.status_code == 200
    assert "déjà reçu".encode() in reponse.content
    assert DistributionAide.objects.count() == 1


def test_distribution_inexistante_donne_404(client, creer_utilisateur, campagne):
    connecter(client, creer_utilisateur, Role.COORDINATEUR, nom="c3")
    reponse = client.post(
        reverse("campagnes:annuler", args=[999999]), {"motif": "Erreur"}
    )
    assert reponse.status_code == 404


def test_annulation_par_le_coordinateur(
    client, creer_utilisateur, campagne, beneficiaire, village
):
    coordinateur = connecter(
        client, creer_utilisateur, Role.COORDINATEUR, nom="c4"
    )
    distribution = enregistrer_distribution(
        coordinateur, beneficiaire=beneficiaire, campagne=campagne,
        village=village, date_distribution="2026-02-20",
    )
    reponse = client.post(
        reverse("campagnes:annuler", args=[distribution.pk]),
        {"motif": "Erreur de saisie"},
    )
    assert reponse.status_code == 302
    assert DistributionAide.objects.count() == 0
    assert DistributionAide.tous.count() == 1


def test_champs_du_formulaire_coherents_avec_le_service():
    from apps.campagnes.forms import FormulaireDistribution
    from apps.campagnes.services import CHAMPS_DISTRIBUTION

    assert set(FormulaireDistribution.Meta.fields) == CHAMPS_DISTRIBUTION


def test_campagne_fermee_absente_des_choix_du_formulaire(coordinateur, campagne):
    """Une campagne annulée ne doit pas être proposée à la saisie : la
    couche services refuserait de toute façon la distribution.

    Une campagne encore ouverte (`campagne`, planifiée par défaut) doit en
    revanche rester proposée.
    """
    from apps.campagnes.forms import FormulaireDistribution

    campagne_annulee = creer_campagne(
        coordinateur, code="RAM-2027", libelle="Ramadan clos", annee=2027,
        budget="500.00", date_debut="2027-02-18", projet=campagne.projet,
        responsable=coordinateur, etat=EtatCampagne.ANNULEE,
    )

    formulaire = FormulaireDistribution()
    choix = formulaire.fields["campagne"].queryset

    assert campagne_annulee not in choix
    assert campagne in choix
