# Plan 1 — Socle technique et bénéficiaires (lots 0 et 1)

> **Pour les agents d'exécution :** SOUS-COMPÉTENCE REQUISE — utiliser
> `superpowers:subagent-driven-development` (recommandé) ou
> `superpowers:executing-plans` pour implémenter ce plan tâche par tâche.
> Les étapes utilisent la syntaxe à cases à cocher (`- [ ]`).

**Objectif :** obtenir une application Django qui démarre, authentifie sept rôles,
gère le référentiel géographique et permet la gestion complète des bénéficiaires
avec détection des doublons et masquage des données sensibles.

**Architecture :** quatre couches (présentation, services, données, orchestration IA).
Toute règle métier vit dans la couche services ; les vues n'en contiennent aucune.
Chaque fonction de service reçoit l'utilisateur comme premier paramètre et retourne
des données déjà filtrées selon ses droits — c'est ce qui rendra le cloisonnement
de l'IA structurel au plan 5.

**Pile technique :** Python 3.13, Django 5.2 LTS, SQLite en développement,
pytest + pytest-django.

**Spécification :** `docs/superpowers/specs/2026-09-04-ngo-management-system-design.md`

**Couverture :** lots 0 et 1 du §11 de la spécification. Sections implémentées :
§4 (couches), §5 (organisation), §6.3, §6.4 (référentiel, bénéficiaires),
§7 (MLD correspondant), §8.1 (identification des bénéficiaires), §9 (rôles).

---

## Contraintes globales

Ces contraintes s'appliquent à **toutes** les tâches sans être répétées.

- **Python 3.13.15**, **Django 5.2 LTS** (dernière version à support long terme
  compatible Python 3.13).
- **SQLite en développement, PostgreSQL en production** — aucune fonctionnalité
  propre à PostgreSQL. Pas de `ArrayField`, pas de `JSONField` spécifique
  PostgreSQL, pas de recherche plein texte native.
- **Nommage en français** pour tous les modèles et champs métier, conformément au
  MCD. Le code d'infrastructure (settings, tests) suit les conventions Django.
- **Signature imposée des services** : toute fonction de `services.py` prend
  `utilisateur` comme premier paramètre et retourne des données filtrées.
- **Aucune règle métier dans les vues.** Une vue appelle un service, rien de plus.
- **Aucune suppression physique** sur les données historisées — un indicateur
  d'archivage remplace la suppression.
- **Git est volontairement désactivé** à la demande de l'utilisateur. Les étapes
  de commit sont donc absentes de ce plan. Quand le versionnement sera activé,
  chaque tâche terminée constituera un commit naturel.

### Correspondance MLD → Django

Le MLD nomme les clés primaires `id_beneficiaire`, `id_village`, etc. Django crée
automatiquement une clé primaire nommée `id` et nomme les colonnes de clés
étrangères `<champ>_id`.

**On laisse Django faire.** `BENEFICIAIRE.id_beneficiaire` du MLD devient donc
`Beneficiaire.id` en base, et `→id_village` devient `beneficiaire.village_id`.
La correspondance est mécanique et sans ambiguïté ; la forcer produirait du bruit
sans bénéfice. Ce point est à mentionner dans le mémoire lors de la présentation
du passage MLD → MPD.

### Environnement (Windows, PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements/dev.txt
```

Toutes les commandes `pytest` de ce plan s'exécutent depuis la racine du projet,
environnement virtuel activé.

---

## Structure des fichiers

| Fichier | Responsabilité |
|---|---|
| `config/settings/base.py` | configuration commune aux environnements |
| `config/settings/dev.py` | SQLite, débogage, fournisseur IA factice |
| `config/settings/prod.py` | PostgreSQL, secrets externalisés |
| `core/models.py` | classes abstraites partagées |
| `core/roles.py` | énumération des rôles et matrice des droits |
| `core/permissions.py` | fonctions de vérification des droits |
| `core/exceptions.py` | exceptions métier |
| `apps/accounts/models.py` | modèle Utilisateur |
| `apps/geographie/models.py` | Pays, Région, District, Commune, Village |
| `apps/beneficiaires/models.py` | Beneficiaire |
| `apps/beneficiaires/services.py` | règles métier des bénéficiaires |
| `apps/beneficiaires/views.py` | vues, sans règle métier |

`geographie` est une application technique non listée au §11.1 du cahier des
charges. Elle porte le référentiel de la décision D1, qui n'appartient à aucun
module métier et sert bénéficiaires, forages, distributions et analyse des besoins.

---

## Tâche 1 : Socle du projet

**Fichiers :**
- Créer : `requirements/base.txt`, `requirements/dev.txt`, `requirements/prod.txt`
- Créer : `manage.py`, `config/__init__.py`, `config/urls.py`, `config/wsgi.py`
- Créer : `config/settings/__init__.py`, `config/settings/base.py`,
  `config/settings/dev.py`, `config/settings/prod.py`
- Créer : `pytest.ini`, `.env.example`
- Test : `config/tests/test_configuration.py`

**Interfaces :**
- Consomme : rien (tâche initiale)
- Produit : `config.settings.base` avec `INSTALLED_APPS`, `AUTH_USER_MODEL`
  défini à `accounts.Utilisateur` ; variable d'environnement
  `DJANGO_SETTINGS_MODULE=config.settings.dev` par défaut en développement.

> **Piège à éviter.** `AUTH_USER_MODEL` doit être défini **avant la toute
> première migration**. Le changer après coup impose de détruire la base et de
> recommencer les migrations. Il est donc posé dès cette tâche, alors même que
> l'application `accounts` n'existera qu'à la tâche 3.

- [ ] **Étape 1 : Créer l'arborescence et les fichiers de dépendances**

`requirements/base.txt` :

```
Django==5.2.*
python-dotenv==1.0.*
Pillow==11.*
```

`requirements/dev.txt` :

```
-r base.txt
pytest==8.*
pytest-django==4.*
```

`requirements/prod.txt` :

```
-r base.txt
psycopg[binary]==3.2.*
gunicorn==23.*
```

Pillow est requis dès maintenant : le champ `photo` du bénéficiaire (tâche 6) est
un `ImageField`, qui refuse de se valider sans Pillow.

- [ ] **Étape 2 : Écrire `config/settings/base.py`**

```python
"""Configuration commune à tous les environnements."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Défini avant la première migration : le modifier ensuite impose de
# reconstruire entièrement la base.
AUTH_USER_MODEL = "accounts.Utilisateur"

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Indian/Antananarivo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
```

- [ ] **Étape 3 : Écrire `config/settings/dev.py` et `config/settings/prod.py`**

`config/settings/dev.py` :

```python
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
```

`config/settings/prod.py` :

```python
"""Configuration de production : PostgreSQL, secrets externalisés."""
import os

from .base import *  # noqa: F403

DEBUG = False
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")

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
```

`.env.example` :

```
DJANGO_SECRET_KEY=
DJANGO_ALLOWED_HOSTS=
DB_NAME=ong_effm
DB_USER=
DB_PASSWORD=
DB_HOST=localhost
DB_PORT=5432
FOURNISSEUR_IA=factice
```

- [ ] **Étape 4 : Écrire `pytest.ini`, `manage.py`, `config/urls.py`, `config/wsgi.py`**

`pytest.ini` :

```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings.dev
python_files = test_*.py
testpaths = config core apps
```

`manage.py` :

```python
#!/usr/bin/env python
"""Utilitaire en ligne de commande de Django."""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
```

`config/urls.py` :

```python
from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
]
```

`config/wsgi.py` :

```python
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")
application = get_wsgi_application()
```

- [ ] **Étape 5 : Écrire le test de configuration**

`config/tests/test_configuration.py` :

```python
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
```

Créer aussi `config/tests/__init__.py` (fichier vide).

- [ ] **Étape 6 : Lancer les tests et vérifier l'échec**

```powershell
pytest config/tests/test_configuration.py -v
```

Attendu : ÉCHEC. Django refuse de démarrer avec
`AUTH_USER_MODEL refers to model 'accounts.Utilisateur' that has not been installed`.
C'est normal : l'application `accounts` n'existe qu'à la tâche 3.

- [ ] **Étape 7 : Créer l'application `core` minimale pour débloquer le démarrage**

```powershell
New-Item -ItemType Directory -Force core
New-Item -ItemType File core/__init__.py
New-Item -ItemType File core/models.py
```

`core/apps.py` :

```python
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
```

- [ ] **Étape 8 : Constater la dépendance et passer à la tâche 3**

Le test de configuration **ne peut pas passer** avant que l'application
`accounts` n'existe. C'est une dépendance réelle, pas un défaut du plan : elle
découle de la contrainte sur `AUTH_USER_MODEL`.

Marquer ce test comme le critère de validation de la **tâche 3**, et poursuivre
avec la tâche 2 (qui ne dépend pas de la base de données).

---

## Tâche 2 : Classes abstraites du noyau

**Fichiers :**
- Modifier : `core/models.py`
- Créer : `core/exceptions.py`
- Test : `core/tests/test_models.py`, `core/tests/__init__.py`

**Interfaces :**
- Consomme : rien
- Produit :
  - `core.models.Horodate` — abstrait, champs `date_creation` (auto à la
    création) et `date_modification` (auto à chaque sauvegarde)
  - `core.models.Archivable` — abstrait, champ booléen `archive` (défaut `False`)
    et gestionnaire `objects` filtrant les archivés, `tous` les incluant
  - `core.exceptions.PermissionRefusee(Exception)`
  - `core.exceptions.RegleMetierViolee(Exception)`

- [ ] **Étape 1 : Écrire les tests en échec**

`core/tests/test_models.py` :

```python
"""Vérifie le contrat des classes abstraites partagées."""
from core.models import Archivable, Horodate


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
```

- [ ] **Étape 2 : Lancer les tests et vérifier l'échec**

```powershell
pytest core/tests/test_models.py -v
```

Attendu : ÉCHEC avec `ImportError: cannot import name 'Horodate' from 'core.models'`.

- [ ] **Étape 3 : Écrire l'implémentation minimale**

`core/models.py` :

```python
"""Classes abstraites partagées par tous les modules métier."""
from django.db import models


class Horodate(models.Model):
    """Trace la création et la dernière modification d'un enregistrement."""

    date_creation = models.DateTimeField("date de création", auto_now_add=True)
    date_modification = models.DateTimeField("date de modification", auto_now=True)

    class Meta:
        abstract = True


