"""Configuration dédiée à l'exécution de la suite de tests.

Hérite de `dev.py` (même base de données SQLite, gérée par pytest-django qui
crée sa propre base de test) mais accélère le hachage des mots de passe.

Pourquoi : Django utilise par défaut PBKDF2 à un million d'itérations, soit
environ 0,88 seconde par utilisateur créé. C'est un coût voulu : c'est une
protection contre les attaques par force brute hors ligne sur des mots de
passe utilisateurs réels. Mais la fixture `creer_utilisateur` (voir
`conftest.py`) est appelée des centaines de fois dans la suite, toujours
avec le même mot de passe fixe ("motdepasse123"), connu de quiconque lit le
code — il n'y a rien à protéger ici, seulement du temps à gagner.

ATTENTION, LECTEUR : le hachage rapide ci-dessous n'est PAS une faiblesse de
sécurité du projet. Il n'a aucun effet en production, ni même en
développement normal (`manage.py runserver`) : ce module n'est référencé
que par `pytest.ini` (DJANGO_SETTINGS_MODULE = config.settings.test).
Ni `dev.py` ni `prod.py` n'importent ce fichier — il n'existe aucun chemin
par lequel MD5PasswordHasher pourrait se retrouver actif en production.
"""
from .dev import *  # noqa: F403

# Hachage rapide (mais faible) réservé aux tests — voir l'avertissement
# ci-dessus. Ne jamais copier cette ligne dans dev.py ou prod.py.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]
