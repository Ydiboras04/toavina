"""Vérifie les primitives partagées par toutes les couches de services."""
import pytest
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError

from apps.beneficiaires.models import Beneficiaire
from core.exceptions import Introuvable, RegleMetierViolee
from core.permissions import Module
from core.roles import Role
from core.services import (
    appliquer_validation,
    champs_visibles,
    obtenir_ou_introuvable,
    valider_champs,
)

AUTORISES = frozenset({"nom", "prenom"})


def test_valider_champs_accepte_les_cles_autorisees():
    valider_champs({"nom": "Rakoto", "prenom": "Jean"}, AUTORISES)


def test_valider_champs_accepte_un_dictionnaire_vide():
    valider_champs({}, AUTORISES)


def test_valider_champs_refuse_une_cle_inconnue():
    with pytest.raises(RegleMetierViolee) as erreur:
        valider_champs({"nom": "Rakoto", "archive": True}, AUTORISES)
    assert "archive" in str(erreur.value)


@pytest.mark.django_db
def test_obtenir_ou_introuvable_retourne_l_instance(village):
    beneficiaire = Beneficiaire.objects.create(
        nom="Rakoto", prenom="Jean", sexe="M", village=village
    )
    trouve = obtenir_ou_introuvable(Beneficiaire.objects, pk=beneficiaire.pk)
    assert trouve.pk == beneficiaire.pk


@pytest.mark.django_db
def test_obtenir_ou_introuvable_leve_introuvable(village):
    with pytest.raises(Introuvable):
        obtenir_ou_introuvable(Beneficiaire.objects, pk=999999)


@pytest.mark.django_db
def test_obtenir_ou_introuvable_ne_laisse_pas_fuir_doesnotexist(village):
    """Aucune exception de l'ORM ne doit franchir la frontière du service."""
    try:
        obtenir_ou_introuvable(Beneficiaire.objects, pk=999999)
    except Beneficiaire.DoesNotExist:  # pragma: no cover
        pytest.fail("DoesNotExist a fui hors du service")
    except Introuvable:
        pass


@pytest.mark.django_db
def test_obtenir_ou_introuvable_convertit_plusieurs_resultats_en_regle_metier_violee(
    village,
):
    """Un critère qui ne garantit pas l'unicité ne doit pas laisser fuir
    `MultipleObjectsReturned` : plusieurs résultats là où un seul est attendu
    révèle une incohérence des données, pas une absence."""
    Beneficiaire.objects.create(
        nom="Rakoto", prenom="Jean", sexe="M", village=village
    )
    Beneficiaire.objects.create(
        nom="Rakoto", prenom="Paul", sexe="M", village=village
    )
    try:
        obtenir_ou_introuvable(Beneficiaire.objects, nom="Rakoto")
    except Beneficiaire.MultipleObjectsReturned:  # pragma: no cover
        pytest.fail("MultipleObjectsReturned a fui hors du service")
    except RegleMetierViolee:
        pass


@pytest.mark.django_db
def test_appliquer_validation_refuse_une_valeur_hors_choix(village):
    beneficiaire = Beneficiaire(
        nom="Rakoto", prenom="Jean", sexe="ZZZ", village=village
    )
    with pytest.raises(RegleMetierViolee):
        appliquer_validation(beneficiaire)


@pytest.mark.django_db
def test_appliquer_validation_laisse_passer_une_instance_valide(village):
    beneficiaire = Beneficiaire(
        nom="Rakoto", prenom="Jean", sexe="M", village=village
    )
    appliquer_validation(beneficiaire)


@pytest.mark.django_db
def test_appliquer_validation_nomme_le_champ_en_erreur(village):
    """Une erreur rattachée à un champ précis garde son préfixe."""
    beneficiaire = Beneficiaire(
        nom="Rakoto", prenom="Jean", sexe="ZZZ", village=village
    )
    with pytest.raises(RegleMetierViolee) as erreur:
        appliquer_validation(beneficiaire)
    assert "sexe" in str(erreur.value)


class _InstanceAvecErreurTransversale:
    """Simule une instance dont `clean()` produit une erreur non rattachée à
    un champ précis (le cas `NON_FIELD_ERRORS` de Django) — par exemple « la
    quantité distribuée dépasse le stock ». `Projet.clean()` et
    `Campagne.clean()` lèvent aujourd'hui ce genre d'erreur, et le chemin réel
    est couvert de bout en bout par les tests des projets et des campagnes :
    cette doublure sert un autre objectif, isoler le traitement du
    dictionnaire d'erreurs par `appliquer_validation` et le tester sans base
    de données, sans passer par un vrai `full_clean()` de modèle.
    """

    def full_clean(self):
        raise ValidationError(
            {NON_FIELD_ERRORS: ["La quantité distribuée dépasse le stock disponible."]}
        )


def test_appliquer_validation_ne_prefixe_pas_une_erreur_transversale():
    """Une erreur `NON_FIELD_ERRORS` ne doit pas exposer la clé technique
    « __all__ » à l'opérateur."""
    with pytest.raises(RegleMetierViolee) as erreur:
        appliquer_validation(_InstanceAvecErreurTransversale())
    assert "__all__" not in str(erreur.value)
    assert "La quantité distribuée dépasse le stock disponible." in str(erreur.value)


@pytest.mark.django_db
def test_champs_visibles_ajoute_les_sensibles_si_le_role_y_a_droit(
    creer_utilisateur,
):
    coordinateur = creer_utilisateur(Role.COORDINATEUR)
    champs = champs_visibles(coordinateur, {"nom"}, {"numero_cin"})
    assert champs == {"nom", "numero_cin"}


@pytest.mark.django_db
def test_champs_visibles_masque_les_sensibles_sinon(creer_utilisateur):
    volontaire = creer_utilisateur(Role.VOLONTAIRE)
    champs = champs_visibles(volontaire, {"nom"}, {"numero_cin"})
    assert champs == {"nom"}