class GestionnaireActifs(models.Manager):
    """Ne retourne que les enregistrements non archivés."""

    def get_queryset(self):
        return super().get_queryset().filter(archive=False)


class Archivable(models.Model):
    """Remplace la suppression physique par un archivage.

    La spécification (§8 du MPD) interdit la suppression des données
    historisées : une distribution effacée ferait disparaître la trace d'une
    aide réellement remise.
    """

    archive = models.BooleanField("archivé", default=False)

    objects = GestionnaireActifs()
    tous = models.Manager()

    class Meta:
        abstract = True
```

`core/exceptions.py` :

```python
"""Exceptions métier communes.

Elles sont distinctes des exceptions techniques : la couche présentation les
affiche en langage clair à l'utilisateur, tandis qu'une erreur technique est
journalisée et présentée de façon générique (§13 de la spécification).
"""


class PermissionRefusee(Exception):
    """L'utilisateur n'a pas le droit d'effectuer cette opération."""


class RegleMetierViolee(Exception):
    """L'opération contredit une règle de gestion de l'ONG."""
```

- [ ] **Étape 4 : Lancer les tests et vérifier le succès**

```powershell
pytest core/tests/test_models.py -v
```

Attendu : SUCCÈS, 6 tests passés.

---

## Tâche 3 : Modèle Utilisateur et rôles

**Fichiers :**
- Créer : `core/roles.py`
- Créer : `apps/__init__.py`, `apps/accounts/__init__.py`,
  `apps/accounts/apps.py`, `apps/accounts/models.py`, `apps/accounts/admin.py`
- Modifier : `config/settings/base.py` (ajouter `apps.accounts` à `INSTALLED_APPS`)
- Test : `apps/accounts/tests/test_models.py`, `apps/accounts/tests/__init__.py`

**Interfaces :**
- Consomme : `core.models.Horodate`
- Produit :
  - `core.roles.Role` — énumération de texte, valeurs : `SUPER_ADMIN`,
    `PRESIDENT`, `COORDINATEUR`, `COMPTABLE`, `RESPONSABLE_PROJET`,
    `VOLONTAIRE`, `VISITEUR`
  - `apps.accounts.models.Utilisateur` — hérite de `AbstractUser` et `Horodate`,
    champs supplémentaires `role` (défaut `Role.VISITEUR`), `telephone`,
    `creation_ia_autorisee` (booléen, défaut `True`)

- [ ] **Étape 1 : Écrire les tests en échec**

`apps/accounts/tests/test_models.py` :

```python
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
```

- [ ] **Étape 2 : Lancer les tests et vérifier l'échec**

```powershell
pytest apps/accounts/tests/test_models.py -v
```

Attendu : ÉCHEC avec `ModuleNotFoundError: No module named 'apps.accounts'`.

- [ ] **Étape 3 : Écrire `core/roles.py`**

```python
"""Rôles de l'ONG et leur libellé (§5 du cahier des charges)."""
from django.db import models


class Role(models.TextChoices):
    SUPER_ADMIN = "super_admin", "Super administrateur"
    PRESIDENT = "president", "Président"
    COORDINATEUR = "coordinateur", "Coordinateur"
    COMPTABLE = "comptable", "Comptable"
    RESPONSABLE_PROJET = "responsable_projet", "Responsable de projet"
    VOLONTAIRE = "volontaire", "Volontaire"
    VISITEUR = "visiteur", "Visiteur"
```

- [ ] **Étape 4 : Écrire `apps/accounts/models.py`**

```python
"""Modèle Utilisateur de l'ONG E.F.F.M."""
from django.contrib.auth.models import AbstractUser
from django.db import models

from core.models import Horodate
from core.roles import Role


class Utilisateur(AbstractUser, Horodate):
    """Utilisateur interne. Un utilisateur porte exactement un rôle (§5)."""

    role = models.CharField(
        "rôle", max_length=32, choices=Role.choices, default=Role.VISITEUR
    )
    telephone = models.CharField("téléphone", max_length=32, blank=True)
    creation_ia_autorisee = models.BooleanField(
        "création assistée par IA autorisée",
        default=True,
        help_text=(
            "Décoché, l'utilisateur peut interroger l'assistant mais ne peut "
            "plus lui demander de préparer des créations (§12)."
        ),
    )

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"

    def __str__(self):
        nom_complet = f"{self.first_name} {self.last_name}".strip()
        return f"{nom_complet or self.username} ({self.get_role_display()})"

    def save(self, *args, **kwargs):
        # Un superutilisateur Django est nécessairement super administrateur
        # métier : sans cela, il aurait tous les droits techniques et aucun
        # droit applicatif.
        if self.is_superuser:
            self.role = Role.SUPER_ADMIN
        super().save(*args, **kwargs)
```

`apps/accounts/apps.py` :

```python
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    label = "accounts"
    verbose_name = "Utilisateurs et rôles"
```

Le `label = "accounts"` est indispensable : sans lui, Django nomme
l'application `apps.accounts` et `AUTH_USER_MODEL = "accounts.Utilisateur"`
ne correspond plus.

- [ ] **Étape 5 : Déclarer l'application et créer les migrations**

Dans `config/settings/base.py`, ajouter à `INSTALLED_APPS` après `"core"` :

```python
    "apps.accounts",
```

Puis :

```powershell
python manage.py makemigrations accounts
python manage.py migrate
```

- [ ] **Étape 6 : Lancer les tests et vérifier le succès**

```powershell
pytest apps/accounts/tests/test_models.py config/tests/test_configuration.py -v
```

Attendu : SUCCÈS, 10 tests passés — les 6 de cette tâche et les 4 de la tâche 1,
désormais débloqués.

---

## Tâche 4 : Matrice des droits

**Fichiers :**
- Créer : `core/permissions.py`
- Test : `core/tests/test_permissions.py`

**Interfaces :**
- Consomme : `core.roles.Role`, `core.exceptions.PermissionRefusee`
- Produit :
  - `core.permissions.Module` — énumération de texte : `BENEFICIAIRES`,
    `DONNEES_SENSIBLES`, `PROJETS`, `DISTRIBUTIONS`, `FINANCES`, `DOCUMENTS`,
    `STATISTIQUES`, `UTILISATEURS`, `ASSISTANT_IA`, `ANALYSE_BESOINS`,
    `VALIDATION_IA`
  - `core.permissions.Acces` — `IntEnum` : `AUCUN=0`, `LECTURE=1`, `PROPRE=2`,
    `COMPLET=3`
  - `core.permissions.acces(utilisateur, module) -> Acces`
  - `core.permissions.peut_lire(utilisateur, module) -> bool`
  - `core.permissions.peut_ecrire(utilisateur, module) -> bool`
  - `core.permissions.perimetre_restreint(utilisateur, module) -> bool`
  - `core.permissions.exiger(utilisateur, module, minimum)` — lève
    `PermissionRefusee` si l'accès est insuffisant

- [ ] **Étape 1 : Écrire les tests en échec**

`core/tests/test_permissions.py` :

```python
"""Vérifie la matrice des droits du §9.1 de la spécification."""
import pytest

from core.exceptions import PermissionRefusee
from core.permissions import (
    Acces,
    Module,
    acces,
    exiger,
    perimetre_restreint,
    peut_ecrire,
    peut_lire,
)
from core.roles import Role


class UtilisateurFactice:
    """Substitut léger : la matrice ne dépend que du rôle, pas de la base."""

    def __init__(self, role):
        self.role = role


