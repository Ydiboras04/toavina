"""Vérifie que l'administration ne permet pas de supprimer physiquement un
projet — donnée historisée au même titre que les campagnes et distributions
(§8 du MPD)."""
import pytest
from django.contrib import admin
from django.test import RequestFactory

from apps.accounts.models import Utilisateur
from apps.projets.models import Projet


@pytest.fixture
def superutilisateur(db):
    return Utilisateur.objects.create_superuser(
        username="admin_test_projet", email="admin_test_projet@example.com",
        password="motdepasse123",
    )


def test_suppression_de_projet_refusee_pour_un_superutilisateur(superutilisateur):
    requete = RequestFactory().get("/admin/projets/projet/")
    requete.user = superutilisateur

    modele_admin = admin.site._registry[Projet]
    assert modele_admin.has_delete_permission(requete) is False
