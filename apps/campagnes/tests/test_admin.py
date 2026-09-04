"""Vérifie que l'administration ne permet pas de supprimer les données
historisées (§8 du MPD) : suppression physique interdite sur les campagnes
et les distributions, même pour un superutilisateur."""
import pytest
from django.contrib import admin
from django.test import RequestFactory

from apps.accounts.models import Utilisateur
from apps.campagnes.models import CampagneAide, DistributionAide


@pytest.fixture
def superutilisateur(db):
    return Utilisateur.objects.create_superuser(
        username="admin_test", email="admin_test@example.com",
        password="motdepasse123",
    )


def test_suppression_de_distribution_refusee_pour_un_superutilisateur(
    superutilisateur,
):
    requete = RequestFactory().get("/admin/campagnes/distributionaide/")
    requete.user = superutilisateur

    modele_admin = admin.site._registry[DistributionAide]
    assert modele_admin.has_delete_permission(requete) is False


def test_suppression_de_campagne_refusee_pour_un_superutilisateur(
    superutilisateur,
):
    requete = RequestFactory().get("/admin/campagnes/campagneaide/")
    requete.user = superutilisateur

    modele_admin = admin.site._registry[CampagneAide]
    assert modele_admin.has_delete_permission(requete) is False
