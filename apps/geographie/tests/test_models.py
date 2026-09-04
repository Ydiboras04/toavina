"""Vérifie la hiérarchie géographique de la décision D1."""
import pytest
from django.db import IntegrityError

from apps.geographie.models import Commune, Village

# La fixture `village` est définie dans le conftest.py à la racine du projet.


def test_hierarchie_complete(village):
    assert village.commune.district.region.pays.libelle == "Madagascar"


def test_village_remonte_a_sa_region(village):
    assert village.region.libelle == "Menabe"


def test_representation_textuelle(village):
    assert str(village) == "Betania (Morondava)"


@pytest.mark.django_db
def test_deux_villages_homonymes_interdits_dans_la_meme_commune(village):
    with pytest.raises(IntegrityError):
        Village.objects.create(libelle="Betania", commune=village.commune)


@pytest.mark.django_db
def test_deux_villages_homonymes_autorises_dans_des_communes_differentes(village):
    autre = Commune.objects.create(
        libelle="Bemanonga", district=village.commune.district
    )
    Village.objects.create(libelle="Betania", commune=autre)
    assert Village.objects.filter(libelle="Betania").count() == 2


@pytest.mark.django_db
def test_coordonnees_facultatives(village):
    assert village.latitude is None
    assert village.longitude is None
