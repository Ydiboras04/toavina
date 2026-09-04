"""Vérifie les campagnes, les distributions et la règle anti-doublon."""
import pytest
from django.db import IntegrityError

from apps.campagnes.models import CampagneAide, DistributionAide
from apps.projets.models import Projet
from core.models import EtatCampagne
from core.roles import Role


@pytest.fixture
def projet(db, type_action, creer_utilisateur):
    return Projet.objects.create(
        code="PROJ-2026-001",
        titre="Distribution alimentaire",
        budget_prevu="1000000.00",
        date_debut="2026-01-15",
        type_action=type_action,
        responsable=creer_utilisateur(Role.RESPONSABLE_PROJET),
    )


@pytest.fixture
def campagne(db, projet, creer_utilisateur):
    return CampagneAide.objects.create(
        code="RAM-2026",
        libelle="Ramadan",
        annee=2026,
        budget="500000.00",
        date_debut="2026-02-18",
        projet=projet,
        responsable=creer_utilisateur(Role.COORDINATEUR, nom="coord1"),
    )


@pytest.fixture
def agent(creer_utilisateur):
    return creer_utilisateur(Role.VOLONTAIRE, nom="agent1")


def test_campagne_creee_planifiee(campagne):
    assert campagne.etat == EtatCampagne.PLANIFIEE


def test_representation_de_la_campagne(campagne):
    assert str(campagne) == "Ramadan 2026"


def test_distribution_enregistree(campagne, beneficiaire, village, agent):
    distribution = DistributionAide.objects.create(
        beneficiaire=beneficiaire,
        campagne=campagne,
        village=village,
        date_distribution="2026-02-20",
        saisie_par=agent,
    )
    assert distribution.pk is not None
    assert distribution.quantite == 1


@pytest.mark.django_db
def test_deux_distributions_pour_la_meme_campagne_refusees(
    campagne, beneficiaire, village, agent
):
    """Critère de réception : pas de doublon de distribution."""
    DistributionAide.objects.create(
        beneficiaire=beneficiaire, campagne=campagne, village=village,
        date_distribution="2026-02-20", saisie_par=agent,
    )
    with pytest.raises(IntegrityError):
        DistributionAide.objects.create(
            beneficiaire=beneficiaire, campagne=campagne, village=village,
            date_distribution="2026-02-25", saisie_par=agent,
        )


@pytest.mark.django_db
def test_une_distribution_annulee_libere_la_place(
    campagne, beneficiaire, village, agent
):
    """Une aide annulée n'a pas été reçue : la vraie doit pouvoir être saisie."""
    premiere = DistributionAide.objects.create(
        beneficiaire=beneficiaire, campagne=campagne, village=village,
        date_distribution="2026-02-20", saisie_par=agent,
    )
    premiere.archive = True
    premiere.save()

    seconde = DistributionAide.objects.create(
        beneficiaire=beneficiaire, campagne=campagne, village=village,
        date_distribution="2026-02-25", saisie_par=agent,
    )
    assert seconde.pk is not None
    assert DistributionAide.objects.count() == 1
    assert DistributionAide.tous.count() == 2


@pytest.mark.django_db
def test_deux_campagnes_differentes_autorisees(
    campagne, projet, beneficiaire, village, agent, creer_utilisateur
):
    """Recevoir Ramadan puis Kurban la même année est légitime."""
    autre = CampagneAide.objects.create(
        code="KUR-2026", libelle="Kurban", annee=2026, budget="300000.00",
        date_debut="2026-06-06", projet=projet,
        responsable=creer_utilisateur(Role.COORDINATEUR, nom="coord2"),
    )
    DistributionAide.objects.create(
        beneficiaire=beneficiaire, campagne=campagne, village=village,
        date_distribution="2026-02-20", saisie_par=agent,
    )
    DistributionAide.objects.create(
        beneficiaire=beneficiaire, campagne=autre, village=village,
        date_distribution="2026-06-10", saisie_par=agent,
    )
    assert DistributionAide.objects.count() == 2


def test_suppression_du_beneficiaire_bloquee(
    campagne, beneficiaire, village, agent
):
    """L'historique des aides ne doit pas pouvoir disparaître."""
    from django.db.models import ProtectedError

    DistributionAide.objects.create(
        beneficiaire=beneficiaire, campagne=campagne, village=village,
        date_distribution="2026-02-20", saisie_par=agent,
    )
    with pytest.raises(ProtectedError):
        beneficiaire.delete()


@pytest.mark.django_db
def test_distribution_reste_consultable_apres_archivage_du_beneficiaire(
    campagne, beneficiaire, village, agent
):
    """L'historique d'une aide ne doit pas disparaître quand le bénéficiaire
    qui l'a reçue est ensuite archivé : c'est l'usage même que le gestionnaire
    `tous` est censé permettre.

    Ce test n'emprunte volontairement aucun `select_related` : il traverse la
    relation `beneficiaire` en accès simple, comme le ferait `str()`, pour
    exercer le gestionnaire de base réellement utilisé par Django lors d'une
    traversée de clé étrangère.
    """
    distribution = DistributionAide.objects.create(
        beneficiaire=beneficiaire, campagne=campagne, village=village,
        date_distribution="2026-02-20", saisie_par=agent,
    )
    beneficiaire.archive = True
    beneficiaire.save()

    relue = DistributionAide.tous.get(pk=distribution.pk)
    assert relue.beneficiaire.pk == beneficiaire.pk
    assert str(relue) == "Rakoto Jean — Ramadan 2026"


def test_representation_de_la_distribution(
    campagne, beneficiaire, village, agent
):
    distribution = DistributionAide.objects.create(
        beneficiaire=beneficiaire, campagne=campagne, village=village,
        date_distribution="2026-02-20", saisie_par=agent,
    )
    assert str(distribution) == "Rakoto Jean — Ramadan 2026"