def test_super_admin_a_acces_complet_partout():
    utilisateur = UtilisateurFactice(Role.SUPER_ADMIN)
    for module in Module:
        assert acces(utilisateur, module) == Acces.COMPLET


def test_visiteur_n_a_acces_a_rien_en_interne():
    utilisateur = UtilisateurFactice(Role.VISITEUR)
    for module in Module:
        assert acces(utilisateur, module) == Acces.AUCUN


def test_comptable_n_accede_pas_aux_beneficiaires():
    """Principe de minimisation : le comptable travaille sur des montants."""
    utilisateur = UtilisateurFactice(Role.COMPTABLE)
    assert acces(utilisateur, Module.BENEFICIAIRES) == Acces.AUCUN
    assert peut_lire(utilisateur, Module.BENEFICIAIRES) is False


def test_comptable_gere_les_finances():
    utilisateur = UtilisateurFactice(Role.COMPTABLE)
    assert peut_ecrire(utilisateur, Module.FINANCES) is True


def test_coordinateur_ecrit_les_beneficiaires():
    utilisateur = UtilisateurFactice(Role.COORDINATEUR)
    assert peut_ecrire(utilisateur, Module.BENEFICIAIRES) is True


def test_coordinateur_lit_les_finances_sans_les_ecrire():
    utilisateur = UtilisateurFactice(Role.COORDINATEUR)
    assert peut_lire(utilisateur, Module.FINANCES) is True
    assert peut_ecrire(utilisateur, Module.FINANCES) is False


def test_responsable_projet_limite_a_son_perimetre():
    utilisateur = UtilisateurFactice(Role.RESPONSABLE_PROJET)
    assert peut_ecrire(utilisateur, Module.PROJETS) is True
    assert perimetre_restreint(utilisateur, Module.PROJETS) is True


def test_coordinateur_n_est_pas_restreint_sur_les_projets():
    utilisateur = UtilisateurFactice(Role.COORDINATEUR)
    assert perimetre_restreint(utilisateur, Module.PROJETS) is False


def test_seul_le_super_admin_gere_les_utilisateurs():
    for role in Role:
        utilisateur = UtilisateurFactice(role)
        attendu = role == Role.SUPER_ADMIN
        assert peut_ecrire(utilisateur, Module.UTILISATEURS) is attendu


def test_donnees_sensibles_reservees_a_trois_roles():
    """CIN et passeport : super admin, président, coordinateur (§9.1)."""
    autorises = {Role.SUPER_ADMIN, Role.PRESIDENT, Role.COORDINATEUR}
    for role in Role:
        utilisateur = UtilisateurFactice(role)
        lisible = peut_lire(utilisateur, Module.DONNEES_SENSIBLES)
        assert lisible is (role in autorises)


def test_volontaire_consulte_l_assistant_sans_creer():
    utilisateur = UtilisateurFactice(Role.VOLONTAIRE)
    assert peut_lire(utilisateur, Module.ASSISTANT_IA) is True
    assert perimetre_restreint(utilisateur, Module.ASSISTANT_IA) is True


def test_exiger_leve_une_exception_si_acces_insuffisant():
    utilisateur = UtilisateurFactice(Role.VOLONTAIRE)
    with pytest.raises(PermissionRefusee):
        exiger(utilisateur, Module.FINANCES, Acces.LECTURE)


def test_exiger_ne_leve_rien_si_acces_suffisant():
    utilisateur = UtilisateurFactice(Role.COORDINATEUR)
    exiger(utilisateur, Module.BENEFICIAIRES, Acces.COMPLET)


def test_utilisateur_anonyme_n_a_aucun_acces():
    class Anonyme:
        role = None

    for module in Module:
        assert acces(Anonyme(), module) == Acces.AUCUN
```

- [ ] **Étape 2 : Lancer les tests et vérifier l'échec**

```powershell
pytest core/tests/test_permissions.py -v
```

Attendu : ÉCHEC avec `ModuleNotFoundError: No module named 'core.permissions'`.

- [ ] **Étape 3 : Écrire `core/permissions.py`**

```python
"""Matrice des droits par rôle (§9 de la spécification).

Cette matrice est l'unique source de vérité des permissions. Les vues et les
outils de l'assistant IA la consultent tous les deux : c'est ce qui garantit
que l'IA ne peut pas accéder à davantage que son utilisateur (§9.3).
"""
from enum import IntEnum

from django.db import models

from core.exceptions import PermissionRefusee
from core.roles import Role


class Module(models.TextChoices):
    BENEFICIAIRES = "beneficiaires", "Bénéficiaires"
    DONNEES_SENSIBLES = "donnees_sensibles", "Données sensibles"
    PROJETS = "projets", "Projets et campagnes"
    DISTRIBUTIONS = "distributions", "Distributions"
    FINANCES = "finances", "Dons et finances"
    DOCUMENTS = "documents", "Documents"
    STATISTIQUES = "statistiques", "Statistiques et rapports"
    UTILISATEURS = "utilisateurs", "Utilisateurs"
    ASSISTANT_IA = "assistant_ia", "Assistant IA"
    ANALYSE_BESOINS = "analyse_besoins", "Analyse des besoins"
    VALIDATION_IA = "validation_ia", "Validation des propositions IA"


class Acces(IntEnum):
    """Niveaux d'accès, du plus faible au plus fort."""

    AUCUN = 0
    LECTURE = 1
    PROPRE = 2  # écriture limitée à ses propres objets
    COMPLET = 3


_A = Acces.AUCUN
_L = Acces.LECTURE
_P = Acces.PROPRE
_C = Acces.COMPLET

# Reproduit littéralement le tableau du §9.1 de la spécification.
MATRICE = {
    Role.SUPER_ADMIN: {module: _C for module in Module},
    Role.PRESIDENT: {
        Module.BENEFICIAIRES: _L,
        Module.DONNEES_SENSIBLES: _L,
        Module.PROJETS: _L,
        Module.DISTRIBUTIONS: _L,
        Module.FINANCES: _L,
        Module.DOCUMENTS: _L,
        Module.STATISTIQUES: _L,
        Module.UTILISATEURS: _L,
        Module.ASSISTANT_IA: _C,
        Module.ANALYSE_BESOINS: _C,
        Module.VALIDATION_IA: _C,
    },
    Role.COORDINATEUR: {
        Module.BENEFICIAIRES: _C,
        Module.DONNEES_SENSIBLES: _L,
        Module.PROJETS: _C,
        Module.DISTRIBUTIONS: _C,
        Module.FINANCES: _L,
        Module.DOCUMENTS: _C,
        Module.STATISTIQUES: _L,
        Module.UTILISATEURS: _A,
        Module.ASSISTANT_IA: _C,
        Module.ANALYSE_BESOINS: _C,
        Module.VALIDATION_IA: _C,
    },
    Role.COMPTABLE: {
        Module.BENEFICIAIRES: _A,
        Module.DONNEES_SENSIBLES: _A,
        Module.PROJETS: _L,
        Module.DISTRIBUTIONS: _A,
        Module.FINANCES: _C,
        Module.DOCUMENTS: _P,
        Module.STATISTIQUES: _L,
        Module.UTILISATEURS: _A,
        Module.ASSISTANT_IA: _C,
        Module.ANALYSE_BESOINS: _L,
        Module.VALIDATION_IA: _P,
    },
    Role.RESPONSABLE_PROJET: {
        Module.BENEFICIAIRES: _L,
        Module.DONNEES_SENSIBLES: _A,
        Module.PROJETS: _P,
        Module.DISTRIBUTIONS: _P,
        Module.FINANCES: _L,
        Module.DOCUMENTS: _P,
        Module.STATISTIQUES: _P,
        Module.UTILISATEURS: _A,
        Module.ASSISTANT_IA: _C,
        Module.ANALYSE_BESOINS: _L,
        Module.VALIDATION_IA: _P,
    },
    Role.VOLONTAIRE: {
        Module.BENEFICIAIRES: _L,
        Module.DONNEES_SENSIBLES: _A,
        Module.PROJETS: _A,
        Module.DISTRIBUTIONS: _P,
        Module.FINANCES: _A,
        Module.DOCUMENTS: _A,
        Module.STATISTIQUES: _A,
        Module.UTILISATEURS: _A,
        Module.ASSISTANT_IA: _P,
        Module.ANALYSE_BESOINS: _A,
        Module.VALIDATION_IA: _A,
    },
    Role.VISITEUR: {module: _A for module in Module},
}


def acces(utilisateur, module):
    """Retourne le niveau d'accès de l'utilisateur sur le module."""
    role = getattr(utilisateur, "role", None)
    if role is None:
        return Acces.AUCUN
    return MATRICE.get(role, {}).get(module, Acces.AUCUN)


def peut_lire(utilisateur, module):
    return acces(utilisateur, module) >= Acces.LECTURE


def peut_ecrire(utilisateur, module):
    return acces(utilisateur, module) >= Acces.PROPRE


