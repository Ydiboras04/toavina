"""Configuration de production : PostgreSQL, secrets externalisés."""
import os

from .base import *  # noqa: F403

DEBUG = False
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
ALLOWED_HOSTS = [
    hote.strip()
    for hote in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
    if hote.strip()
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["DB_NAME"],
        "USER": os.environ["DB_USER"],
        "PASSWORD": os.environ["DB_PASSWORD"],
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}

FOURNISSEUR_IA = os.environ.get("FOURNISSEUR_IA", "factice")

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
