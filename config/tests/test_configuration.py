"""Vérifie que la configuration respecte les contraintes de la spécification."""
from django.conf import settings


def test_developpement_utilise_sqlite():
    assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3"


def test_modele_utilisateur_personnalise_declare():
    assert settings.AUTH_USER_MODEL == "accounts.Utilisateur"


def test_langue_et_fuseau_conformes():
    assert settings.LANGUAGE_CODE == "fr-fr"
    assert settings.TIME_ZONE == "Indian/Antananarivo"


def test_fournisseur_ia_factice_par_defaut():
    assert settings.FOURNISSEUR_IA == "factice"
