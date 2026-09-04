"""Vérifie le contrat des classes abstraites partagées."""
import pytest

from core.models import Archivable, Campagne, Horodate


class CampagneConcrete(Campagne):
    """Sous-classe concrète de Campagne pour tester clean().

    Campagne étant abstraite, il faut une sous-classe concrète pour instancier
    et exercer sa méthode clean(). app_label la rattache à l'application core
    existante afin qu'aucune migration ne soit générée.
    """

    class Meta:
        app_label = "core"


def test_horodate_est_abstrait():
    assert Horodate._meta.abstract


def test_horodate_declare_les_deux_champs():
    champs = {champ.name for champ in Horodate._meta.get_fields()}
    assert champs == {"date_creation", "date_modification"}


def test_date_creation_remplie_automatiquement():
    champ = Horodate._meta.get_field("date_creation")
    assert champ.auto_now_add is True


def test_date_modification_remplie_a_chaque_sauvegarde():
    champ = Horodate._meta.get_field("date_modification")
    assert champ.auto_now is True


def test_archivable_est_abstrait():
    assert Archivable._meta.abstract


def test_archive_est_faux_par_defaut():
    champ = Archivable._meta.get_field("archive")
    assert champ.default is False


def test_saisie_par_est_abstrait():
    from core.models import SaisiPar

    assert SaisiPar._meta.abstract


def test_saisie_par_declare_un_seul_champ():
    from core.models import SaisiPar

    champs = {champ.name for champ in SaisiPar._meta.get_fields()}
    assert champs == {"saisie_par"}


def test_saisie_par_protege_contre_la_suppression():
    """Supprimer un utilisateur effacerait la trace de qui a saisi quoi."""
    from django.db import models as djmodels

    from core.models import SaisiPar

    champ = SaisiPar._meta.get_field("saisie_par")
    assert champ.remote_field.on_delete is djmodels.PROTECT


def test_campagne_est_abstraite():
    from core.models import Campagne

    assert Campagne._meta.abstract


def test_campagne_porte_le_tronc_commun():
    from core.models import Campagne

    champs = {champ.name for champ in Campagne._meta.get_fields()}
    assert champs == {
        "code", "libelle", "annee", "budget", "date_debut", "date_fin", "etat",
    }


def test_campagne_est_planifiee_par_defaut():
    from core.models import Campagne, EtatCampagne

    assert Campagne._meta.get_field("etat").default == EtatCampagne.PLANIFIEE


def test_quatre_etats_de_campagne():
    from core.models import EtatCampagne

    assert len(EtatCampagne.choices) == 4


def test_distribution_est_abstraite():
    from core.models import Distribution

    assert Distribution._meta.abstract


def test_distribution_porte_le_tronc_commun():
    from core.models import Distribution

    champs = {champ.name for champ in Distribution._meta.get_fields()}
    assert champs == {"date_distribution", "quantite", "unite", "observation"}


def test_budget_de_campagne_refuse_le_negatif():
    from django.core.validators import MinValueValidator

    from core.models import Campagne

    champ = Campagne._meta.get_field("budget")
    assert any(isinstance(v, MinValueValidator) for v in champ.validators)


def test_campagne_clean_refuse_date_fin_anterieure_a_debut():
    """Une campagne avec date_fin < date_debut lève ValidationError."""
    from datetime import date

    from django.core.exceptions import ValidationError

    # Instancier avec date_fin antérieure à date_debut
    campagne = CampagneConcrete(
        code="TEST",
        libelle="Test",
        annee=2026,
        budget=1000,
        date_debut=date(2026, 9, 10),
        date_fin=date(2026, 9, 4),
        etat="planifiee",
    )

    with pytest.raises(ValidationError):
        campagne.clean()


def test_campagne_clean_accepte_date_fin_posterieure():
    """Une campagne avec date_fin >= date_debut passe la validation."""
    from datetime import date

    # Instancier avec date_fin postérieure à date_debut
    campagne = CampagneConcrete(
        code="TEST",
        libelle="Test",
        annee=2026,
        budget=1000,
        date_debut=date(2026, 9, 4),
        date_fin=date(2026, 9, 10),
        etat="planifiee",
    )

    # Ne doit pas lever d'exception
    campagne.clean()


def test_campagne_clean_accepte_date_fin_absente():
    """Une campagne sans date_fin passe la validation."""
    from datetime import date

    # Instancier sans date_fin
    campagne = CampagneConcrete(
        code="TEST",
        libelle="Test",
        annee=2026,
        budget=1000,
        date_debut=date(2026, 9, 4),
        date_fin=None,
        etat="planifiee",
    )

    # Ne doit pas lever d'exception
    campagne.clean()


def test_quantite_de_distribution_refuse_le_zero():
    """La quantité d'une distribution doit être strictement positive."""
    from decimal import Decimal

    from django.core.validators import MinValueValidator

    from core.models import Distribution

    champ = Distribution._meta.get_field("quantite")
    # Vérifier que le validateur est MinValueValidator(Decimal("0.01"))
    assert any(
        isinstance(v, MinValueValidator) and v.limit_value == Decimal("0.01")
        for v in champ.validators
    )


def test_budget_de_campagne_accepte_le_zero():
    """Le budget d'une campagne peut être zéro."""
    from django.core.validators import MinValueValidator

    from core.models import Campagne

    champ = Campagne._meta.get_field("budget")
    # Vérifier que le validateur accepte zéro (MinValueValidator(0))
    assert any(
        isinstance(v, MinValueValidator) and v.limit_value == 0
        for v in champ.validators
    )
