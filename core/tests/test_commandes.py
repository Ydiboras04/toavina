"""Vérifie la commande de chargement des données de démonstration."""
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from apps.beneficiaires.models import Beneficiaire
from apps.campagnes.models import CampagneAide, DistributionAide
from apps.geographie.models import Village
from apps.projets.models import Projet, TypeAction
from core.roles import Role

# La commande refuse de s'exécuter avec le débogage désactivé, et les tests
# Django forcent précisément `DEBUG = False`. On le réactive donc ici : c'est
# ce refus lui-même qu'un test vérifie plus bas.
en_developpement = override_settings(DEBUG=True)


@pytest.mark.django_db
def test_la_commande_charge_un_jeu_complet():
    with en_developpement:
        call_command("donnees_demo", verbosity=0)

    assert Village.objects.count() == 4
    assert TypeAction.objects.count() == 12
    assert Projet.objects.count() == 1
    assert CampagneAide.objects.count() == 1
    assert Beneficiaire.objects.count() == 5
    assert DistributionAide.objects.count() == 3


@pytest.mark.django_db
def test_la_commande_cree_un_compte_par_role():
    from django.contrib.auth import get_user_model

    with en_developpement:
        call_command("donnees_demo", verbosity=0)

    roles = set(get_user_model().objects.values_list("role", flat=True))
    assert roles == {
        Role.SUPER_ADMIN,
        Role.PRESIDENT,
        Role.COORDINATEUR,
        Role.COMPTABLE,
        Role.RESPONSABLE_PROJET,
        Role.VOLONTAIRE,
    }


@pytest.mark.django_db
def test_relancer_la_commande_ne_duplique_rien():
    """Elle doit pouvoir servir à recharger un jeu propre sans tout casser."""
    with en_developpement:
        call_command("donnees_demo", verbosity=0)
        call_command("donnees_demo", verbosity=0)

    assert Beneficiaire.objects.count() == 5
    assert DistributionAide.objects.count() == 3
    assert TypeAction.objects.count() == 12


@pytest.mark.django_db
def test_l_option_vider_repart_d_un_etat_propre():
    with en_developpement:
        call_command("donnees_demo", verbosity=0)
        call_command("donnees_demo", "--vider", verbosity=0)

    assert Beneficiaire.objects.count() == 5
    assert DistributionAide.objects.count() == 3


@pytest.mark.django_db
def test_deux_beneficiaires_restent_a_servir():
    """Le jeu laisse de quoi essayer une saisie depuis l'interface."""
    with en_developpement:
        call_command("donnees_demo", verbosity=0)

    servis = DistributionAide.objects.values_list("beneficiaire_id", flat=True)
    assert Beneficiaire.objects.exclude(pk__in=servis).count() == 2


@pytest.mark.django_db
def test_la_commande_refuse_de_s_executer_hors_developpement():
    """Elle crée des comptes dont le mot de passe est écrit dans le code."""
    with override_settings(DEBUG=False):
        with pytest.raises(CommandError):
            call_command("donnees_demo", verbosity=0)
