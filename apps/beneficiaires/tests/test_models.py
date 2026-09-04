"""Vérifie le modèle Beneficiaire et l'unicité partielle du CIN (§8.1)."""
import pytest
from django.db import IntegrityError

from apps.beneficiaires.models import Beneficiaire, Sexe, StatutBeneficiaire

# La fixture `village` est définie dans le conftest.py à la racine du projet.


@pytest.fixture
def beneficiaire(village):
    return Beneficiaire.objects.create(
        nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN,
        date_naissance="1985-04-12", village=village,
    )


def test_creation_avec_champs_minimaux(beneficiaire):
    assert beneficiaire.nom == "Rakoto"
    assert beneficiaire.statut == StatutBeneficiaire.ACTIF


def test_representation_textuelle(beneficiaire):
    assert str(beneficiaire) == "Rakoto Jean"


def test_non_archive_par_defaut(beneficiaire):
    assert beneficiaire.archive is False


def test_gestionnaire_masque_les_archives(beneficiaire):
    beneficiaire.archive = True
    beneficiaire.save()
    assert Beneficiaire.objects.count() == 0
    assert Beneficiaire.tous.count() == 1


@pytest.mark.django_db
def test_cin_unique_lorsqu_il_est_renseigne(village):
    Beneficiaire.objects.create(
        nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN, village=village,
        numero_cin="101234567890",
    )
    with pytest.raises(IntegrityError):
        Beneficiaire.objects.create(
            nom="Rabe", prenom="Paul", sexe=Sexe.MASCULIN, village=village,
            numero_cin="101234567890",
        )


@pytest.mark.django_db
def test_plusieurs_beneficiaires_sans_cin_autorises(village):
    """Tous les bénéficiaires ne disposent pas d'une carte d'identité (§8.1)."""
    Beneficiaire.objects.create(
        nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN, village=village,
    )
    Beneficiaire.objects.create(
        nom="Rabe", prenom="Paul", sexe=Sexe.MASCULIN, village=village,
    )
    assert Beneficiaire.objects.count() == 2


def test_acces_a_la_region_par_le_village(beneficiaire):
    assert beneficiaire.village.region.libelle == "Menabe"
