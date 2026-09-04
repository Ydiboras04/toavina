"""Fixtures partagées entre les suites de tests.

Avant l'introduction de ce fichier, la même hiérarchie géographique (Pays,
Région, District, Commune, Village) était recréée à l'identique dans quatre
fichiers de test, avec un risque de divergence silencieuse entre les copies —
c'est d'ailleurs ce qui s'est produit : seule la copie de
`apps/geographie/tests/test_models.py` donnait à la commune un libellé
(« Analaiva ») distinct de celui du district (« Morondava »), ce qui est
nécessaire pour qu'un test affichant les deux puisse réellement distinguer un
rendu correct d'une confusion entre les deux niveaux. Les autres copies
portaient une commune nommée « Morondava », identique au district.
"""
import pytest

from apps.accounts.models import Utilisateur
from apps.geographie.models import Commune, District, Pays, Region, Village


@pytest.fixture
def village(db):
    """Hiérarchie géographique complète (Pays > Région > District > Commune >
    Village), avec un village prêt à l'emploi.

    Le libellé de la commune (« Analaiva ») est délibérément distinct de celui
    du district (« Morondava ») : voir la note de module ci-dessus.
    """
    pays = Pays.objects.create(libelle="Madagascar", code_iso="MG")
    region = Region.objects.create(libelle="Menabe", pays=pays)
    district = District.objects.create(libelle="Morondava", region=region)
    commune = Commune.objects.create(libelle="Analaiva", district=district)
    return Village.objects.create(libelle="Betania", commune=commune)


@pytest.fixture
def creer_utilisateur(db):
    """Fabrique d'utilisateurs par rôle.

    Retourne une fonction `role -> Utilisateur`, avec un mot de passe connu
    (utilisable pour se connecter, y compris via le client de test).
    """

    def _creer(role, nom="agent"):
        return Utilisateur.objects.create_user(
            username=f"{nom}_{role}", password="motdepasse123", role=role
        )

    return _creer


@pytest.fixture
def type_action(db):
    from apps.projets.models import TypeAction

    return TypeAction.objects.create(libelle="Distribution alimentaire")


@pytest.fixture
def beneficiaire(db, village):
    from apps.beneficiaires.models import Beneficiaire

    return Beneficiaire.objects.create(
        nom="Rakoto", prenom="Jean", sexe="M", village=village
    )
