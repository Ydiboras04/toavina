"""Vérifie le modèle Utilisateur et son rôle."""
import pytest

from apps.accounts.models import Utilisateur
from core.roles import Role


@pytest.mark.django_db
def test_utilisateur_cree_avec_role_visiteur_par_defaut():
    utilisateur = Utilisateur.objects.create_user(
        username="rakoto", password="motdepasse123"
    )
    assert utilisateur.role == Role.VISITEUR


@pytest.mark.django_db
def test_role_peut_etre_precise_a_la_creation():
    utilisateur = Utilisateur.objects.create_user(
        username="rasoa", password="motdepasse123", role=Role.COORDINATEUR
    )
    assert utilisateur.role == Role.COORDINATEUR


@pytest.mark.django_db
def test_creation_ia_autorisee_par_defaut():
    utilisateur = Utilisateur.objects.create_user(
        username="naivo", password="motdepasse123"
    )
    assert utilisateur.creation_ia_autorisee is True


@pytest.mark.django_db
def test_superutilisateur_recoit_le_role_super_admin():
    utilisateur = Utilisateur.objects.create_superuser(
        username="admin", password="motdepasse123", email="admin@effm.mg"
    )
    assert utilisateur.role == Role.SUPER_ADMIN


def test_sept_roles_definis():
    assert len(Role.choices) == 7


@pytest.mark.django_db
def test_representation_textuelle():
    utilisateur = Utilisateur.objects.create_user(
        username="rakoto", password="motdepasse123",
        first_name="Jean", last_name="Rakoto",
    )
    assert str(utilisateur) == "Jean Rakoto (Visiteur)"
