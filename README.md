# Système de gestion de l'ONG E.F.F.M

Application web de gestion des opérations humanitaires et sociales de l'ONG
E.F.F.M : suivi des bénéficiaires, des projets, des campagnes d'aide et des
distributions, avec prévention des doublons.

Projet de fin d'études — Master 2 MIAGE.

**Pile technique** : Python 3.13, Django 5.2 LTS, SQLite en développement,
PostgreSQL en production.

---

## État d'avancement

| Lot | Contenu | État |
|---|---|---|
| 1 | Socle technique, rôles et permissions, référentiel géographique, bénéficiaires | ✅ terminé |
| 2 | Projets, campagnes, distributions, règle anti-doublon | ✅ terminé |
| 3 | Campagnes Ramadan et Kurban | à venir |
| 4 | Dons, donateurs, partenaires, volontaires | à venir |
| 5 | Tableau de bord, statistiques, rapports PDF et Excel | à venir |
| 6 | Assistant conversationnel (IA) | à venir |
| 7 | Analyse des besoins | à venir |
| 8 | Site public | à venir |

**294 tests** couvrent l'existant.

---

## Installation

### Prérequis

- Python 3.13 ou supérieur
- Git

### Mise en place

```powershell
git clone https://github.com/Ydiboras04/toavina.git
cd toavina

python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Windows PowerShell
# source .venv/bin/activate         # Linux / macOS

pip install -r requirements/dev.txt
python manage.py migrate
```

La base SQLite `db.sqlite3` est créée automatiquement. Elle n'est pas
versionnée : chacun travaille sur la sienne.

---

## Lancer l'application

### 1. Charger des données de démonstration

Sans référentiel géographique, aucun bénéficiaire ne peut être enregistré —
une fiche exige un village, qui exige une commune, un district, une région et
un pays. Une commande évite d'avoir à tout saisir à la main :

```powershell
python manage.py donnees_demo
```

Elle crée le référentiel géographique du district de Morondava, les douze
types d'action du cahier des charges, **un compte par rôle**, un projet, une
campagne Ramadan 2026, cinq bénéficiaires et trois distributions.

La commande est rejouable : la relancer ne crée pas de doublons. Pour repartir
d'un état propre — par exemple avant une démonstration :

```powershell
python manage.py donnees_demo --vider
```

Elle refuse de s'exécuter lorsque le débogage est désactivé, puisqu'elle crée
des comptes dont le mot de passe est écrit dans le code.

### 2. Démarrer le serveur

```powershell
python manage.py runserver
```

L'application est disponible sur http://127.0.0.1:8000/

### 3. Se connecter

Tous les comptes de démonstration partagent le mot de passe `demo12345`.

| Identifiant | Rôle | Ce qu'il voit |
|---|---|---|
| `admin` | Super administrateur | tout, y compris l'administration Django |
| `president` | Président | tout en consultation |
| `coordo` | Coordinateur | bénéficiaires, projets, campagnes, distributions |
| `comptable` | Comptable | finances et projets, **pas** les bénéficiaires |
| `chefprojet` | Responsable de projet | ses projets et leurs distributions |
| `volontaire` | Volontaire | les bénéficiaires, et **ses propres** saisies |

Connexion sur http://127.0.0.1:8000/comptes/login/

### Adresses principales

| Adresse | Contenu |
|---|---|
| `/beneficiaires/` | liste et recherche des bénéficiaires |
| `/beneficiaires/nouveau/` | créer une fiche |
| `/campagnes/` | liste des campagnes |
| `/campagnes/distributions/` | distributions enregistrées |
| `/campagnes/distributions/nouvelle/` | enregistrer une distribution |
| `/admin/` | administration Django (compte `admin`) |

---

## Essayer l'application

Quatre parcours qui montrent ce que le projet garantit. Comptez dix minutes.

### 1. La règle centrale : pas deux fois la même aide

C'est le critère de réception principal du cahier des charges.

1. Connectez-vous en `coordo` et ouvrez `/campagnes/distributions/`.
   Trois distributions sont déjà enregistrées pour la campagne Ramadan 2026.
2. Cliquez sur **Enregistrer une distribution**.
3. Choisissez un bénéficiaire **déjà servi** — Rakoto Jean, Rabe Paul ou
   Razafy Vola — la campagne Ramadan 2026, un village, une date.
4. Validez.

Le formulaire revient avec le message *« … a déjà reçu une aide pour la
campagne Ramadan 2026 »*. Pas d'erreur serveur : un message en français.

La règle n'est pas seulement appliquée par le code — un index unique partiel
de la base l'interdit également, et un troisième contrôle intercepte le cas
où deux opérateurs saisiraient au même instant.

### 2. Une aide annulée libère la place

Une distribution saisie par erreur ne doit pas bloquer définitivement la vraie.

1. Sur `/campagnes/distributions/`, cliquez **Annuler** sur une ligne.
2. Saisissez un motif — il est obligatoire — et confirmez.
3. La ligne disparaît de la liste.
4. Enregistrez maintenant une distribution pour ce même bénéficiaire et cette
   même campagne : elle est **acceptée**.

Rien n'a été effacé : ouvrez `/admin/` en `admin`, section *Distributions*.
La ligne annulée y figure toujours, avec son motif, qui l'a annulée et quand.

