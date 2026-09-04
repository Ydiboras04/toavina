"""Vérifie le modèle Projet et le référentiel des types d'action."""
from datetime import date

import pytest
from django.core.exceptions import ValidationError

from apps.projets.models import EtatProjet, Projet


@pytest.fixture
def projet(db, type_action, creer_utilisateur, village):
    from core.roles import Role

    return Projet.objects.create(
        code="PROJ-2026-001",
        titre="Distribution alimentaire à Morondava",
        description="Campagne de distribution sur le district de Morondava.",
        budget_prevu="15000000.00",
        date_debut="2026-01-15",
        type_action=type_action,
        responsable=creer_utilisateur(Role.RESPONSABLE_PROJET),
        region=village.region,
    )


def test_creation_avec_champs_minimaux(projet):
    assert projet.pk is not None
    assert projet.etat == EtatProjet.PLANIFIE


def test_budget_consomme_est_nul_au_depart(projet):
    assert projet.budget_consomme == 0


def test_budget_restant(projet):
    projet.budget_consomme = "5000000.00"
    projet.save()
    projet.refresh_from_db()
    assert str(projet.budget_restant) == "10000000.00"


def test_representation_textuelle(projet):
    assert str(projet) == "PROJ-2026-001 — Distribution alimentaire à Morondava"


@pytest.mark.django_db
def test_code_unique(projet, type_action, creer_utilisateur):
    from django.db import IntegrityError
    from core.roles import Role

    with pytest.raises(IntegrityError):
        Projet.objects.create(
            code="PROJ-2026-001",
            titre="Autre projet",
            budget_prevu="100.00",
            date_debut="2026-02-01",
            type_action=type_action,
            responsable=creer_utilisateur(Role.COORDINATEUR),
        )


def test_non_archive_par_defaut(projet):
    assert projet.archive is False


def test_gestionnaire_masque_les_archives(projet):
    projet.archive = True
    projet.save()
    assert Projet.objects.count() == 0
    assert Projet.tous.count() == 1


def test_type_action_representation(type_action):
    assert str(type_action) == "Distribution alimentaire"


def test_clean_refuse_date_fin_avant_date_debut():
    """`clean()` doit rejeter l'incohérence sans passer par les services.

    Appelé directement sur une instance non sauvegardée : c'est ce chemin,
    emprunté aussi par l'administration Django via `full_clean()`, que la
    couche de services ne peut pas garantir seule.
    """
    projet = Projet(date_debut=date(2026, 2, 1), date_fin=date(2026, 1, 1))
    with pytest.raises(ValidationError):
        projet.clean()