def perimetre_restreint(utilisateur, module):
    """Vrai si l'utilisateur ne voit que ses propres objets sur ce module."""
    return acces(utilisateur, module) == Acces.PROPRE


def exiger(utilisateur, module, minimum):
    """Lève PermissionRefusee si l'accès est inférieur au minimum requis."""
    if acces(utilisateur, module) < minimum:
        raise PermissionRefusee(
            f"Accès refusé au module « {Module(module).label} »."
        )
```

- [ ] **Étape 4 : Lancer les tests et vérifier le succès**

```powershell
pytest core/tests/test_permissions.py -v
```

Attendu : SUCCÈS, 14 tests passés.

---

## Tâche 5 : Référentiel géographique

**Fichiers :**
- Créer : `apps/geographie/__init__.py`, `apps/geographie/apps.py`,
  `apps/geographie/models.py`, `apps/geographie/admin.py`
- Modifier : `config/settings/base.py` (`INSTALLED_APPS`)
- Test : `apps/geographie/tests/test_models.py`, `apps/geographie/tests/__init__.py`

**Interfaces :**
- Consomme : `core.models.Horodate`
- Produit : `apps.geographie.models.Pays`, `Region`, `District`, `Commune`,
  `Village`. Chaque niveau expose `libelle` et une clé étrangère vers son parent
  (`Region.pays`, `District.region`, `Commune.district`, `Village.commune`).
  `Village` expose en plus `latitude` et `longitude` (décimaux, facultatifs) et
  la propriété `region` qui remonte la hiérarchie.

- [ ] **Étape 1 : Écrire les tests en échec**

`apps/geographie/tests/test_models.py` :

```python
"""Vérifie la hiérarchie géographique de la décision D1."""
import pytest
from django.db import IntegrityError

from apps.geographie.models import Commune, District, Pays, Region, Village


@pytest.fixture
def village(db):
    pays = Pays.objects.create(libelle="Madagascar", code_iso="MG")
    region = Region.objects.create(libelle="Menabe", pays=pays)
    district = District.objects.create(libelle="Morondava", region=region)
    commune = Commune.objects.create(libelle="Morondava", district=district)
    return Village.objects.create(libelle="Betania", commune=commune)


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
```

- [ ] **Étape 2 : Lancer les tests et vérifier l'échec**

```powershell
pytest apps/geographie/tests/test_models.py -v
```

Attendu : ÉCHEC avec `ModuleNotFoundError: No module named 'apps.geographie'`.

- [ ] **Étape 3 : Écrire `apps/geographie/models.py`**

```python
"""Référentiel géographique (décision D1 de la spécification).

Le cahier des charges plaçait village, commune, district et région comme
champs texte de la fiche bénéficiaire. En texte libre, l'agrégation par zone
exigée au §8.1 devient impossible : ces niveaux sont donc des entités.
"""
from django.db import models

from core.models import Horodate


class Pays(Horodate):
    libelle = models.CharField("libellé", max_length=100, unique=True)
    code_iso = models.CharField("code ISO", max_length=3, unique=True)

    class Meta:
        verbose_name = "pays"
        verbose_name_plural = "pays"
        ordering = ["libelle"]

    def __str__(self):
        return self.libelle


class Region(Horodate):
    libelle = models.CharField("libellé", max_length=100)
    pays = models.ForeignKey(
        Pays, on_delete=models.PROTECT, related_name="regions", verbose_name="pays"
    )

    class Meta:
        verbose_name = "région"
        verbose_name_plural = "régions"
        ordering = ["libelle"]
        constraints = [
            models.UniqueConstraint(
                fields=["libelle", "pays"], name="region_unique_dans_pays"
            )
        ]

    def __str__(self):
        return self.libelle


class District(Horodate):
    libelle = models.CharField("libellé", max_length=100)
    region = models.ForeignKey(
        Region,
        on_delete=models.PROTECT,
        related_name="districts",
        verbose_name="région",
    )

    class Meta:
        verbose_name = "district"
        verbose_name_plural = "districts"
        ordering = ["libelle"]
        constraints = [
            models.UniqueConstraint(
                fields=["libelle", "region"], name="district_unique_dans_region"
            )
        ]

    def __str__(self):
        return self.libelle


class Commune(Horodate):
    libelle = models.CharField("libellé", max_length=100)
    district = models.ForeignKey(
        District,
        on_delete=models.PROTECT,
        related_name="communes",
        verbose_name="district",
    )

    class Meta:
        verbose_name = "commune"
        verbose_name_plural = "communes"
        ordering = ["libelle"]
        constraints = [
            models.UniqueConstraint(
                fields=["libelle", "district"], name="commune_unique_dans_district"
            )
        ]

    def __str__(self):
        return self.libelle


class Village(Horodate):
    libelle = models.CharField("libellé", max_length=100)
    commune = models.ForeignKey(
        Commune,
        on_delete=models.PROTECT,
        related_name="villages",
        verbose_name="commune",
    )
    latitude = models.DecimalField(
        "latitude", max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        "longitude", max_digits=9, decimal_places=6, null=True, blank=True
    )

    class Meta:
        verbose_name = "village"
        verbose_name_plural = "villages"
        ordering = ["libelle"]
        constraints = [
            models.UniqueConstraint(
                fields=["libelle", "commune"], name="village_unique_dans_commune"
            )
        ]

    def __str__(self):
        return f"{self.libelle} ({self.commune.district.libelle})"

    @property
    def region(self):
        """Remonte la hiérarchie jusqu'à la région."""
        return self.commune.district.region
```

Le `on_delete=models.PROTECT` est délibéré : supprimer une commune qui porte
des villages, donc des bénéficiaires et des distributions, effacerait de
l'historique. La spécification l'interdit (§8 du MPD).

`apps/geographie/apps.py` :

```python
from django.apps import AppConfig


class GeographieConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.geographie"
    label = "geographie"
    verbose_name = "Référentiel géographique"
```

- [ ] **Étape 4 : Déclarer l'application et migrer**

Ajouter `"apps.geographie",` à `INSTALLED_APPS` dans `config/settings/base.py`,
puis :

```powershell
python manage.py makemigrations geographie
python manage.py migrate
```

- [ ] **Étape 5 : Lancer les tests et vérifier le succès**

```powershell
pytest apps/geographie/tests/test_models.py -v
```

Attendu : SUCCÈS, 6 tests passés.

---

## Tâche 6 : Modèle Bénéficiaire

**Fichiers :**
- Créer : `apps/beneficiaires/__init__.py`, `apps/beneficiaires/apps.py`,
  `apps/beneficiaires/models.py`
- Modifier : `config/settings/base.py` (`INSTALLED_APPS`)
- Test : `apps/beneficiaires/tests/test_models.py`,
  `apps/beneficiaires/tests/__init__.py`

**Interfaces :**
- Consomme : `core.models.Horodate`, `core.models.Archivable`,
  `apps.geographie.models.Village`
- Produit : `apps.beneficiaires.models.Beneficiaire` avec tous les champs du
  §4.1 du cahier des charges, la clé étrangère `village`, et une contrainte
  d'unicité partielle sur `numero_cin`.

- [ ] **Étape 1 : Écrire les tests en échec**

`apps/beneficiaires/tests/test_models.py` :

```python
"""Vérifie le modèle Beneficiaire et l'unicité partielle du CIN (§8.1)."""
import pytest
from django.db import IntegrityError

from apps.beneficiaires.models import Beneficiaire, Sexe, StatutBeneficiaire
from apps.geographie.models import Commune, District, Pays, Region, Village


@pytest.fixture
def village(db):
    pays = Pays.objects.create(libelle="Madagascar", code_iso="MG")
    region = Region.objects.create(libelle="Menabe", pays=pays)
    district = District.objects.create(libelle="Morondava", region=region)
    commune = Commune.objects.create(libelle="Morondava", district=district)
    return Village.objects.create(libelle="Betania", commune=commune)


@pytest.fixture
def beneficiaire(village):
    return Beneficiaire.objects.create(
        nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN,
        date_naissance="1985-04-12", village=village,
    )


def test_creation_avec_champs_minimaux(beneficiaire):
    assert beneficiaire.nom == "Rakoto"
    assert beneficiaire.statut == StatutBeneficiaire.ACTIF


def test_representation_textuelle(beneficiaire):
    assert str(beneficiaire) == "Rakoto Jean"


def test_non_archive_par_defaut(beneficiaire):
    assert beneficiaire.archive is False


def test_gestionnaire_masque_les_archives(beneficiaire):
    beneficiaire.archive = True
    beneficiaire.save()
    assert Beneficiaire.objects.count() == 0
    assert Beneficiaire.tous.count() == 1


@pytest.mark.django_db
def test_cin_unique_lorsqu_il_est_renseigne(village):
    Beneficiaire.objects.create(
        nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN, village=village,
        numero_cin="101234567890",
    )
    with pytest.raises(IntegrityError):
        Beneficiaire.objects.create(
            nom="Rabe", prenom="Paul", sexe=Sexe.MASCULIN, village=village,
            numero_cin="101234567890",
        )