### 3. Chacun ne voit que ce qui le concerne

1. Connectez-vous en `coordo`, ouvrez `/campagnes/distributions/` : toutes les
   distributions apparaissent.
2. Déconnectez-vous, reconnectez-vous en `volontaire`, même adresse : seules
   les distributions qu'il a lui-même saisies apparaissent.
3. Reconnectez-vous en `comptable` et ouvrez `/beneficiaires/` : **erreur
   403**. Le comptable travaille sur des montants, pas sur des données
   personnelles.

### 4. Les données sensibles sont masquées

1. En `coordo`, ouvrez la fiche d'un bénéficiaire : le numéro CIN est affiché.
2. En `volontaire`, ouvrez la même fiche : le numéro CIN, le passeport et le
   revenu ont disparu.
3. En `volontaire`, tentez d'ouvrir directement l'adresse de modification
   (`/beneficiaires/1/modifier/`) : **erreur 403**, avant même que le
   formulaire ne soit construit.

---

## Tests

```powershell
pytest
```

**294 tests, environ deux secondes.**

Quelques cibles utiles :

```powershell
pytest core/tests/test_permissions.py -v      # matrice des droits, 77 cellules
pytest apps/campagnes/ -v                     # règle anti-doublon
pytest -k doublon -v                          # tout ce qui touche aux doublons
pytest --tb=short -q                          # sortie compacte
```

Les tests utilisent un module de réglages dédié (`config/settings/test.py`)
qui accélère le hachage des mots de passe. Sans lui, la suite prend près de
trois minutes au lieu de deux secondes : Django hache par défaut avec un
million d'itérations, et les tests créent des centaines de comptes. Ce réglage
ne s'applique **jamais** hors des tests.

Autres vérifications :

```powershell
python manage.py check                            # cohérence du projet
python manage.py makemigrations --check --dry-run # aucune migration oubliée
```

---

## Organisation du code

```
config/settings/    base.py · dev.py · prod.py · test.py
core/               noyau partagé, sans dépendance aux modules métier
  models.py           classes abstraites : horodatage, archivage, campagne…
  permissions.py      matrice des droits : 7 rôles × 11 modules
  services.py         primitives partagées des couches de services
  vues.py             traduction des erreurs métier en réponses HTTP
apps/
  accounts/         utilisateurs et rôles
  geographie/       pays → région → district → commune → village
  beneficiaires/    fiches, doublons, données sensibles
  projets/          projets et types d'action
  campagnes/        campagnes et distributions
templates/          gabarits (mise en forme graphique à venir)
docs/               spécification de conception et plans d'implémentation
```

### Le principe d'architecture

Le cahier des charges impose que le futur assistant IA respecte **exactement**
les mêmes règles d'accès que l'interface. Or un assistant n'appelle pas les
vues : toute règle placée dans une vue serait donc contournée.

D'où la règle qui gouverne tout le code :

> Chaque règle métier vit dans un `services.py`. Chaque fonction de service
> reçoit l'utilisateur en premier paramètre et ne retourne que ce qu'il a le
> droit de voir. Les vues appellent ces fonctions — les outils de l'assistant
> appelleront les mêmes.

Une vue ne contient aucune règle métier : elle appelle un service, laisse un
décorateur traduire les refus en 403 et les absences en 404, et transmet le
résultat au gabarit.

---

## Documentation

| Document | Contenu |
|---|---|
| [Spécification de conception](docs/superpowers/specs/2026-09-04-ngo-management-system-design.md) | modèle Merise complet (MCD, MLD, MPD), matrice des droits, architecture des modules IA, découpage en lots |
| [Plan du lot 1](docs/superpowers/plans/2026-09-04-lot-0-1-socle-et-beneficiaires.md) | socle et bénéficiaires |
| [Plan du lot 2](docs/superpowers/plans/2026-09-04-lot-2-campagnes-et-distributions.md) | projets, campagnes et distributions |

---

## Points ouverts

Trois questions attendent une décision de l'ONG avant le module d'IA :

1. Le coordinateur peut saisir un numéro CIN, alors que la matrice ne lui
   accorde que la lecture sur les données sensibles.
2. Un numéro CIN porté par une fiche archivée reste bloqué indéfiniment ; les
   distributions, elles, suivent la règle inverse.
3. Un volontaire doit choisir une campagne pour saisir une distribution, mais
   n'a aucun droit sur le module des projets, où vivent les campagnes.

---

## Déploiement en production

`config/settings/prod.py` attend ces variables d'environnement — voir
`.env.example` :

```
DJANGO_SECRET_KEY      DJANGO_ALLOWED_HOSTS
DB_NAME  DB_USER  DB_PASSWORD  DB_HOST  DB_PORT
```

```powershell
pip install -r requirements/prod.txt
$env:DJANGO_SETTINGS_MODULE = "config.settings.prod"
python manage.py migrate
python manage.py collectstatic
```

Aucune fonctionnalité propre à PostgreSQL n'est utilisée : la migration depuis
SQLite est un transfert de données, pas une réécriture.

> ⚠️ Ne lancez **jamais** `donnees_demo` en production : la commande crée des
> comptes dont le mot de passe figure dans le code source. Elle refuse de
> s'exécuter avec le débogage désactivé, mais la règle vaut d'être rappelée.
