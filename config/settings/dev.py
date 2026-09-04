"""Configuration de développement : SQLite, débogage actif."""
from .base import *  # noqa: F403

DEBUG = True
SECRET_KEY = "cle-de-developpement-non-secrete"
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
    }
}

# Fournisseur de modèle de langage factice tant qu'aucune clé n'est disponible
# (§10.3 de la spécification).
FOURNISSEUR_IA = "factice"