@pytest.mark.django_db
def test_plusieurs_beneficiaires_sans_cin_autorises(village):
    """Tous les bénéficiaires ne disposent pas d'une carte d'identité (§8.1)."""
    Beneficiaire.objects.create(
        nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN, village=village,
    )
    Beneficiaire.objects.create(
        nom="Rabe", prenom="Paul", sexe=Sexe.MASCULIN, village=village,
    )
    assert Beneficiaire.objects.count() == 2


def test_acces_a_la_region_par_le_village(beneficiaire):
    assert beneficiaire.village.region.libelle == "Menabe"
```

- [ ] **Étape 2 : Lancer les tests et vérifier l'échec**

```powershell
pytest apps/beneficiaires/tests/test_models.py -v
```

Attendu : ÉCHEC avec `ModuleNotFoundError: No module named 'apps.beneficiaires'`.

- [ ] **Étape 3 : Écrire `apps/beneficiaires/models.py`**

```python
"""Fiche bénéficiaire (§4.1 du cahier des charges)."""
from django.db import models

from apps.geographie.models import Village
from core.models import Archivable, Horodate


class Sexe(models.TextChoices):
    MASCULIN = "M", "Masculin"
    FEMININ = "F", "Féminin"


class SituationFamiliale(models.TextChoices):
    CELIBATAIRE = "celibataire", "Célibataire"
    MARIE = "marie", "Marié(e)"
    VEUF = "veuf", "Veuf(ve)"
    DIVORCE = "divorce", "Divorcé(e)"


class StatutBeneficiaire(models.TextChoices):
    ACTIF = "actif", "Actif"
    INACTIF = "inactif", "Inactif"
    DECEDE = "decede", "Décédé(e)"
    DEMENAGE = "demenage", "Déménagé(e)"


class Beneficiaire(Horodate, Archivable):
    nom = models.CharField("nom", max_length=100)
    prenom = models.CharField("prénom", max_length=100)
    sexe = models.CharField("sexe", max_length=1, choices=Sexe.choices)
    date_naissance = models.DateField("date de naissance", null=True, blank=True)

    telephone = models.CharField("téléphone", max_length=32, blank=True)
    adresse = models.CharField("adresse", max_length=255, blank=True)
    village = models.ForeignKey(
        Village,
        on_delete=models.PROTECT,
        related_name="beneficiaires",
        verbose_name="village",
    )

    profession = models.CharField("profession", max_length=100, blank=True)
    nombre_enfants = models.PositiveSmallIntegerField("nombre d'enfants", default=0)
    situation_familiale = models.CharField(
        "situation familiale",
        max_length=20,
        choices=SituationFamiliale.choices,
        blank=True,
    )
    revenu = models.DecimalField(
        "revenu mensuel", max_digits=12, decimal_places=2, null=True, blank=True
    )

    photo = models.ImageField(
        "photo", upload_to="beneficiaires/photos/", blank=True
    )
    numero_cin = models.CharField(
        "numéro CIN", max_length=32, blank=True, null=True, db_index=True
    )
    numero_passeport = models.CharField(
        "numéro de passeport", max_length=32, blank=True
    )

    statut = models.CharField(
        "statut",
        max_length=20,
        choices=StatutBeneficiaire.choices,
        default=StatutBeneficiaire.ACTIF,
    )

    class Meta:
        verbose_name = "bénéficiaire"
        verbose_name_plural = "bénéficiaires"
        ordering = ["nom", "prenom"]
        indexes = [
            models.Index(fields=["nom", "prenom"], name="beneficiaire_nom_prenom"),
        ]
        constraints = [
            # Unicité partielle : le CIN identifie de façon fiable, mais tous
            # les bénéficiaires n'en possèdent pas (§8.1).
            models.UniqueConstraint(
                fields=["numero_cin"],
                condition=models.Q(numero_cin__isnull=False),
                name="cin_unique_si_renseigne",
            ),
        ]

    def __str__(self):
        return f"{self.nom} {self.prenom}"
```

`numero_cin` est déclaré `blank=True, null=True` : la contrainte partielle
s'appuie sur `NULL`, alors qu'une chaîne vide serait une valeur comme une autre
et déclencherait un conflit d'unicité au deuxième bénéficiaire sans CIN. Le
service de la tâche 7 convertit donc systématiquement la chaîne vide en `NULL`.

`apps/beneficiaires/apps.py` :

```python
from django.apps import AppConfig


class BeneficiairesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.beneficiaires"
    label = "beneficiaires"
    verbose_name = "Bénéficiaires"
```

- [ ] **Étape 4 : Déclarer l'application et migrer**

Ajouter `"apps.beneficiaires",` à `INSTALLED_APPS`, puis :

```powershell
python manage.py makemigrations beneficiaires
python manage.py migrate
```

- [ ] **Étape 5 : Lancer les tests et vérifier le succès**

```powershell
pytest apps/beneficiaires/tests/test_models.py -v
```

Attendu : SUCCÈS, 7 tests passés.

---

## Tâche 7 : Couche de services des bénéficiaires

C'est la tâche centrale du plan : elle établit le contrat que **toutes** les
couches de services suivantes respecteront, et sur lequel reposera le
cloisonnement de l'assistant IA au plan 5.

**Fichiers :**
- Créer : `apps/beneficiaires/services.py`
- Test : `apps/beneficiaires/tests/test_services.py`

**Interfaces :**
- Consomme : `core.permissions`, `core.exceptions`,
  `apps.beneficiaires.models.Beneficiaire`
- Produit :
  - `lister_beneficiaires(utilisateur, recherche="", village=None) -> QuerySet`
  - `obtenir_beneficiaire(utilisateur, identifiant) -> Beneficiaire`
  - `rechercher_doublons(utilisateur, nom, prenom, date_naissance, village, exclure=None) -> QuerySet`
  - `creer_beneficiaire(utilisateur, **donnees) -> Beneficiaire`
  - `modifier_beneficiaire(utilisateur, identifiant, **donnees) -> Beneficiaire`
  - `archiver_beneficiaire(utilisateur, identifiant) -> Beneficiaire`
  - `champs_visibles(utilisateur) -> set[str]`

- [ ] **Étape 1 : Écrire les tests en échec**

`apps/beneficiaires/tests/test_services.py` :

```python
"""Vérifie les règles métier et le filtrage par rôle des bénéficiaires."""
import pytest

from apps.accounts.models import Utilisateur
from apps.beneficiaires.models import Beneficiaire, Sexe
from apps.beneficiaires.services import (
    archiver_beneficiaire,
    champs_visibles,
    creer_beneficiaire,
    lister_beneficiaires,
    rechercher_doublons,
)
from apps.geographie.models import Commune, District, Pays, Region, Village
from core.exceptions import PermissionRefusee
from core.roles import Role


@pytest.fixture
def village(db):
    pays = Pays.objects.create(libelle="Madagascar", code_iso="MG")
    region = Region.objects.create(libelle="Menabe", pays=pays)
    district = District.objects.create(libelle="Morondava", region=region)
    commune = Commune.objects.create(libelle="Morondava", district=district)
    return Village.objects.create(libelle="Betania", commune=commune)


def creer_utilisateur(role, nom="agent"):
    return Utilisateur.objects.create_user(
        username=f"{nom}_{role}", password="motdepasse123", role=role
    )


@pytest.fixture
def coordinateur(db):
    return creer_utilisateur(Role.COORDINATEUR)


@pytest.fixture
def comptable(db):
    return creer_utilisateur(Role.COMPTABLE)


@pytest.fixture
def volontaire(db):
    return creer_utilisateur(Role.VOLONTAIRE)


def test_coordinateur_cree_un_beneficiaire(coordinateur, village):
    beneficiaire = creer_beneficiaire(
        coordinateur, nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN,
        village=village,
    )
    assert beneficiaire.pk is not None


def test_volontaire_ne_peut_pas_creer(volontaire, village):
    with pytest.raises(PermissionRefusee):
        creer_beneficiaire(
            volontaire, nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN,
            village=village,
        )


def test_comptable_ne_peut_pas_lister(comptable, village):
    with pytest.raises(PermissionRefusee):
        lister_beneficiaires(comptable)


def test_volontaire_peut_lister(volontaire, coordinateur, village):
    creer_beneficiaire(
        coordinateur, nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN,
        village=village,
    )
    assert lister_beneficiaires(volontaire).count() == 1


def test_cin_vide_converti_en_null(coordinateur, village):
    """Deux bénéficiaires sans CIN ne doivent pas entrer en conflit (§8.1)."""
    creer_beneficiaire(
        coordinateur, nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN,
        village=village, numero_cin="",
    )
    creer_beneficiaire(
        coordinateur, nom="Rabe", prenom="Paul", sexe=Sexe.MASCULIN,
        village=village, numero_cin="",
    )
    assert Beneficiaire.objects.filter(numero_cin__isnull=True).count() == 2


def test_doublon_detecte_sur_nom_prenom_naissance_village(coordinateur, village):
    creer_beneficiaire(
        coordinateur, nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN,
        date_naissance="1985-04-12", village=village,
    )
    doublons = rechercher_doublons(
        coordinateur, nom="RAKOTO", prenom="jean",
        date_naissance="1985-04-12", village=village,
    )
    assert doublons.count() == 1


def test_pas_de_doublon_dans_un_autre_village(coordinateur, village):
    creer_beneficiaire(
        coordinateur, nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN,
        date_naissance="1985-04-12", village=village,
    )
    autre = Village.objects.create(libelle="Ampasy", commune=village.commune)
    doublons = rechercher_doublons(
        coordinateur, nom="Rakoto", prenom="Jean",
        date_naissance="1985-04-12", village=autre,
    )
    assert doublons.count() == 0


def test_doublon_avertit_sans_bloquer(coordinateur, village):
    """Un homonyme réel dans un même village reste possible (§8.1)."""
    creer_beneficiaire(
        coordinateur, nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN,
        date_naissance="1985-04-12", village=village,
    )
    second = creer_beneficiaire(
        coordinateur, nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN,
        date_naissance="1985-04-12", village=village,
    )
    assert second.pk is not None


def test_recherche_par_nom(coordinateur, village):
    creer_beneficiaire(
        coordinateur, nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN,
        village=village,
    )
    creer_beneficiaire(
        coordinateur, nom="Rabe", prenom="Paul", sexe=Sexe.MASCULIN,
        village=village,
    )
    assert lister_beneficiaires(coordinateur, recherche="rakoto").count() == 1


def test_archivage_retire_de_la_liste(coordinateur, village):
    beneficiaire = creer_beneficiaire(
        coordinateur, nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN,
        village=village,
    )
    archiver_beneficiaire(coordinateur, beneficiaire.pk)
    assert lister_beneficiaires(coordinateur).count() == 0
    assert Beneficiaire.tous.count() == 1


def test_donnees_sensibles_visibles_par_le_coordinateur(coordinateur):
    assert "numero_cin" in champs_visibles(coordinateur)


def test_donnees_sensibles_masquees_au_volontaire(volontaire):
    champs = champs_visibles(volontaire)
    assert "numero_cin" not in champs
    assert "numero_passeport" not in champs
    assert "nom" in champs
```

- [ ] **Étape 2 : Lancer les tests et vérifier l'échec**

```powershell
pytest apps/beneficiaires/tests/test_services.py -v
```

Attendu : ÉCHEC avec
`ImportError: cannot import name 'creer_beneficiaire' from 'apps.beneficiaires.services'`.

- [ ] **Étape 3 : Écrire `apps/beneficiaires/services.py`**

```python
"""Règles métier des bénéficiaires.

Toute écriture passe par ce module. Les vues et, à partir du plan 5, les outils
de l'assistant IA appellent ces mêmes fonctions : une règle écrite ici
s'applique donc aux deux (§3 de la spécification).

Chaque fonction reçoit l'utilisateur en premier paramètre et retourne des
données déjà filtrées selon ses droits.
"""
from django.db.models import Q

from apps.beneficiaires.models import Beneficiaire
from core.permissions import Acces, Module, exiger, peut_lire

# Champs jamais exposés à un utilisateur sans accès aux données sensibles (§12).
CHAMPS_SENSIBLES = {"numero_cin", "numero_passeport", "revenu"}

CHAMPS_COURANTS = {
    "id", "nom", "prenom", "sexe", "date_naissance", "telephone", "adresse",
    "village", "profession", "nombre_enfants", "situation_familiale", "photo",
    "statut",
}


def champs_visibles(utilisateur):
    """Retourne les champs que cet utilisateur a le droit de consulter."""
    champs = set(CHAMPS_COURANTS)
    if peut_lire(utilisateur, Module.DONNEES_SENSIBLES):
        champs |= CHAMPS_SENSIBLES
    return champs


def lister_beneficiaires(utilisateur, recherche="", village=None):
    """Liste les bénéficiaires actifs visibles par l'utilisateur."""
    exiger(utilisateur, Module.BENEFICIAIRES, Acces.LECTURE)

    resultats = Beneficiaire.objects.select_related("village")

    if recherche:
        resultats = resultats.filter(
            Q(nom__icontains=recherche) | Q(prenom__icontains=recherche)
        )
    if village is not None:
        resultats = resultats.filter(village=village)

    return resultats


def obtenir_beneficiaire(utilisateur, identifiant):
    """Retourne un bénéficiaire actif, ou lève Beneficiaire.DoesNotExist."""
    exiger(utilisateur, Module.BENEFICIAIRES, Acces.LECTURE)
    return Beneficiaire.objects.select_related("village").get(pk=identifiant)


def rechercher_doublons(utilisateur, nom, prenom, date_naissance, village,
                        exclure=None):
    """Cherche des bénéficiaires ressemblant à ceux qu'on s'apprête à créer.

    La recherche est restreinte au même village : deux personnes portant les
    mêmes nom, prénom et date de naissance dans deux villages éloignés sont
    presque certainement deux personnes distinctes (§8.1).

    Le résultat est un avertissement destiné à l'opérateur, jamais un blocage :
    l'homonymie réelle existe et ne doit pas empêcher un enregistrement.
    """
    exiger(utilisateur, Module.BENEFICIAIRES, Acces.LECTURE)

    resultats = Beneficiaire.objects.filter(
        nom__iexact=nom.strip(),
        prenom__iexact=prenom.strip(),
        village=village,
    )
    if date_naissance:
        resultats = resultats.filter(date_naissance=date_naissance)
    if exclure is not None:
        resultats = resultats.exclude(pk=exclure)

    return resultats


def _normaliser_cin(donnees):
    """Convertit un CIN vide en NULL.

    La contrainte d'unicité partielle porte sur les valeurs non nulles. Une
    chaîne vide serait une valeur comme une autre, et le deuxième bénéficiaire
    sans carte d'identité déclencherait un conflit.
    """
    if not donnees.get("numero_cin"):
        donnees["numero_cin"] = None
    return donnees


def creer_beneficiaire(utilisateur, **donnees):
    """Crée un bénéficiaire après vérification des droits."""
    exiger(utilisateur, Module.BENEFICIAIRES, Acces.PROPRE)
    return Beneficiaire.objects.create(**_normaliser_cin(donnees))


def modifier_beneficiaire(utilisateur, identifiant, **donnees):
    """Modifie un bénéficiaire existant."""
    exiger(utilisateur, Module.BENEFICIAIRES, Acces.PROPRE)

    beneficiaire = Beneficiaire.objects.get(pk=identifiant)
    for champ, valeur in _normaliser_cin(donnees).items():
        setattr(beneficiaire, champ, valeur)
    beneficiaire.save()
    return beneficiaire


def archiver_beneficiaire(utilisateur, identifiant):
    """Archive un bénéficiaire sans le supprimer.

    La suppression physique est interdite : elle effacerait l'historique des
    aides reçues (§8 du MPD).
    """
    exiger(utilisateur, Module.BENEFICIAIRES, Acces.COMPLET)

    beneficiaire = Beneficiaire.tous.get(pk=identifiant)
    beneficiaire.archive = True
    beneficiaire.save(update_fields=["archive", "date_modification"])
    return beneficiaire
```

- [ ] **Étape 4 : Lancer les tests et vérifier le succès**

```powershell
pytest apps/beneficiaires/tests/test_services.py -v
```

Attendu : SUCCÈS, 12 tests passés.

- [ ] **Étape 5 : Lancer l'ensemble des tests**

```powershell
pytest -v
```

Attendu : SUCCÈS, **55 tests** passés, aucun échec. Détail du compte :

| Fichier | Tests |
|---|:--:|
| `config/tests/test_configuration.py` | 4 |
| `core/tests/test_models.py` | 6 |
| `core/tests/test_permissions.py` | 14 |
| `apps/accounts/tests/test_models.py` | 6 |
| `apps/geographie/tests/test_models.py` | 6 |
| `apps/beneficiaires/tests/test_models.py` | 7 |
| `apps/beneficiaires/tests/test_services.py` | 12 |
| **Total** | **55** |

---

## Tâche 8 : Vues et formulaires des bénéficiaires

**Fichiers :**
- Créer : `apps/beneficiaires/forms.py`, `apps/beneficiaires/views.py`,
  `apps/beneficiaires/urls.py`
- Créer : `templates/base.html`,
  `templates/beneficiaires/liste.html`,
  `templates/beneficiaires/detail.html`,
  `templates/beneficiaires/formulaire.html`
- Modifier : `config/urls.py`
- Test : `apps/beneficiaires/tests/test_views.py`

**Interfaces :**
- Consomme : toutes les fonctions de `apps.beneficiaires.services`
- Produit : les routes nommées `beneficiaires:liste`, `beneficiaires:detail`,
  `beneficiaires:creer`, `beneficiaires:modifier`

**Règle impérative :** ces vues ne contiennent aucune règle métier. Elles
appellent un service, traduisent `PermissionRefusee` en réponse HTTP 403, et
transmettent le résultat au gabarit.

- [ ] **Étape 1 : Écrire les tests en échec**

`apps/beneficiaires/tests/test_views.py` :

```python
"""Vérifie que les vues appliquent bien les droits de la couche services."""
import pytest
from django.urls import reverse

from apps.accounts.models import Utilisateur
from apps.beneficiaires.models import Beneficiaire, Sexe
from apps.geographie.models import Commune, District, Pays, Region, Village
from core.roles import Role


@pytest.fixture
def village(db):
    pays = Pays.objects.create(libelle="Madagascar", code_iso="MG")
    region = Region.objects.create(libelle="Menabe", pays=pays)
    district = District.objects.create(libelle="Morondava", region=region)
    commune = Commune.objects.create(libelle="Morondava", district=district)
    return Village.objects.create(libelle="Betania", commune=commune)


def connecter(client, role):
    utilisateur = Utilisateur.objects.create_user(
        username=f"agent_{role}", password="motdepasse123", role=role
    )
    client.force_login(utilisateur)
    return utilisateur


def test_liste_refusee_a_l_utilisateur_anonyme(client, db):
    reponse = client.get(reverse("beneficiaires:liste"))
    assert reponse.status_code in (302, 403)


def test_liste_accessible_au_coordinateur(client, village):
    connecter(client, Role.COORDINATEUR)
    reponse = client.get(reverse("beneficiaires:liste"))
    assert reponse.status_code == 200


def test_liste_refusee_au_comptable(client, village):
    connecter(client, Role.COMPTABLE)
    reponse = client.get(reverse("beneficiaires:liste"))
    assert reponse.status_code == 403


def test_creation_refusee_au_volontaire(client, village):
    connecter(client, Role.VOLONTAIRE)
    reponse = client.post(
        reverse("beneficiaires:creer"),
        {"nom": "Rakoto", "prenom": "Jean", "sexe": Sexe.MASCULIN,
         "village": village.pk, "nombre_enfants": 0, "statut": "actif"},
    )
    assert reponse.status_code == 403
    assert Beneficiaire.objects.count() == 0


def test_creation_reussie_par_le_coordinateur(client, village):
    connecter(client, Role.COORDINATEUR)
    reponse = client.post(
        reverse("beneficiaires:creer"),
        {"nom": "Rakoto", "prenom": "Jean", "sexe": Sexe.MASCULIN,
         "village": village.pk, "nombre_enfants": 0, "statut": "actif"},
    )
    assert reponse.status_code == 302
    assert Beneficiaire.objects.count() == 1


def test_modification_par_le_coordinateur(client, village):
    connecter(client, Role.COORDINATEUR)
    beneficiaire = Beneficiaire.objects.create(
        nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN, village=village,
    )
    reponse = client.post(
        reverse("beneficiaires:modifier", args=[beneficiaire.pk]),
        {"nom": "Rakotoarisoa", "prenom": "Jean", "sexe": Sexe.MASCULIN,
         "village": village.pk, "nombre_enfants": 2, "statut": "actif"},
    )
    assert reponse.status_code == 302
    beneficiaire.refresh_from_db()
    assert beneficiaire.nom == "Rakotoarisoa"
    assert beneficiaire.nombre_enfants == 2


def test_modification_refusee_au_volontaire(client, village):
    connecter(client, Role.VOLONTAIRE)
    beneficiaire = Beneficiaire.objects.create(
        nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN, village=village,
    )
    reponse = client.post(
        reverse("beneficiaires:modifier", args=[beneficiaire.pk]),
        {"nom": "Modifie", "prenom": "Jean", "sexe": Sexe.MASCULIN,
         "village": village.pk, "nombre_enfants": 0, "statut": "actif"},
    )
    assert reponse.status_code == 403
    beneficiaire.refresh_from_db()
    assert beneficiaire.nom == "Rakoto"


def test_cin_masque_au_volontaire(client, village):
    beneficiaire = Beneficiaire.objects.create(
        nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN, village=village,
        numero_cin="101234567890",
    )
    connecter(client, Role.VOLONTAIRE)

    reponse = client.get(
        reverse("beneficiaires:detail", args=[beneficiaire.pk])
    )
    assert reponse.status_code == 200
    assert b"101234567890" not in reponse.content


def test_cin_visible_par_le_coordinateur(client, village):
    connecter(client, Role.COORDINATEUR)
    beneficiaire = Beneficiaire.objects.create(
        nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN, village=village,
        numero_cin="101234567890",
    )
    reponse = client.get(
        reverse("beneficiaires:detail", args=[beneficiaire.pk])
    )
    assert b"101234567890" in reponse.content
```

- [ ] **Étape 2 : Lancer les tests et vérifier l'échec**

```powershell
pytest apps/beneficiaires/tests/test_views.py -v
```

Attendu : ÉCHEC avec
`django.urls.exceptions.NoReverseMatch: 'beneficiaires' is not a registered namespace`.

- [ ] **Étape 3 : Écrire `apps/beneficiaires/forms.py`**

```python
"""Formulaires des bénéficiaires.

Le formulaire ne valide que la forme des données. Les règles métier — droits,
doublons, normalisation du CIN — appartiennent à la couche services.
"""
from django import forms

from apps.beneficiaires.models import Beneficiaire


class FormulaireBeneficiaire(forms.ModelForm):
    class Meta:
        model = Beneficiaire
        fields = [
            "nom", "prenom", "sexe", "date_naissance", "telephone", "adresse",
            "village", "profession", "nombre_enfants", "situation_familiale",
            "revenu", "photo", "numero_cin", "numero_passeport", "statut",
        ]
        widgets = {
            "date_naissance": forms.DateInput(attrs={"type": "date"}),
            "adresse": forms.TextInput(),
        }
```

- [ ] **Étape 4 : Écrire `apps/beneficiaires/views.py`**

```python
"""Vues des bénéficiaires.

Aucune règle métier ici : chaque vue appelle un service et traduit
PermissionRefusee en réponse HTTP 403 (§4 de la spécification).
"""
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render

from apps.beneficiaires.forms import FormulaireBeneficiaire
from apps.beneficiaires.services import (
    champs_visibles,
    creer_beneficiaire,
    lister_beneficiaires,
    modifier_beneficiaire,
    obtenir_beneficiaire,
    rechercher_doublons,
)
from core.exceptions import PermissionRefusee


@login_required
def liste(requete):
    recherche = requete.GET.get("recherche", "")
    try:
        beneficiaires = lister_beneficiaires(requete.user, recherche=recherche)
    except PermissionRefusee as erreur:
        raise PermissionDenied(str(erreur))

    return render(
        requete,
        "beneficiaires/liste.html",
        {"beneficiaires": beneficiaires, "recherche": recherche},
    )


@login_required
def detail(requete, identifiant):
    try:
        beneficiaire = obtenir_beneficiaire(requete.user, identifiant)
    except PermissionRefusee as erreur:
        raise PermissionDenied(str(erreur))

    return render(
        requete,
        "beneficiaires/detail.html",
        {
            "beneficiaire": beneficiaire,
            "champs_visibles": champs_visibles(requete.user),
        },
    )


@login_required
def creer(requete):
    formulaire = FormulaireBeneficiaire(requete.POST or None, requete.FILES or None)
    doublons = []

    if requete.method == "POST" and formulaire.is_valid():
        donnees = formulaire.cleaned_data
        try:
            doublons = list(
                rechercher_doublons(
                    requete.user,
                    nom=donnees["nom"],
                    prenom=donnees["prenom"],
                    date_naissance=donnees.get("date_naissance"),
                    village=donnees["village"],
                )
            )
            if doublons and requete.POST.get("confirmer") != "1":
                # Avertissement, non blocage : l'opérateur tranche (§8.1).
                return render(
                    requete,
                    "beneficiaires/formulaire.html",
                    {"formulaire": formulaire, "doublons": doublons},
                )

            beneficiaire = creer_beneficiaire(requete.user, **donnees)
        except PermissionRefusee as erreur:
            raise PermissionDenied(str(erreur))

        return redirect("beneficiaires:detail", identifiant=beneficiaire.pk)

    return render(
        requete,
        "beneficiaires/formulaire.html",
        {"formulaire": formulaire, "doublons": doublons},
    )


@login_required
def modifier(requete, identifiant):
    try:
        beneficiaire = obtenir_beneficiaire(requete.user, identifiant)
    except PermissionRefusee as erreur:
        raise PermissionDenied(str(erreur))

    formulaire = FormulaireBeneficiaire(
        requete.POST or None, requete.FILES or None, instance=beneficiaire
    )

    if requete.method == "POST" and formulaire.is_valid():
        try:
            modifier_beneficiaire(
                requete.user, identifiant, **formulaire.cleaned_data
            )
        except PermissionRefusee as erreur:
            raise PermissionDenied(str(erreur))

        return redirect("beneficiaires:detail", identifiant=identifiant)

    return render(
        requete,
        "beneficiaires/formulaire.html",
        {"formulaire": formulaire, "beneficiaire": beneficiaire, "doublons": []},
    )
```

Le formulaire est lié à l'instance existante afin que les champs s'affichent
pré-remplis, mais l'enregistrement passe par `modifier_beneficiaire` et non par
`formulaire.save()` : c'est le service qui porte le contrôle des droits et la
normalisation du CIN. Appeler `save()` sur le formulaire court-circuiterait la
couche métier, ce que le §4 de la spécification interdit.

Ajouter `modifier_beneficiaire` aux imports depuis `apps.beneficiaires.services`
en tête du fichier.

- [ ] **Étape 5 : Écrire les routes**

`apps/beneficiaires/urls.py` :

```python
from django.urls import path

from apps.beneficiaires import views

app_name = "beneficiaires"

urlpatterns = [
    path("", views.liste, name="liste"),
    path("nouveau/", views.creer, name="creer"),
    path("<int:identifiant>/", views.detail, name="detail"),
    path("<int:identifiant>/modifier/", views.modifier, name="modifier"),
]
```

Dans `config/urls.py` :

```python
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("comptes/", include("django.contrib.auth.urls")),
    path("beneficiaires/", include("apps.beneficiaires.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

- [ ] **Étape 6 : Écrire les gabarits**

`templates/base.html` :

```html
{% raw %}<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block titre %}ONG E.F.F.M{% endblock %}</title>
</head>
<body>
  <header>
    <a href="/">ONG E.F.F.M</a>
    {% if user.is_authenticated %}
      <span>{{ user }}</span>
    {% endif %}
  </header>
  <main>
    {% block contenu %}{% endblock %}
  </main>
</body>
</html>{% endraw %}
```

`templates/beneficiaires/liste.html` :

```html
{% raw %}{% extends "base.html" %}
{% block titre %}Bénéficiaires{% endblock %}
{% block contenu %}
  <h1>Bénéficiaires</h1>

  <form method="get">
    <input type="search" name="recherche" value="{{ recherche }}"
           placeholder="Nom ou prénom">
    <button type="submit">Rechercher</button>
  </form>

  <a href="{% url 'beneficiaires:creer' %}">Nouveau bénéficiaire</a>

  <table>
    <thead>
      <tr><th>Nom</th><th>Prénom</th><th>Village</th><th>Statut</th></tr>
    </thead>
    <tbody>
      {% for beneficiaire in beneficiaires %}
        <tr>
          <td>
            <a href="{% url 'beneficiaires:detail' beneficiaire.pk %}">
              {{ beneficiaire.nom }}
            </a>
          </td>
          <td>{{ beneficiaire.prenom }}</td>
          <td>{{ beneficiaire.village }}</td>
          <td>{{ beneficiaire.get_statut_display }}</td>
        </tr>
      {% empty %}
        <tr><td colspan="4">Aucun bénéficiaire enregistré.</td></tr>
      {% endfor %}
    </tbody>
  </table>
{% endblock %}{% endraw %}
```

`templates/beneficiaires/detail.html` :

```html
{% raw %}{% extends "base.html" %}
{% block titre %}{{ beneficiaire }}{% endblock %}
{% block contenu %}
  <h1>{{ beneficiaire }}</h1>

  <dl>
    <dt>Sexe</dt><dd>{{ beneficiaire.get_sexe_display }}</dd>
    <dt>Date de naissance</dt><dd>{{ beneficiaire.date_naissance|default:"—" }}</dd>
    <dt>Village</dt><dd>{{ beneficiaire.village }}</dd>
    <dt>Profession</dt><dd>{{ beneficiaire.profession|default:"—" }}</dd>
    <dt>Nombre d'enfants</dt><dd>{{ beneficiaire.nombre_enfants }}</dd>
    <dt>Statut</dt><dd>{{ beneficiaire.get_statut_display }}</dd>

    {% if "numero_cin" in champs_visibles %}
      <dt>Numéro CIN</dt><dd>{{ beneficiaire.numero_cin|default:"—" }}</dd>
    {% endif %}
    {% if "numero_passeport" in champs_visibles %}
      <dt>Passeport</dt><dd>{{ beneficiaire.numero_passeport|default:"—" }}</dd>
    {% endif %}
    {% if "revenu" in champs_visibles %}
      <dt>Revenu</dt><dd>{{ beneficiaire.revenu|default:"—" }}</dd>
    {% endif %}
  </dl>

  <a href="{% url 'beneficiaires:modifier' beneficiaire.pk %}">Modifier</a>
  <a href="{% url 'beneficiaires:liste' %}">Retour à la liste</a>
{% endblock %}{% endraw %}
```

`templates/beneficiaires/formulaire.html` — ce gabarit sert à la fois la
création et la modification ; la variable `beneficiaire` n'est fournie que par
la vue `modifier` :

```html
{% raw %}{% extends "base.html" %}
{% block titre %}
  {% if beneficiaire %}Modifier {{ beneficiaire }}{% else %}Nouveau bénéficiaire{% endif %}
{% endblock %}
{% block contenu %}
  <h1>
    {% if beneficiaire %}
      Modifier {{ beneficiaire }}
    {% else %}
      Nouveau bénéficiaire
    {% endif %}
  </h1>

  {% if doublons %}
    <div role="alert">
      <p>
        Un bénéficiaire portant les mêmes nom, prénom et date de naissance
        existe déjà dans ce village :
      </p>
      <ul>
        {% for doublon in doublons %}
          <li>
            <a href="{% url 'beneficiaires:detail' doublon.pk %}">{{ doublon }}</a>
          </li>
        {% endfor %}
      </ul>
      <p>Vérifiez qu'il ne s'agit pas de la même personne avant de continuer.</p>
    </div>
  {% endif %}

  <form method="post" enctype="multipart/form-data">
    {% csrf_token %}
    {{ formulaire.as_p }}
    {% if doublons %}
      <input type="hidden" name="confirmer" value="1">
      <button type="submit">Enregistrer malgré tout</button>
    {% else %}
      <button type="submit">Enregistrer</button>
    {% endif %}
  </form>
{% endblock %}{% endraw %}
```

> Les balises `{% raw %}{% raw %}{% endraw %}` de ce plan ne font pas partie des
> gabarits : elles empêchent seulement le présent document d'interpréter la
> syntaxe Django. Les recopier **sans** ces balises.

- [ ] **Étape 7 : Lancer les tests et vérifier le succès**

```powershell
pytest apps/beneficiaires/tests/test_views.py -v
```

Attendu : SUCCÈS, 9 tests passés.

- [ ] **Étape 8 : Lancer la totalité de la suite**

```powershell
pytest -v
```

Attendu : SUCCÈS, **64 tests** passés (55 après la tâche 7, plus les 9 de
celle-ci), aucun échec.

- [ ] **Étape 9 : Vérifier manuellement dans le navigateur**

```powershell
python manage.py createsuperuser
python manage.py runserver
```

Se connecter sur `http://127.0.0.1:8000/admin/`, créer un pays, une région, un
district, une commune et un village. Puis ouvrir
`http://127.0.0.1:8000/beneficiaires/` et créer un bénéficiaire.

Vérifier de visu : la liste s'affiche, la recherche fonctionne, la création
aboutit, et l'enregistrement d'un homonyme déclenche l'avertissement de doublon
sans bloquer.

---

## Critères d'achèvement du plan 1

- [ ] `pytest -v` passe intégralement, sans échec ni test ignoré
- [ ] `python manage.py check` ne signale aucun problème
- [ ] `python manage.py makemigrations --check --dry-run` confirme qu'aucune
      migration n'est en attente
- [ ] Un coordinateur peut créer, consulter, modifier et rechercher un bénéficiaire
- [ ] Un comptable reçoit une erreur 403 sur la liste des bénéficiaires
- [ ] Un volontaire consulte une fiche sans voir le numéro CIN
- [ ] L'enregistrement d'un homonyme dans le même village déclenche un
      avertissement sans blocage

---

## Ce que ce plan ne couvre pas

Ces éléments relèvent des plans suivants et ne doivent pas être anticipés :

| Élément | Plan |
|---|---|
| Campagnes, distributions, règle anti-doublon des aides | 2 |
| Vérification de l'historique des aides reçues par un bénéficiaire | 2 |
| Projets, dons, partenaires | 2 et 3 |
| Tableau de bord et statistiques | 4 |
| Assistant IA et propositions | 5 |
| Analyse des besoins | 6 |
| Site public et mise en forme graphique | 7 |

Les gabarits de la tâche 8 sont volontairement dépouillés : la mise en forme
graphique appartient au plan 7. Les habiller maintenant serait du travail à
refaire.
