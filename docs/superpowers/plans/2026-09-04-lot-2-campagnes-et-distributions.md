# Plan 2 — Consolidation, projets, campagnes et distributions

> **Pour les agents d'exécution :** SOUS-COMPÉTENCE REQUISE — utiliser
> `superpowers:subagent-driven-development` (recommandé) ou
> `superpowers:executing-plans` pour implémenter ce plan tâche par tâche.
> Les étapes utilisent la syntaxe à cases à cocher (`- [ ]`).

**Objectif :** rendre structurellement impossible qu'un bénéficiaire reçoive
deux fois la même aide, en posant au passage les primitives partagées que les
cinq lots suivants réutiliseront au lieu de les recopier.

**Architecture :** les quatre couches du lot 1 sont conservées. Ce plan remonte
dans `core/` ce que le lot 1 avait laissé dans `apps/beneficiaires/` — validation
des champs, traduction des exceptions, filtrage par périmètre — puis construit
projets, campagnes et distributions par-dessus. La règle anti-doublon est portée
par une contrainte du SGBD, doublée d'une vérification métier dans la couche de
services pour produire un message compréhensible.

**Pile technique :** Python 3.13, Django 5.2 LTS, SQLite en développement,
pytest + pytest-django.

**Spécification :** `docs/superpowers/specs/2026-09-04-ngo-management-system-design.md`

**Plan précédent :** `docs/superpowers/plans/2026-09-04-lot-0-1-socle-et-beneficiaires.md`
(terminé — 169 tests verts)

**Couverture :** lot 2 du §11 de la spécification, plus la consolidation
recommandée par sa relecture finale. Sections implémentées : §6.1 décisions D2 et
D3, §6.5 (projets, campagnes, distributions), §9.2 niveau objet, §13 gestion des
erreurs. Le §17 y trouve son critère de réception le plus important : *« Les
distributions sont enregistrées et consultables sans doublons injustifiés. »*

---

## Contraintes globales

Reprises du lot 1 et applicables à **toutes** les tâches sans être répétées.

- **Python 3.13.15**, **Django 5.2 LTS**.
- **SQLite en développement, PostgreSQL en production** — aucune fonctionnalité
  propre à PostgreSQL.
- **Nommage en français** pour tout le métier : classes, champs, `verbose_name`.
- **Signature imposée des services** : toute fonction publique de `services.py`
  prend `utilisateur` comme premier paramètre et appelle `exiger(...)` avant tout
  accès aux données.
- **Aucune règle métier dans les vues.** Une vue appelle un service, traduit les
  exceptions en réponse HTTP, transmet au gabarit.
- **Aucune exception étrangère au contrat ne franchit la frontière d'un
  service** : `DoesNotExist` devient `Introuvable`, `ValidationError` devient
  `RegleMetierViolee`.
- **Aucune suppression physique** des données historisées — l'archivage la
  remplace.
- **Git est désactivé** à la demande de l'utilisateur : aucune étape de commit.

### Acquis du lot 1 sur lesquels ce plan s'appuie

| Élément | Emplacement | Contenu |
|---|---|---|
| `Horodate` | `core/models.py` | `date_creation`, `date_modification` |
| `Archivable` | `core/models.py` | `archive`, gestionnaires `objects` (actifs) et `tous` |
| `PermissionRefusee`, `RegleMetierViolee`, `Introuvable` | `core/exceptions.py` | exceptions métier |
| `Role` | `core/roles.py` | 7 rôles |
| `Module`, `Acces`, `MATRICE`, `acces`, `peut_lire`, `peut_ecrire`, `perimetre_restreint`, `exiger` | `core/permissions.py` | matrice de 77 cellules, immuable |
| `Pays`, `Region`, `District`, `Commune`, `Village` | `apps/geographie/models.py` | référentiel |
| `Beneficiaire` | `apps/beneficiaires/models.py` | fiche, unicité partielle du CIN |
| fixtures `village`, `creer_utilisateur` | `conftest.py` (racine) | partagées |

État de départ : **169 tests passent, `manage.py check` est silencieux.**

**Signatures exactes des fixtures partagées**, à utiliser telles quelles :

- `village` — hiérarchie complète Madagascar → Menabe → Morondava (district) →
  Analaiva (commune) → Betania (village). Le libellé de la commune est
  délibérément distinct de celui du district : ne l'aligne pas.
- `creer_utilisateur` — fabrique : `creer_utilisateur(role, nom="agent")`
  retourne un utilisateur dont l'identifiant est `f"{nom}_{role}"` et le mot de
  passe `"motdepasse123"`. **Donne un `nom` distinct** dès que deux utilisateurs
  du même rôle coexistent dans un test, sinon la création échouera sur
  l'unicité de l'identifiant.

`apps/beneficiaires/tests/test_services.py` définit en outre localement les
fixtures `coordinateur`, `comptable` et `volontaire`, construites sur
`creer_utilisateur`.

---

## Deux décisions de conception à connaître avant de commencer

### D5 — La contrainte anti-doublon ne porte que sur les distributions actives

La spécification exige qu'un bénéficiaire ne reçoive pas deux fois la même
campagne. La traduction naïve serait `UniqueConstraint(["beneficiaire",
"campagne"])`.

Elle est fausse. L'archivage remplaçant la suppression dans tout le projet, une
distribution saisie par erreur puis annulée resterait en base et **bloquerait
définitivement** la distribution réelle. L'opérateur se retrouverait incapable
d'enregistrer une aide effectivement remise.

La contrainte porte donc sur les seules lignes non archivées :

```python
models.UniqueConstraint(
    fields=["beneficiaire", "campagne"],
    condition=models.Q(archive=False),
    name="distribution_unique_par_campagne",
)
```

C'est la même forme d'unicité partielle que celle du numéro CIN au lot 1, et
elle exprime exactement la règle métier : *une personne ne peut pas avoir deux
aides **valides** pour la même campagne*. Une aide annulée n'a pas été reçue.

### D6 — Le niveau d'accès « propre » devient réel

Le lot 1 a déclaré `Acces.PROPRE` sans jamais l'appliquer : aucun rôle n'avait
ce niveau sur les bénéficiaires. Sur les distributions, **le responsable de
projet et le volontaire l'ont** (§9.1). Un service calqué sur celui des
bénéficiaires leur donnerait l'écriture sur l'intégralité du module.

D'où deux ajouts dans `core/` à la tâche 2 : un abstrait `SaisiPar` portant
l'auteur de la saisie — que le §6.5 exige de toute façon par son association
SAISIE_PAR — et une primitive `filtrer_perimetre` appelée systématiquement après
`exiger`.

---

## Structure des fichiers

| Fichier | Responsabilité |
|---|---|
| `core/services.py` | primitives partagées par toutes les couches de services |
| `core/vues.py` | décorateur traduisant les exceptions métier en réponses HTTP |
| `core/models.py` | abstraits : ajout de `SaisiPar`, `Campagne`, `Distribution` |
| `core/permissions.py` | ajout de `filtrer_perimetre` |
| `apps/projets/` | types d'action et projets |
| `apps/campagnes/` | campagnes concrètes et distributions |

`apps/campagnes/` porte à la fois `Campagne` et `Distribution` : les deux
changent ensemble, la contrainte d'unicité lie l'une à l'autre, et les séparer
imposerait une dépendance circulaire entre deux applications.

---

## Tâche 1 : Primitives partagées de la couche de services

Le lot 1 a laissé dans `apps/beneficiaires/services.py` quatre fonctions privées
qui n'ont rien de spécifique aux bénéficiaires. Recopiées dans cinq modules,
elles divergeront. Cette tâche les remonte dans `core/` **et** fait basculer les
bénéficiaires dessus, pour prouver que l'abstraction fonctionne sur un cas réel
avant que quiconque s'en serve.

**Fichiers :**
- Créer : `core/services.py`, `core/tests/test_services.py`
- Modifier : `apps/beneficiaires/services.py`

**Interfaces :**
- Consomme : `core.exceptions.{Introuvable, RegleMetierViolee}`,
  `core.permissions.{Module, peut_lire}`
- Produit :
  - `valider_champs(donnees, autorises)` — lève `RegleMetierViolee` nommant la
    première clé refusée ; ne retourne rien
  - `appliquer_validation(instance)` — appelle `full_clean()`, convertit
    `ValidationError` en `RegleMetierViolee` ; ne retourne rien
  - `obtenir_ou_introuvable(gestionnaire, **criteres)` — retourne l'instance ou
    lève `Introuvable`
  - `champs_visibles(utilisateur, courants, sensibles)` — retourne un `set`

- [ ] **Étape 1 : Écrire les tests en échec**

`core/tests/test_services.py` :

```python
"""Vérifie les primitives partagées par toutes les couches de services."""
import pytest
from django.db import models

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
```

- [ ] **Étape 2 : Lancer les tests et vérifier l'échec**

```powershell
pytest core/tests/test_services.py -v
```

Attendu : ÉCHEC avec `ModuleNotFoundError: No module named 'core.services'`.

- [ ] **Étape 3 : Écrire `core/services.py`**

```python
"""Primitives partagées par toutes les couches de services métier.

Ces fonctions n'ont rien de spécifique à un module : les recopier dans chaque
`services.py` les ferait diverger. Elles vivent donc ici, et chaque module les
paramètre avec ses propres listes de champs.

Règle que ce fichier fait respecter : aucune exception étrangère au contrat
métier ne franchit la frontière d'un service. Les erreurs de l'ORM et de la
validation Django sont converties en exceptions de `core.exceptions`.
"""
from django.core.exceptions import ValidationError

from core.exceptions import Introuvable, RegleMetierViolee
from core.permissions import Module, peut_lire


def valider_champs(donnees, autorises):
    """Rejette toute clé absente de l'ensemble autorisé.

    Sans ce contrôle, un appel du type `modifier(u, pk, archive=True)`
    contournerait le niveau d'accès exigé par la fonction d'archivage, et une
    clé mal orthographiée serait silencieusement perdue à l'enregistrement.
    """
    for champ in donnees:
        if champ not in autorises:
            raise RegleMetierViolee(
                f"Le champ « {champ} » ne peut pas être modifié ici."
            )


def appliquer_validation(instance):
    """Valide l'instance et convertit l'erreur Django en erreur métier.

    Appelée avant chaque `save()` : le formulaire vérifie déjà les listes de
    choix et les longueurs, mais c'est précisément la couche qu'un assistant
    IA n'empruntera pas.
    """
    try:
        instance.full_clean()
    except ValidationError as erreur:
        messages = []
        for champ, erreurs in erreur.message_dict.items():
            messages.append(f"{champ} : {' '.join(erreurs)}")
        raise RegleMetierViolee(" ; ".join(messages)) from erreur


def obtenir_ou_introuvable(gestionnaire, **criteres):
    """Retourne l'instance correspondante, ou lève `Introuvable`.

    Le gestionnaire est passé explicitement : `objets` masque les
    enregistrements archivés, `tous` les inclut. Le service choisit selon ce
    qu'il fait — on ne modifie pas une fiche archivée, mais on doit pouvoir
    l'archiver ou la consulter.
    """
    try:
        return gestionnaire.get(**criteres)
    except gestionnaire.model.DoesNotExist as erreur:
        raise Introuvable(
            f"{gestionnaire.model._meta.verbose_name} introuvable."
        ) from erreur


def champs_visibles(utilisateur, courants, sensibles):
    """Retourne les champs que cet utilisateur a le droit de consulter.

    Le résultat indique à l'appelant ce qu'il peut afficher : cette fonction
    ne filtre aucune donnée par elle-même, c'est à la couche présentation de
    l'appliquer.
    """
    champs = set(courants)
    if peut_lire(utilisateur, Module.DONNEES_SENSIBLES):
        champs |= set(sensibles)
    return champs
```

- [ ] **Étape 4 : Lancer les tests et vérifier le succès**

```powershell
pytest core/tests/test_services.py -v
```

Attendu : SUCCÈS, 10 tests passés.

- [ ] **Étape 5 : Faire basculer les bénéficiaires sur les primitives**

Dans `apps/beneficiaires/services.py` :

1. Supprimer les fonctions privées `_valider_champs`, `_appliquer_validation` et
   la fonction publique `champs_visibles`.
2. Importer depuis `core.services` : `valider_champs`, `appliquer_validation`,
   `obtenir_ou_introuvable`, et `champs_visibles` sous le nom
   `champs_visibles_generique`.
3. Remplacer chaque appel à `_valider_champs(donnees)` par
   `valider_champs(donnees, CHAMPS_MODIFIABLES)`.
4. Remplacer chaque appel à `_appliquer_validation(beneficiaire)` par
   `appliquer_validation(beneficiaire)`.
5. Remplacer chaque bloc `try: ... .get(pk=...) except Beneficiaire.DoesNotExist:
   raise Introuvable(...)` par un appel à `obtenir_ou_introuvable`.
6. Redéfinir `champs_visibles` comme une mince enveloppe :

```python
def champs_visibles(utilisateur):
    """Champs de la fiche bénéficiaire visibles par cet utilisateur."""
    return champs_visibles_generique(
        utilisateur, CHAMPS_COURANTS, CHAMPS_SENSIBLES
    )
```

Conserver `_normaliser_cin` et `_verifier_cin_unique` : celles-là sont bien
propres aux bénéficiaires.

- [ ] **Étape 6 : Lancer la suite complète**

```powershell
pytest -v
```

Attendu : SUCCÈS, **179 tests passés** (169 existants + 10 nouveaux), aucun
échec. Aucun test des bénéficiaires ne doit avoir été modifié : c'est ce qui
prouve que la bascule est neutre.

---

## Tâche 2 : Traçabilité de la saisie et filtrage par périmètre

**Fichiers :**
- Modifier : `core/models.py`, `core/permissions.py`
- Test : `core/tests/test_models.py`, `core/tests/test_permissions.py`

**Interfaces :**
- Consomme : `core.permissions.{Acces, acces, perimetre_restreint}`
- Produit :
  - `core.models.SaisiPar` — abstrait, champ `saisie_par` en clé étrangère vers
    le modèle utilisateur, `PROTECT`, `related_name="%(class)ss"`
  - `core.permissions.filtrer_perimetre(queryset, utilisateur, module, champ="saisie_par")`
    — retourne le queryset restreint aux objets de l'utilisateur lorsque son
    niveau d'accès est exactement « propre », le queryset inchangé sinon

- [ ] **Étape 1 : Écrire les tests en échec**

Ajouter à `core/tests/test_models.py` :

```python
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
```

Ajouter à `core/tests/test_permissions.py` :

```python
class QuerySetFactice:
    """Substitut minimal : on vérifie l'intention, pas l'ORM."""

    def __init__(self):
        self.filtre = None

    def filter(self, **criteres):
        self.filtre = criteres
        return self


def test_filtrer_perimetre_restreint_au_niveau_propre():
    from core.permissions import filtrer_perimetre

    utilisateur = UtilisateurFactice(Role.RESPONSABLE_PROJET)
    qs = QuerySetFactice()
    resultat = filtrer_perimetre(qs, utilisateur, Module.DISTRIBUTIONS)
    assert resultat.filtre == {"saisie_par": utilisateur}


def test_filtrer_perimetre_ne_restreint_pas_au_niveau_complet():
    from core.permissions import filtrer_perimetre

    utilisateur = UtilisateurFactice(Role.COORDINATEUR)
    qs = QuerySetFactice()
    resultat = filtrer_perimetre(qs, utilisateur, Module.DISTRIBUTIONS)
    assert resultat.filtre is None


def test_filtrer_perimetre_ne_restreint_pas_au_niveau_lecture():
    from core.permissions import filtrer_perimetre

    utilisateur = UtilisateurFactice(Role.PRESIDENT)
    qs = QuerySetFactice()
    resultat = filtrer_perimetre(qs, utilisateur, Module.DISTRIBUTIONS)
    assert resultat.filtre is None


def test_filtrer_perimetre_accepte_un_autre_champ():
    from core.permissions import filtrer_perimetre

    utilisateur = UtilisateurFactice(Role.RESPONSABLE_PROJET)
    qs = QuerySetFactice()
    resultat = filtrer_perimetre(
        qs, utilisateur, Module.PROJETS, champ="responsable"
    )
    assert resultat.filtre == {"responsable": utilisateur}
```

- [ ] **Étape 2 : Lancer les tests et vérifier l'échec**

```powershell
pytest core/tests/ -v
```

Attendu : ÉCHEC — `cannot import name 'SaisiPar'` et
`cannot import name 'filtrer_perimetre'`.

- [ ] **Étape 3 : Ajouter `SaisiPar` à `core/models.py`**

À la suite des classes existantes :

```python
class SaisiPar(models.Model):
    """Conserve qui a enregistré la donnée.

    Deux usages. D'abord la traçabilité, exigée par l'association SAISIE_PAR
    du modèle conceptuel : savoir qui a enregistré quelle aide, et quand.
    Ensuite le contrôle d'accès : c'est ce champ qui permet de restreindre un
    rôle à ses propres enregistrements, comme le prévoit le niveau « propre »
    de la matrice des droits.

    `PROTECT` est délibéré : supprimer un utilisateur effacerait la trace de
    ce qu'il a saisi.
    """

    saisie_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="%(class)ss",
        verbose_name="saisi par",
    )

    class Meta:
        abstract = True
```

Ajouter en tête du fichier : `from django.conf import settings`.

- [ ] **Étape 4 : Ajouter `filtrer_perimetre` à `core/permissions.py`**

À la suite des fonctions existantes :

```python
def filtrer_perimetre(queryset, utilisateur, module, champ="saisie_par"):
    """Restreint un queryset aux objets de l'utilisateur si son accès est « propre ».

    À appeler systématiquement **après** `exiger`, jamais à sa place : cette
    fonction affine un périmètre déjà autorisé, elle n'autorise rien par
    elle-même. Sans elle, un rôle au niveau « propre » obtiendrait la totalité
    du module — le niveau ne serait qu'un décor.
    """
    if perimetre_restreint(utilisateur, module):
        return queryset.filter(**{champ: utilisateur})
    return queryset
```

- [ ] **Étape 5 : Lancer la suite complète**

```powershell
pytest -v
```

Attendu : SUCCÈS, **186 tests passés** (179 + 3 + 4). `SaisiPar` étant
abstrait, aucune migration ne doit être générée — vérifier avec :

```powershell
python manage.py makemigrations --check --dry-run
```

Attendu : `No changes detected`.

---

## Tâche 3 : Décorateur de traduction des exceptions

Les vues des bénéficiaires répètent six fois le même bloc `try/except`. Répété
dans cinq modules, cela ferait une quarantaine de blocs identiques, et il
suffirait d'en oublier un pour qu'une erreur 500 remplace un 403 ou un 404.

**Fichiers :**
- Créer : `core/vues.py`, `core/tests/test_vues.py`
- Modifier : `apps/beneficiaires/views.py`

**Interfaces :**
- Consomme : `core.exceptions.{PermissionRefusee, Introuvable}`
- Produit : `core.vues.traduire_erreurs_metier` — décorateur de vue convertissant
  `PermissionRefusee` en `PermissionDenied` (403) et `Introuvable` en `Http404`.
  `RegleMetierViolee` n'est **pas** interceptée : elle se rattache au formulaire,
  ce que seule la vue sait faire.

- [ ] **Étape 1 : Écrire les tests en échec**

`core/tests/test_vues.py` :

```python
"""Vérifie le décorateur de traduction des exceptions métier."""
import pytest
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse

from core.exceptions import Introuvable, PermissionRefusee, RegleMetierViolee
from core.vues import traduire_erreurs_metier


def test_permission_refusee_devient_403():
    @traduire_erreurs_metier
    def vue(requete):
        raise PermissionRefusee("accès refusé au module Distributions")

    with pytest.raises(PermissionDenied) as erreur:
        vue(None)
    assert "Distributions" in str(erreur.value)


def test_introuvable_devient_404():
    @traduire_erreurs_metier
    def vue(requete):
        raise Introuvable("bénéficiaire introuvable")

    with pytest.raises(Http404):
        vue(None)


def test_regle_metier_violee_n_est_pas_interceptee():
    """La vue doit pouvoir la rattacher au formulaire elle-même."""

    @traduire_erreurs_metier
    def vue(requete):
        raise RegleMetierViolee("ce bénéficiaire a déjà reçu cette aide")

    with pytest.raises(RegleMetierViolee):
        vue(None)


def test_une_vue_sans_erreur_retourne_sa_reponse():
    @traduire_erreurs_metier
    def vue(requete):
        return HttpResponse("bonjour")

    assert vue(None).content == b"bonjour"


def test_le_decorateur_preserve_le_nom_de_la_vue():
    @traduire_erreurs_metier
    def liste(requete):
        return HttpResponse("")

    assert liste.__name__ == "liste"
```

- [ ] **Étape 2 : Lancer les tests et vérifier l'échec**

```powershell
pytest core/tests/test_vues.py -v
```

Attendu : ÉCHEC avec `ModuleNotFoundError: No module named 'core.vues'`.

- [ ] **Étape 3 : Écrire `core/vues.py`**

```python
"""Outils partagés par les vues.

Les vues ne contiennent aucune règle métier : elles appellent un service et
traduisent ses exceptions en réponses HTTP. Cette traduction étant identique
partout, elle vit ici.
"""
from functools import wraps

from django.core.exceptions import PermissionDenied
from django.http import Http404

from core.exceptions import Introuvable, PermissionRefusee


def traduire_erreurs_metier(vue):
    """Convertit les exceptions de la couche de services en réponses HTTP.

    `PermissionRefusee` devient un 403, `Introuvable` un 404.

    `RegleMetierViolee` est délibérément laissée passer : c'est une erreur de
    saisie, pas un refus d'accès. La vue doit la rattacher au formulaire pour
    que l'opérateur voie ce qui ne va pas et puisse corriger — le décorateur ne
    peut pas le faire à sa place.
    """

    @wraps(vue)
    def enveloppe(requete, *args, **kwargs):
        try:
            return vue(requete, *args, **kwargs)
        except PermissionRefusee as erreur:
            raise PermissionDenied(str(erreur)) from erreur
        except Introuvable as erreur:
            raise Http404(str(erreur)) from erreur

    return enveloppe
```

- [ ] **Étape 4 : Appliquer le décorateur aux vues des bénéficiaires**

Dans `apps/beneficiaires/views.py`, pour chacune des quatre vues :

1. Ajouter `@traduire_erreurs_metier` sous `@login_required`.
2. Supprimer les blocs `except PermissionRefusee` et `except Introuvable` ainsi
   que les `raise PermissionDenied` / `raise Http404` correspondants.
3. **Conserver** les blocs `except RegleMetierViolee` avec leur
   `formulaire.add_error(None, str(erreur))`.
4. Nettoyer les imports devenus inutiles (`PermissionDenied`, `Http404`,
   `PermissionRefusee`, `Introuvable` si plus référencés).

L'ordre des décorateurs compte : `login_required` doit rester le plus externe,
afin qu'un utilisateur anonyme soit redirigé vers la connexion avant qu'une
quelconque exception métier ne puisse survenir.

```python
@login_required
@traduire_erreurs_metier
def detail(requete, identifiant):
    beneficiaire = obtenir_beneficiaire(requete.user, identifiant)
    return render(
        requete,
        "beneficiaires/detail.html",
        {
            "beneficiaire": beneficiaire,
            "champs_visibles": champs_visibles(requete.user),
            "peut_modifier": peut_ecrire(requete.user, Module.BENEFICIAIRES),
        },
    )
```

- [ ] **Étape 5 : Lancer la suite complète**

```powershell
pytest -v
```

Attendu : SUCCÈS, **191 tests passés** (186 + 5). Les tests de vues du lot 1
doivent passer **sans modification** : c'est ce qui prouve que le décorateur
reproduit exactement le comportement précédent.

---

## Tâche 4 : Abstraits Campagne et Distribution

**Fichiers :**
- Modifier : `core/models.py`
- Test : `core/tests/test_models.py`

**Interfaces :**
- Consomme : `core.models.{Horodate, Archivable, SaisiPar}`
- Produit :
  - `core.models.EtatCampagne` — `TextChoices` : `PLANIFIEE`, `EN_COURS`,
    `TERMINEE`, `ANNULEE`
  - `core.models.Campagne` — abstrait : `code`, `libelle`, `annee`, `budget`,
    `date_debut`, `date_fin`, `etat`
  - `core.models.Distribution` — abstrait : `date_distribution`, `quantite`,
    `unite`, `observation`

- [ ] **Étape 1 : Écrire les tests en échec**

Ajouter à `core/tests/test_models.py` :

```python
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
```

- [ ] **Étape 2 : Lancer les tests et vérifier l'échec**

```powershell
pytest core/tests/test_models.py -v
```

Attendu : ÉCHEC avec `cannot import name 'Campagne' from 'core.models'`.

- [ ] **Étape 3 : Ajouter les abstraits à `core/models.py`**

```python
class EtatCampagne(models.TextChoices):
    PLANIFIEE = "planifiee", "Planifiée"
    EN_COURS = "en_cours", "En cours"
    TERMINEE = "terminee", "Terminée"
    ANNULEE = "annulee", "Annulée"


class Campagne(models.Model):
    """Tronc commun des campagnes d'aide.

    Ramadan, Kurban, les bourses et les forages suivent tous le même patron :
    une campagne dotée d'un budget, de dates, d'un responsable et d'un état,
    qui produit des distributions vers des bénéficiaires. Écrire ce patron
    quatre fois multiplierait par quatre les occasions d'erreur — en
    particulier sur la règle anti-doublon, qui est un critère de réception.

    Chaque module concret hérite d'ici et n'ajoute que ce qui lui est propre :
    la composition du colis pour Ramadan, le nombre de zébus pour Kurban.
    """

    code = models.CharField("code", max_length=32)
    libelle = models.CharField("libellé", max_length=150)
    annee = models.PositiveSmallIntegerField("année")
    budget = models.DecimalField(
        "budget",
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    date_debut = models.DateField("date de début")
    date_fin = models.DateField("date de fin", null=True, blank=True)
    etat = models.CharField(
        "état",
        max_length=20,
        choices=EtatCampagne.choices,
        default=EtatCampagne.PLANIFIEE,
    )

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.libelle} {self.annee}"


class Distribution(models.Model):
    """Tronc commun des distributions d'aide à un bénéficiaire.

    La quantité et son unité sont génériques : un colis pour Ramadan, des
    kilogrammes de viande pour Kurban.
    """

    date_distribution = models.DateField("date de distribution")
    quantite = models.DecimalField(
        "quantité",
        max_digits=10,
        decimal_places=2,
        default=1,
        validators=[MinValueValidator(0)],
    )
    unite = models.CharField("unité", max_length=32, default="unité")
    observation = models.TextField("observation", blank=True)

    class Meta:
        abstract = True
```

Ajouter en tête du fichier : `from django.core.validators import MinValueValidator`.

- [ ] **Étape 4 : Lancer la suite complète**

```powershell
pytest -v
python manage.py makemigrations --check --dry-run
```

Attendu : SUCCÈS, **198 tests passés** (191 + 7), et `No changes detected` —
les deux classes étant abstraites, elles ne produisent aucune table.

---

## Tâche 5 : Types d'action et projets

**Fichiers :**
- Créer : `apps/projets/{__init__,apps,models,admin,services}.py`,
  `apps/projets/tests/{__init__,test_models,test_services}.py`
- Modifier : `config/settings/base.py` (`INSTALLED_APPS`)

**Interfaces :**
- Consomme : `core.models.{Horodate, Archivable}`, `core.services.*`,
  `core.permissions.{Module, Acces, exiger, filtrer_perimetre}`,
  `apps.geographie.models.Region`
- Produit :
  - `apps.projets.models.TypeAction` — `libelle`, `description`
  - `apps.projets.models.EtatProjet` — `TextChoices` : `PLANIFIE`, `EN_COURS`,
    `TERMINE`, `SUSPENDU`
  - `apps.projets.models.Projet` — `code` (unique), `titre`, `description`,
    `budget_prevu`, `budget_consomme`, `date_debut`, `date_fin`, `etat`,
    `type_action`, `responsable`, `region`, plus la propriété `budget_restant`
  - `apps.projets.services.lister_projets(utilisateur, recherche="", etat=None)`
  - `apps.projets.services.obtenir_projet(utilisateur, identifiant)`
  - `apps.projets.services.creer_projet(utilisateur, **donnees)`
  - `apps.projets.services.modifier_projet(utilisateur, identifiant, **donnees)`

> **Écart assumé.** Le modèle conceptuel prévoit une association n-n entre
> projet et partenaire (SOUTIENT). L'entité `Partenaire` appartient à un lot
> ultérieur : la relation sera ajoutée par une migration à ce moment-là. Rien
> dans ce plan n'en dépend.

- [ ] **Étape 1 : Écrire les tests de modèle en échec**

`apps/projets/tests/test_models.py` :

```python
"""Vérifie le modèle Projet et le référentiel des types d'action."""
import pytest

from apps.projets.models import EtatProjet, Projet, TypeAction


@pytest.fixture
def type_action(db):
    return TypeAction.objects.create(
        libelle="Distribution alimentaire",
        description="Remise de colis alimentaires aux familles.",
    )


@pytest.fixture
def projet(db, type_action, creer_utilisateur, village):
    from core.roles import Role

    return Projet.objects.create(
        code="PROJ-2026-001",
        titre="Distribution alimentaire à Morondava",
        description="Campagne de distribution sur le district de Morondava.",
        budget_prevu="15000000.00",
        date_debut="2026-01-15",
        type_action=type_action,
        responsable=creer_utilisateur(Role.RESPONSABLE_PROJET),
        region=village.region,
    )


def test_creation_avec_champs_minimaux(projet):
    assert projet.pk is not None
    assert projet.etat == EtatProjet.PLANIFIE


def test_budget_consomme_est_nul_au_depart(projet):
    assert projet.budget_consomme == 0


def test_budget_restant(projet):
    projet.budget_consomme = "5000000.00"
    projet.save()
    projet.refresh_from_db()
    assert str(projet.budget_restant) == "10000000.00"


def test_representation_textuelle(projet):
    assert str(projet) == "PROJ-2026-001 — Distribution alimentaire à Morondava"


@pytest.mark.django_db
def test_code_unique(projet, type_action, creer_utilisateur):
    from django.db import IntegrityError
    from core.roles import Role

    with pytest.raises(IntegrityError):
        Projet.objects.create(
            code="PROJ-2026-001",
            titre="Autre projet",
            budget_prevu="100.00",
            date_debut="2026-02-01",
            type_action=type_action,
            responsable=creer_utilisateur(Role.COORDINATEUR),
        )


def test_non_archive_par_defaut(projet):
    assert projet.archive is False


def test_gestionnaire_masque_les_archives(projet):
    projet.archive = True
    projet.save()
    assert Projet.objects.count() == 0
    assert Projet.tous.count() == 1


def test_type_action_representation(type_action):
    assert str(type_action) == "Distribution alimentaire"
```

- [ ] **Étape 2 : Lancer les tests et vérifier l'échec**

```powershell
pytest apps/projets/tests/test_models.py -v
```

Attendu : ÉCHEC avec `ModuleNotFoundError: No module named 'apps.projets'`.

- [ ] **Étape 3 : Écrire `apps/projets/models.py`**

```python
"""Projets et actions de l'ONG."""
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.geographie.models import Region
from core.models import Archivable, Horodate


class TypeAction(Horodate):
    """Nature de l'action menée.

    Alimente le référentiel des douze types prévus par le cahier des charges :
    distribution alimentaire, distribution de vêtements, kurban, forage d'eau,
    construction de mosquées, construction d'écoles, bourses d'étude,
    parrainage d'orphelins, urgences humanitaires, santé, éducation,
    développement rural.
    """

    libelle = models.CharField("libellé", max_length=100, unique=True)
    description = models.TextField("description", blank=True)

    class Meta:
        verbose_name = "type d'action"
        verbose_name_plural = "types d'action"
        ordering = ["libelle"]

    def __str__(self):
        return self.libelle


class EtatProjet(models.TextChoices):
    PLANIFIE = "planifie", "Planifié"
    EN_COURS = "en_cours", "En cours"
    TERMINE = "termine", "Terminé"
    SUSPENDU = "suspendu", "Suspendu"


class Projet(Horodate, Archivable):
    """Projet humanitaire ou social de l'ONG."""

    code = models.CharField("code", max_length=32, unique=True)
    titre = models.CharField("titre", max_length=200)
    description = models.TextField("description", blank=True)

    budget_prevu = models.DecimalField(
        "budget prévu",
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    budget_consomme = models.DecimalField(
        "budget consommé",
        max_digits=14,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )

    date_debut = models.DateField("date de début")
    date_fin = models.DateField("date de fin", null=True, blank=True)
    etat = models.CharField(
        "état",
        max_length=20,
        choices=EtatProjet.choices,
        default=EtatProjet.PLANIFIE,
    )

    type_action = models.ForeignKey(
        TypeAction,
        on_delete=models.PROTECT,
        related_name="projets",
        verbose_name="type d'action",
    )
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="projets_diriges",
        verbose_name="responsable",
    )
    region = models.ForeignKey(
        Region,
        on_delete=models.PROTECT,
        related_name="projets",
        verbose_name="région",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "projet"
        verbose_name_plural = "projets"
        ordering = ["-date_debut", "code"]

    def __str__(self):
        return f"{self.code} — {self.titre}"

    @property
    def budget_restant(self):
        """Part du budget prévu encore disponible."""
        return self.budget_prevu - self.budget_consomme
```

`apps/projets/apps.py` :

```python
from django.apps import AppConfig


class ProjetsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.projets"
    label = "projets"
    verbose_name = "Projets et actions"
```

`apps/projets/admin.py` :

```python
from django.contrib import admin

from apps.projets.models import Projet, TypeAction


@admin.register(TypeAction)
class TypeActionAdmin(admin.ModelAdmin):
    list_display = ["libelle"]
    search_fields = ["libelle"]


@admin.register(Projet)
class ProjetAdmin(admin.ModelAdmin):
    list_display = ["code", "titre", "type_action", "etat", "date_debut"]
    list_filter = ["etat", "type_action"]
    search_fields = ["code", "titre"]
```

- [ ] **Étape 4 : Déclarer l'application et migrer**

Ajouter `"apps.projets",` à `INSTALLED_APPS` dans `config/settings/base.py`,
puis :

```powershell
python manage.py makemigrations projets
python manage.py migrate
pytest apps/projets/tests/test_models.py -v
```

Attendu : SUCCÈS, 8 tests passés.

- [ ] **Étape 5 : Écrire les tests de services en échec**

`apps/projets/tests/test_services.py` :

```python
"""Vérifie les règles métier et le filtrage par rôle des projets."""
import pytest

from apps.projets.models import EtatProjet, Projet, TypeAction
from apps.projets.services import (
    creer_projet,
    lister_projets,
    modifier_projet,
    obtenir_projet,
)
from core.exceptions import Introuvable, PermissionRefusee, RegleMetierViolee
from core.roles import Role


@pytest.fixture
def type_action(db):
    return TypeAction.objects.create(libelle="Distribution alimentaire")


@pytest.fixture
def coordinateur(creer_utilisateur):
    return creer_utilisateur(Role.COORDINATEUR)


@pytest.fixture
def responsable(creer_utilisateur):
    return creer_utilisateur(Role.RESPONSABLE_PROJET, nom="resp1")


def donnees_projet(type_action, responsable, code="PROJ-2026-001"):
    return {
        "code": code,
        "titre": "Distribution alimentaire",
        "budget_prevu": "1000000.00",
        "date_debut": "2026-01-15",
        "type_action": type_action,
        "responsable": responsable,
    }


def test_coordinateur_cree_un_projet(coordinateur, type_action, responsable):
    projet = creer_projet(
        coordinateur, **donnees_projet(type_action, responsable)
    )
    assert projet.pk is not None


def test_volontaire_ne_peut_pas_creer(
    creer_utilisateur, type_action, responsable
):
    volontaire = creer_utilisateur(Role.VOLONTAIRE)
    with pytest.raises(PermissionRefusee):
        creer_projet(volontaire, **donnees_projet(type_action, responsable))


def test_comptable_lit_sans_ecrire(
    creer_utilisateur, coordinateur, type_action, responsable
):
    comptable = creer_utilisateur(Role.COMPTABLE)
    creer_projet(coordinateur, **donnees_projet(type_action, responsable))
    assert lister_projets(comptable).count() == 1
    with pytest.raises(PermissionRefusee):
        creer_projet(comptable, **donnees_projet(type_action, responsable,
                                                 code="PROJ-2026-002"))


def test_responsable_ne_voit_que_ses_projets(
    coordinateur, responsable, creer_utilisateur, type_action
):
    """Le niveau « propre » de la matrice devient effectif ici."""
    autre = creer_utilisateur(Role.RESPONSABLE_PROJET, nom="resp2")
    creer_projet(coordinateur, **donnees_projet(type_action, responsable))
    creer_projet(
        coordinateur,
        **donnees_projet(type_action, autre, code="PROJ-2026-002"),
    )
    assert lister_projets(responsable).count() == 1
    assert lister_projets(coordinateur).count() == 2


def test_recherche_par_code(coordinateur, type_action, responsable):
    creer_projet(coordinateur, **donnees_projet(type_action, responsable))
    creer_projet(
        coordinateur,
        **donnees_projet(type_action, responsable, code="PROJ-2026-002"),
    )
    assert lister_projets(coordinateur, recherche="001").count() == 1


def test_filtre_par_etat(coordinateur, type_action, responsable):
    projet = creer_projet(
        coordinateur, **donnees_projet(type_action, responsable)
    )
    modifier_projet(coordinateur, projet.pk, etat=EtatProjet.EN_COURS)
    assert lister_projets(coordinateur, etat=EtatProjet.EN_COURS).count() == 1
    assert lister_projets(coordinateur, etat=EtatProjet.TERMINE).count() == 0


def test_code_duplique_refuse(coordinateur, type_action, responsable):
    creer_projet(coordinateur, **donnees_projet(type_action, responsable))
    with pytest.raises(RegleMetierViolee):
        creer_projet(coordinateur, **donnees_projet(type_action, responsable))


def test_budget_negatif_refuse(coordinateur, type_action, responsable):
    donnees = donnees_projet(type_action, responsable)
    donnees["budget_prevu"] = "-100.00"
    with pytest.raises(RegleMetierViolee):
        creer_projet(coordinateur, **donnees)


def test_date_fin_avant_date_debut_refusee(
    coordinateur, type_action, responsable
):
    donnees = donnees_projet(type_action, responsable)
    donnees["date_fin"] = "2026-01-01"
    with pytest.raises(RegleMetierViolee):
        creer_projet(coordinateur, **donnees)


def test_champ_inconnu_refuse(coordinateur, type_action, responsable):
    donnees = donnees_projet(type_action, responsable)
    donnees["archive"] = True
    with pytest.raises(RegleMetierViolee):
        creer_projet(coordinateur, **donnees)


def test_projet_inexistant(coordinateur):
    with pytest.raises(Introuvable):
        obtenir_projet(coordinateur, 999999)


def test_responsable_ne_peut_pas_ouvrir_le_projet_d_un_autre(
    coordinateur, responsable, creer_utilisateur, type_action
):
    autre = creer_utilisateur(Role.RESPONSABLE_PROJET, nom="resp2")
    projet = creer_projet(coordinateur, **donnees_projet(type_action, autre))
    with pytest.raises(Introuvable):
        obtenir_projet(responsable, projet.pk)
```

- [ ] **Étape 6 : Lancer les tests et vérifier l'échec**

```powershell
pytest apps/projets/tests/test_services.py -v
```

Attendu : ÉCHEC avec
`ModuleNotFoundError: No module named 'apps.projets.services'`.

- [ ] **Étape 7 : Écrire `apps/projets/services.py`**

```python
"""Règles métier des projets.

Toute écriture passe par ce module. Chaque fonction reçoit l'utilisateur en
premier paramètre, contrôle son accès au module, puis restreint le résultat à
son périmètre : un responsable de projet ne voit que les projets qui lui sont
attribués, comme le prévoit le niveau « propre » de la matrice des droits.
"""
from django.db.models import Q

from apps.projets.models import Projet
from core.exceptions import RegleMetierViolee
from core.permissions import Acces, Module, exiger, filtrer_perimetre
from core.services import (
    appliquer_validation,
    obtenir_ou_introuvable,
    valider_champs,
)

CHAMPS_MODIFIABLES = frozenset({
    "code", "titre", "description", "budget_prevu", "budget_consomme",
    "date_debut", "date_fin", "etat", "type_action", "responsable", "region",
})


def _perimetre(utilisateur, queryset):
    """Restreint aux projets dont l'utilisateur est responsable, si besoin."""
    return filtrer_perimetre(
        queryset, utilisateur, Module.PROJETS, champ="responsable"
    )


def _verifier_coherence(donnees, instance=None):
    """Vérifie les règles que le modèle seul ne peut pas exprimer."""
    debut = donnees.get("date_debut", getattr(instance, "date_debut", None))
    fin = donnees.get("date_fin", getattr(instance, "date_fin", None))
    if debut and fin and str(fin) < str(debut):
        raise RegleMetierViolee(
            "La date de fin ne peut pas précéder la date de début."
        )


def _verifier_code_unique(code, exclure=None):
    existants = Projet.tous.filter(code=code)
    if exclure is not None:
        existants = existants.exclude(pk=exclure)
    if existants.exists():
        raise RegleMetierViolee(
            f"Le code « {code} » est déjà utilisé par un autre projet."
        )


def lister_projets(utilisateur, recherche="", etat=None):
    """Projets actifs visibles par l'utilisateur."""
    exiger(utilisateur, Module.PROJETS, Acces.LECTURE)

    resultats = Projet.objects.select_related(
        "type_action", "responsable", "region"
    )
    resultats = _perimetre(utilisateur, resultats)

    if recherche:
        resultats = resultats.filter(
            Q(code__icontains=recherche) | Q(titre__icontains=recherche)
        )
    if etat:
        resultats = resultats.filter(etat=etat)

    return resultats


def obtenir_projet(utilisateur, identifiant):
    """Retourne un projet actif du périmètre de l'utilisateur."""
    exiger(utilisateur, Module.PROJETS, Acces.LECTURE)
    return obtenir_ou_introuvable(
        _perimetre(utilisateur, Projet.objects), pk=identifiant
    )


def creer_projet(utilisateur, **donnees):
    exiger(utilisateur, Module.PROJETS, Acces.PROPRE)
    valider_champs(donnees, CHAMPS_MODIFIABLES)
    _verifier_coherence(donnees)
    _verifier_code_unique(donnees.get("code"))

    projet = Projet(**donnees)
    appliquer_validation(projet)
    projet.save()
    return projet


def modifier_projet(utilisateur, identifiant, **donnees):
    exiger(utilisateur, Module.PROJETS, Acces.PROPRE)
    valider_champs(donnees, CHAMPS_MODIFIABLES)

    projet = obtenir_ou_introuvable(
        _perimetre(utilisateur, Projet.objects), pk=identifiant
    )
    _verifier_coherence(donnees, instance=projet)
    if "code" in donnees:
        _verifier_code_unique(donnees["code"], exclure=identifiant)

    for champ, valeur in donnees.items():
        setattr(projet, champ, valeur)
    appliquer_validation(projet)
    projet.save()
    return projet
```

`obtenir_projet` passe par `_perimetre` : un responsable qui demande le projet
d'un collègue reçoit `Introuvable`, et non un refus de droit. C'est délibéré —
répondre « accès refusé » révélerait l'existence du projet.

- [ ] **Étape 8 : Lancer la suite complète**

```powershell
pytest -v
```

Attendu : SUCCÈS, **218 tests passés** (198 + 8 + 12).

---

## Tâche 6 : Campagnes, distributions et règle anti-doublon

C'est la tâche décisive du plan : elle porte le critère de réception le plus
important du cahier des charges.

**Fichiers :**
- Créer : `apps/campagnes/{__init__,apps,models,admin,services}.py`,
  `apps/campagnes/tests/{__init__,test_models,test_services}.py`
- Modifier : `config/settings/base.py` (`INSTALLED_APPS`), `conftest.py`

**Interfaces :**
- Consomme : `core.models.{Horodate, Archivable, SaisiPar, Campagne, Distribution, EtatCampagne}`,
  `apps.projets.models.Projet`, `apps.beneficiaires.models.Beneficiaire`,
  `apps.geographie.models.Village`
- Produit :
  - `apps.campagnes.models.CampagneAide` — campagne concrète, avec `projet` et
    `responsable`
  - `apps.campagnes.models.DistributionAide` — avec `beneficiaire`, `campagne`,
    `village`, `saisie_par`, et la contrainte
    `distribution_unique_par_campagne`
  - `apps.campagnes.services.lister_campagnes(utilisateur, annee=None, etat=None)`
  - `apps.campagnes.services.obtenir_campagne(utilisateur, identifiant)`
  - `apps.campagnes.services.creer_campagne(utilisateur, **donnees)`
  - `apps.campagnes.services.lister_distributions(utilisateur, campagne=None, village=None)`
  - `apps.campagnes.services.enregistrer_distribution(utilisateur, **donnees)`
  - `apps.campagnes.services.annuler_distribution(utilisateur, identifiant, motif)`
  - `apps.campagnes.services.a_deja_recu(utilisateur, beneficiaire, campagne)`

- [ ] **Étape 1 : Ajouter deux fixtures partagées**

Dans `conftest.py`, à la suite des fixtures existantes :

```python
@pytest.fixture
def type_action(db):
    from apps.projets.models import TypeAction

    return TypeAction.objects.create(libelle="Distribution alimentaire")


@pytest.fixture
def beneficiaire(db, village):
    from apps.beneficiaires.models import Beneficiaire

    return Beneficiaire.objects.create(
        nom="Rakoto", prenom="Jean", sexe="M", village=village
    )
```

- [ ] **Étape 2 : Écrire les tests de modèle en échec**

`apps/campagnes/tests/test_models.py` :

```python
"""Vérifie les campagnes, les distributions et la règle anti-doublon."""
import pytest
from django.db import IntegrityError

from apps.campagnes.models import CampagneAide, DistributionAide
from apps.projets.models import Projet
from core.models import EtatCampagne
from core.roles import Role


@pytest.fixture
def projet(db, type_action, creer_utilisateur):
    return Projet.objects.create(
        code="PROJ-2026-001",
        titre="Distribution alimentaire",
        budget_prevu="1000000.00",
        date_debut="2026-01-15",
        type_action=type_action,
        responsable=creer_utilisateur(Role.RESPONSABLE_PROJET),
    )


@pytest.fixture
def campagne(db, projet, creer_utilisateur):
    return CampagneAide.objects.create(
        code="RAM-2026",
        libelle="Ramadan",
        annee=2026,
        budget="500000.00",
        date_debut="2026-02-18",
        projet=projet,
        responsable=creer_utilisateur(Role.COORDINATEUR, nom="coord1"),
    )


@pytest.fixture
def agent(creer_utilisateur):
    return creer_utilisateur(Role.VOLONTAIRE, nom="agent1")


def test_campagne_creee_planifiee(campagne):
    assert campagne.etat == EtatCampagne.PLANIFIEE


def test_representation_de_la_campagne(campagne):
    assert str(campagne) == "Ramadan 2026"


def test_distribution_enregistree(campagne, beneficiaire, village, agent):
    distribution = DistributionAide.objects.create(
        beneficiaire=beneficiaire,
        campagne=campagne,
        village=village,
        date_distribution="2026-02-20",
        saisie_par=agent,
    )
    assert distribution.pk is not None
    assert distribution.quantite == 1


@pytest.mark.django_db
def test_deux_distributions_pour_la_meme_campagne_refusees(
    campagne, beneficiaire, village, agent
):
    """Critère de réception : pas de doublon de distribution."""
    DistributionAide.objects.create(
        beneficiaire=beneficiaire, campagne=campagne, village=village,
        date_distribution="2026-02-20", saisie_par=agent,
    )
    with pytest.raises(IntegrityError):
        DistributionAide.objects.create(
            beneficiaire=beneficiaire, campagne=campagne, village=village,
            date_distribution="2026-02-25", saisie_par=agent,
        )


@pytest.mark.django_db
def test_une_distribution_annulee_libere_la_place(
    campagne, beneficiaire, village, agent
):
    """Une aide annulée n'a pas été reçue : la vraie doit pouvoir être saisie."""
    premiere = DistributionAide.objects.create(
        beneficiaire=beneficiaire, campagne=campagne, village=village,
        date_distribution="2026-02-20", saisie_par=agent,
    )
    premiere.archive = True
    premiere.save()

    seconde = DistributionAide.objects.create(
        beneficiaire=beneficiaire, campagne=campagne, village=village,
        date_distribution="2026-02-25", saisie_par=agent,
    )
    assert seconde.pk is not None
    assert DistributionAide.objects.count() == 1
    assert DistributionAide.tous.count() == 2


@pytest.mark.django_db
def test_deux_campagnes_differentes_autorisees(
    campagne, projet, beneficiaire, village, agent, creer_utilisateur
):
    """Recevoir Ramadan puis Kurban la même année est légitime."""
    autre = CampagneAide.objects.create(
        code="KUR-2026", libelle="Kurban", annee=2026, budget="300000.00",
        date_debut="2026-06-06", projet=projet,
        responsable=creer_utilisateur(Role.COORDINATEUR, nom="coord2"),
    )
    DistributionAide.objects.create(
        beneficiaire=beneficiaire, campagne=campagne, village=village,
        date_distribution="2026-02-20", saisie_par=agent,
    )
    DistributionAide.objects.create(
        beneficiaire=beneficiaire, campagne=autre, village=village,
        date_distribution="2026-06-10", saisie_par=agent,
    )
    assert DistributionAide.objects.count() == 2


def test_suppression_du_beneficiaire_bloquee(
    campagne, beneficiaire, village, agent
):
    """L'historique des aides ne doit pas pouvoir disparaître."""
    from django.db.models import ProtectedError

    DistributionAide.objects.create(
        beneficiaire=beneficiaire, campagne=campagne, village=village,
        date_distribution="2026-02-20", saisie_par=agent,
    )
    with pytest.raises(ProtectedError):
        beneficiaire.delete()


def test_representation_de_la_distribution(
    campagne, beneficiaire, village, agent
):
    distribution = DistributionAide.objects.create(
        beneficiaire=beneficiaire, campagne=campagne, village=village,
        date_distribution="2026-02-20", saisie_par=agent,
    )
    assert str(distribution) == "Rakoto Jean — Ramadan 2026"
```

- [ ] **Étape 3 : Lancer les tests et vérifier l'échec**

```powershell
pytest apps/campagnes/tests/test_models.py -v
```

Attendu : ÉCHEC avec `ModuleNotFoundError: No module named 'apps.campagnes'`.

- [ ] **Étape 4 : Écrire `apps/campagnes/models.py`**

```python
"""Campagnes d'aide et distributions aux bénéficiaires."""
from django.conf import settings
from django.db import models

from apps.beneficiaires.models import Beneficiaire
from apps.geographie.models import Village
from apps.projets.models import Projet
from core.models import Archivable, Campagne, Distribution, Horodate, SaisiPar


class CampagneAide(Campagne, Horodate, Archivable):
    """Campagne concrète rattachée à un projet.

    Hérite du tronc commun défini dans `core` : code, libellé, année, budget,
    dates et état. Les campagnes spécialisées d'un lot ultérieur — Ramadan avec
    la composition de ses colis, Kurban avec ses zébus — hériteront du même
    abstrait plutôt que de réécrire ces champs.
    """

    projet = models.ForeignKey(
        Projet,
        on_delete=models.PROTECT,
        related_name="campagnes",
        verbose_name="projet",
    )
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="campagnes_animees",
        verbose_name="responsable",
    )

    class Meta:
        verbose_name = "campagne"
        verbose_name_plural = "campagnes"
        ordering = ["-annee", "libelle"]
        constraints = [
            models.UniqueConstraint(
                fields=["code"],
                condition=models.Q(archive=False),
                name="campagne_code_unique_si_active",
            )
        ]


class DistributionAide(Distribution, Horodate, Archivable, SaisiPar):
    """Aide effectivement remise à un bénéficiaire au titre d'une campagne.

    Une seule entité pour toutes les formes d'aide. Le cahier des charges
    demande de vérifier si une personne a déjà reçu un colis Ramadan, de la
    viande Kurban, des vêtements, un forage ou une bourse : cinq vérifications
    réparties sur cinq tables offriraient cinq occasions de laisser passer un
    doublon. Ici la règle est portée une fois, par le SGBD.
    """

    beneficiaire = models.ForeignKey(
        Beneficiaire,
        on_delete=models.PROTECT,
        related_name="distributions",
        verbose_name="bénéficiaire",
    )
    campagne = models.ForeignKey(
        CampagneAide,
        on_delete=models.PROTECT,
        related_name="distributions",
        verbose_name="campagne",
    )
    village = models.ForeignKey(
        Village,
        on_delete=models.PROTECT,
        related_name="distributions",
        verbose_name="village de distribution",
        help_text=(
            "Lieu où l'aide a été remise, qui peut différer du village de "
            "résidence du bénéficiaire."
        ),
    )

    class Meta:
        verbose_name = "distribution"
        verbose_name_plural = "distributions"
        ordering = ["-date_distribution"]
        indexes = [
            models.Index(
                fields=["campagne", "village"],
                name="distribution_campagne_village",
            ),
        ]
        constraints = [
            # Un bénéficiaire ne peut recevoir qu'une fois la même campagne.
            # La condition sur l'archivage est essentielle : sans elle, une
            # distribution saisie par erreur puis annulée bloquerait
            # définitivement la distribution réelle.
            models.UniqueConstraint(
                fields=["beneficiaire", "campagne"],
                condition=models.Q(archive=False),
                name="distribution_unique_par_campagne",
            ),
        ]

    def __str__(self):
        return f"{self.beneficiaire} — {self.campagne}"
```

`apps/campagnes/apps.py` :

```python
from django.apps import AppConfig


class CampagnesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.campagnes"
    label = "campagnes"
    verbose_name = "Campagnes et distributions"
```

`apps/campagnes/admin.py` :

```python
from django.contrib import admin

from apps.campagnes.models import CampagneAide, DistributionAide


@admin.register(CampagneAide)
class CampagneAideAdmin(admin.ModelAdmin):
    list_display = ["code", "libelle", "annee", "etat", "projet"]
    list_filter = ["etat", "annee"]
    search_fields = ["code", "libelle"]


@admin.register(DistributionAide)
class DistributionAideAdmin(admin.ModelAdmin):
    list_display = [
        "beneficiaire", "campagne", "village", "date_distribution", "archive",
    ]
    list_filter = ["campagne", "archive"]
    search_fields = ["beneficiaire__nom", "beneficiaire__prenom"]
```

- [ ] **Étape 5 : Déclarer l'application et migrer**

Ajouter `"apps.campagnes",` à `INSTALLED_APPS`, puis :

```powershell
python manage.py makemigrations campagnes
python manage.py migrate
pytest apps/campagnes/tests/test_models.py -v
```

Attendu : SUCCÈS, 8 tests passés.

- [ ] **Étape 6 : Vérifier que la contrainte existe réellement en base**

```powershell
python -c "import sqlite3; c=sqlite3.connect('db.sqlite3'); print([r[1] for r in c.execute(\"select name, sql from sqlite_master where name='distribution_unique_par_campagne'\")])"
```

Attendu : un index unique contenant `WHERE NOT \"archive\"` ou
`WHERE \"archive\" = 0`. Si rien ne sort, la contrainte n'a pas été créée et la
règle anti-doublon ne tient qu'au code applicatif — ce serait un échec de cette
tâche.

- [ ] **Étape 7 : Écrire les tests de services en échec**

`apps/campagnes/tests/test_services.py` :

```python
"""Vérifie les règles métier des distributions, dont la prévention des doublons."""
import pytest

from apps.campagnes.models import CampagneAide, DistributionAide
from apps.campagnes.services import (
    a_deja_recu,
    annuler_distribution,
    creer_campagne,
    enregistrer_distribution,
    lister_campagnes,
    lister_distributions,
    obtenir_campagne,
)
from apps.projets.models import Projet
from core.exceptions import Introuvable, PermissionRefusee, RegleMetierViolee
from core.roles import Role


@pytest.fixture
def coordinateur(creer_utilisateur):
    return creer_utilisateur(Role.COORDINATEUR)


@pytest.fixture
def volontaire(creer_utilisateur):
    return creer_utilisateur(Role.VOLONTAIRE, nom="vol1")


@pytest.fixture
def projet(db, type_action, creer_utilisateur):
    return Projet.objects.create(
        code="PROJ-2026-001", titre="Distribution alimentaire",
        budget_prevu="1000000.00", date_debut="2026-01-15",
        type_action=type_action,
        responsable=creer_utilisateur(Role.RESPONSABLE_PROJET, nom="resp1"),
    )


@pytest.fixture
def campagne(coordinateur, projet):
    return creer_campagne(
        coordinateur, code="RAM-2026", libelle="Ramadan", annee=2026,
        budget="500000.00", date_debut="2026-02-18", projet=projet,
        responsable=coordinateur,
    )


def test_coordinateur_cree_une_campagne(campagne):
    assert campagne.pk is not None


def test_volontaire_ne_peut_pas_creer_de_campagne(volontaire, projet):
    with pytest.raises(PermissionRefusee):
        creer_campagne(
            volontaire, code="RAM-2026", libelle="Ramadan", annee=2026,
            budget="500000.00", date_debut="2026-02-18", projet=projet,
            responsable=volontaire,
        )


def test_volontaire_enregistre_une_distribution(
    volontaire, campagne, beneficiaire, village
):
    """Le volontaire saisit les distributions sur le terrain."""
    distribution = enregistrer_distribution(
        volontaire, beneficiaire=beneficiaire, campagne=campagne,
        village=village, date_distribution="2026-02-20",
    )
    assert distribution.saisie_par == volontaire


def test_comptable_ne_peut_pas_enregistrer(
    creer_utilisateur, campagne, beneficiaire, village
):
    comptable = creer_utilisateur(Role.COMPTABLE)
    with pytest.raises(PermissionRefusee):
        enregistrer_distribution(
            comptable, beneficiaire=beneficiaire, campagne=campagne,
            village=village, date_distribution="2026-02-20",
        )


def test_doublon_refuse_avec_un_message_clair(
    volontaire, campagne, beneficiaire, village
):
    """Le service doit expliquer, pas laisser remonter une erreur technique."""
    enregistrer_distribution(
        volontaire, beneficiaire=beneficiaire, campagne=campagne,
        village=village, date_distribution="2026-02-20",
    )
    with pytest.raises(RegleMetierViolee) as erreur:
        enregistrer_distribution(
            volontaire, beneficiaire=beneficiaire, campagne=campagne,
            village=village, date_distribution="2026-02-25",
        )
    assert "déjà reçu" in str(erreur.value)


def test_a_deja_recu_repond_vrai_apres_distribution(
    volontaire, campagne, beneficiaire, village
):
    assert a_deja_recu(volontaire, beneficiaire, campagne) is False
    enregistrer_distribution(
        volontaire, beneficiaire=beneficiaire, campagne=campagne,
        village=village, date_distribution="2026-02-20",
    )
    assert a_deja_recu(volontaire, beneficiaire, campagne) is True


def test_annulation_libere_la_place(
    volontaire, campagne, beneficiaire, village
):
    distribution = enregistrer_distribution(
        volontaire, beneficiaire=beneficiaire, campagne=campagne,
        village=village, date_distribution="2026-02-20",
    )
    annuler_distribution(volontaire, distribution.pk, motif="Erreur de saisie")

    assert a_deja_recu(volontaire, beneficiaire, campagne) is False
    seconde = enregistrer_distribution(
        volontaire, beneficiaire=beneficiaire, campagne=campagne,
        village=village, date_distribution="2026-02-25",
    )
    assert seconde.pk is not None


def test_annulation_conserve_la_trace(
    volontaire, campagne, beneficiaire, village
):
    """L'historique ne disparaît pas : l'archivage remplace la suppression."""
    distribution = enregistrer_distribution(
        volontaire, beneficiaire=beneficiaire, campagne=campagne,
        village=village, date_distribution="2026-02-20",
    )
    annuler_distribution(volontaire, distribution.pk, motif="Erreur de saisie")

    archivee = DistributionAide.tous.get(pk=distribution.pk)
    assert archivee.archive is True
    assert "Erreur de saisie" in archivee.observation


def test_volontaire_ne_voit_que_ses_saisies(
    volontaire, coordinateur, campagne, beneficiaire, village, creer_utilisateur
):
    """Le niveau « propre » s'applique aux distributions."""
    autre = creer_utilisateur(Role.VOLONTAIRE, nom="vol2")
    from apps.beneficiaires.models import Beneficiaire

    second = Beneficiaire.objects.create(
        nom="Rabe", prenom="Paul", sexe="M", village=village
    )
    enregistrer_distribution(
        volontaire, beneficiaire=beneficiaire, campagne=campagne,
        village=village, date_distribution="2026-02-20",
    )
    enregistrer_distribution(
        autre, beneficiaire=second, campagne=campagne, village=village,
        date_distribution="2026-02-21",
    )
    assert lister_distributions(volontaire).count() == 1
    assert lister_distributions(coordinateur).count() == 2


def test_filtre_par_village(
    volontaire, campagne, beneficiaire, village
):
    enregistrer_distribution(
        volontaire, beneficiaire=beneficiaire, campagne=campagne,
        village=village, date_distribution="2026-02-20",
    )
    assert lister_distributions(volontaire, village=village).count() == 1


def test_campagne_introuvable(coordinateur):
    with pytest.raises(Introuvable):
        obtenir_campagne(coordinateur, 999999)


def test_liste_des_campagnes_filtree_par_annee(coordinateur, campagne):
    assert lister_campagnes(coordinateur, annee=2026).count() == 1
    assert lister_campagnes(coordinateur, annee=2025).count() == 0


def test_champ_inconnu_refuse_a_l_enregistrement(
    volontaire, campagne, beneficiaire, village
):
    with pytest.raises(RegleMetierViolee):
        enregistrer_distribution(
            volontaire, beneficiaire=beneficiaire, campagne=campagne,
            village=village, date_distribution="2026-02-20", archive=True,
        )
```

- [ ] **Étape 8 : Lancer les tests et vérifier l'échec**

```powershell
pytest apps/campagnes/tests/test_services.py -v
```

Attendu : ÉCHEC avec
`ModuleNotFoundError: No module named 'apps.campagnes.services'`.

- [ ] **Étape 9 : Écrire `apps/campagnes/services.py`**

```python
"""Règles métier des campagnes et des distributions.

La règle centrale du projet vit ici : un bénéficiaire ne peut pas recevoir
deux fois la même campagne. Elle est appliquée à deux niveaux — une contrainte
du SGBD qui la rend structurellement vraie, et une vérification préalable dans
ce module qui produit un message compréhensible plutôt qu'une erreur technique.
"""
from apps.campagnes.models import CampagneAide, DistributionAide
from core.exceptions import RegleMetierViolee
from core.permissions import Acces, Module, exiger, filtrer_perimetre
from core.services import (
    appliquer_validation,
    obtenir_ou_introuvable,
    valider_champs,
)

CHAMPS_CAMPAGNE = frozenset({
    "code", "libelle", "annee", "budget", "date_debut", "date_fin", "etat",
    "projet", "responsable",
})

CHAMPS_DISTRIBUTION = frozenset({
    "beneficiaire", "campagne", "village", "date_distribution", "quantite",
    "unite", "observation",
})


# --- Campagnes -------------------------------------------------------------

def lister_campagnes(utilisateur, annee=None, etat=None):
    exiger(utilisateur, Module.PROJETS, Acces.LECTURE)

    resultats = CampagneAide.objects.select_related("projet", "responsable")
    if annee:
        resultats = resultats.filter(annee=annee)
    if etat:
        resultats = resultats.filter(etat=etat)
    return resultats


def obtenir_campagne(utilisateur, identifiant):
    exiger(utilisateur, Module.PROJETS, Acces.LECTURE)
    return obtenir_ou_introuvable(CampagneAide.objects, pk=identifiant)


def creer_campagne(utilisateur, **donnees):
    exiger(utilisateur, Module.PROJETS, Acces.PROPRE)
    valider_champs(donnees, CHAMPS_CAMPAGNE)

    campagne = CampagneAide(**donnees)
    appliquer_validation(campagne)
    campagne.save()
    return campagne


# --- Distributions ---------------------------------------------------------

def _perimetre(utilisateur, queryset):
    """Restreint aux distributions saisies par l'utilisateur, si besoin.

    Le responsable de projet et le volontaire ont le niveau « propre » sur ce
    module : sans ce filtrage, ils obtiendraient l'intégralité des
    distributions de l'ONG.
    """
    return filtrer_perimetre(queryset, utilisateur, Module.DISTRIBUTIONS)


def a_deja_recu(utilisateur, beneficiaire, campagne):
    """Ce bénéficiaire a-t-il déjà reçu une aide valide pour cette campagne ?

    Ne compte que les distributions actives : une aide annulée n'a pas été
    reçue. La question est posée sans restriction de périmètre — un volontaire
    doit savoir qu'une personne a déjà été servie, même par un collègue, sinon
    la prévention des doublons ne fonctionnerait plus.
    """
    exiger(utilisateur, Module.DISTRIBUTIONS, Acces.LECTURE)
    return DistributionAide.objects.filter(
        beneficiaire=beneficiaire, campagne=campagne
    ).exists()


def lister_distributions(utilisateur, campagne=None, village=None):
    exiger(utilisateur, Module.DISTRIBUTIONS, Acces.LECTURE)

    resultats = DistributionAide.objects.select_related(
        "beneficiaire", "campagne", "village", "saisie_par"
    )
    resultats = _perimetre(utilisateur, resultats)

    if campagne is not None:
        resultats = resultats.filter(campagne=campagne)
    if village is not None:
        resultats = resultats.filter(village=village)
    return resultats


def enregistrer_distribution(utilisateur, **donnees):
    """Enregistre une aide remise, après vérification du doublon.

    La contrainte du SGBD rend le doublon impossible ; cette vérification
    préalable existe pour que l'opérateur reçoive une explication en français
    plutôt qu'une erreur d'intégrité.
    """
    exiger(utilisateur, Module.DISTRIBUTIONS, Acces.PROPRE)
    valider_champs(donnees, CHAMPS_DISTRIBUTION)

    beneficiaire = donnees.get("beneficiaire")
    campagne = donnees.get("campagne")
    if DistributionAide.objects.filter(
        beneficiaire=beneficiaire, campagne=campagne
    ).exists():
        raise RegleMetierViolee(
            f"{beneficiaire} a déjà reçu une aide pour la campagne "
            f"« {campagne} »."
        )

    distribution = DistributionAide(saisie_par=utilisateur, **donnees)
    appliquer_validation(distribution)
    distribution.save()
    return distribution


def annuler_distribution(utilisateur, identifiant, motif):
    """Annule une distribution sans l'effacer.

    L'enregistrement est archivé et le motif conservé : l'historique de ce qui
    a été saisi, puis annulé, reste consultable. La place se libère pour une
    nouvelle distribution, la contrainte d'unicité ne portant que sur les
    lignes actives.
    """
    exiger(utilisateur, Module.DISTRIBUTIONS, Acces.PROPRE)
    if not motif:
        raise RegleMetierViolee("Une annulation doit être motivée.")

    distribution = obtenir_ou_introuvable(
        _perimetre(utilisateur, DistributionAide.objects), pk=identifiant
    )
    distribution.archive = True
    distribution.observation = (
        f"{distribution.observation}\nAnnulée : {motif}".strip()
    )
    distribution.save(
        update_fields=["archive", "observation", "date_modification"]
    )
    return distribution
```

- [ ] **Étape 10 : Lancer la suite complète**

```powershell
pytest -v
```

Attendu : SUCCÈS, **239 tests passés** (218 + 8 + 13).

---

## Tâche 7 : Historique des aides d'un bénéficiaire

Le cahier des charges demande de pouvoir vérifier si une personne a déjà reçu
une aide — colis Ramadan, viande Kurban, vêtements, forage, bourse. Cette tâche
rend cette vérification consultable depuis la fiche du bénéficiaire.

**Fichiers :**
- Modifier : `apps/beneficiaires/services.py`, `apps/beneficiaires/views.py`,
  `templates/beneficiaires/detail.html`
- Test : `apps/beneficiaires/tests/test_services.py`,
  `apps/beneficiaires/tests/test_views.py`

**Interfaces :**
- Consomme : `apps.campagnes.services.lister_distributions`
- Produit : `apps.beneficiaires.services.historique_aides(utilisateur, identifiant)`
  — retourne les distributions actives du bénéficiaire, campagne comprise,
  triées de la plus récente à la plus ancienne

> **Note d'implémentation.** L'import se fait à l'intérieur de la fonction, et
> non en tête de module : `apps.campagnes` importe déjà `apps.beneficiaires`
> pour son modèle, et un import croisé au niveau du module provoquerait une
> erreur au démarrage de Django.

- [ ] **Étape 1 : Écrire les tests en échec**

Ajouter à `apps/beneficiaires/tests/test_services.py` :

```python
def test_historique_vide_pour_un_nouveau_beneficiaire(
    coordinateur, beneficiaire
):
    from apps.beneficiaires.services import historique_aides

    assert historique_aides(coordinateur, beneficiaire.pk).count() == 0


def test_historique_liste_les_aides_recues(
    coordinateur, beneficiaire, village, type_action, creer_utilisateur
):
    from apps.beneficiaires.services import historique_aides
    from apps.campagnes.services import creer_campagne, enregistrer_distribution
    from apps.projets.models import Projet
    from core.roles import Role

    projet = Projet.objects.create(
        code="PROJ-2026-001", titre="Distribution", budget_prevu="1000.00",
        date_debut="2026-01-15", type_action=type_action,
        responsable=creer_utilisateur(Role.RESPONSABLE_PROJET, nom="resp9"),
    )
    campagne = creer_campagne(
        coordinateur, code="RAM-2026", libelle="Ramadan", annee=2026,
        budget="500.00", date_debut="2026-02-18", projet=projet,
        responsable=coordinateur,
    )
    enregistrer_distribution(
        coordinateur, beneficiaire=beneficiaire, campagne=campagne,
        village=village, date_distribution="2026-02-20",
    )

    historique = historique_aides(coordinateur, beneficiaire.pk)
    assert historique.count() == 1
    assert historique.first().campagne.libelle == "Ramadan"


def test_historique_ignore_les_aides_annulees(
    coordinateur, beneficiaire, village, type_action, creer_utilisateur
):
    from apps.beneficiaires.services import historique_aides
    from apps.campagnes.services import (
        annuler_distribution,
        creer_campagne,
        enregistrer_distribution,
    )
    from apps.projets.models import Projet
    from core.roles import Role

    projet = Projet.objects.create(
        code="PROJ-2026-002", titre="Distribution", budget_prevu="1000.00",
        date_debut="2026-01-15", type_action=type_action,
        responsable=creer_utilisateur(Role.RESPONSABLE_PROJET, nom="resp10"),
    )
    campagne = creer_campagne(
        coordinateur, code="RAM-2027", libelle="Ramadan", annee=2027,
        budget="500.00", date_debut="2027-02-08", projet=projet,
        responsable=coordinateur,
    )
    distribution = enregistrer_distribution(
        coordinateur, beneficiaire=beneficiaire, campagne=campagne,
        village=village, date_distribution="2027-02-10",
    )
    annuler_distribution(coordinateur, distribution.pk, motif="Erreur")

    assert historique_aides(coordinateur, beneficiaire.pk).count() == 0


def test_historique_refuse_a_un_comptable(comptable, beneficiaire):
    from apps.beneficiaires.services import historique_aides
    from core.exceptions import PermissionRefusee

    with pytest.raises(PermissionRefusee):
        historique_aides(comptable, beneficiaire.pk)
```

Ajouter à `apps/beneficiaires/tests/test_views.py` :

```python
def test_la_fiche_affiche_la_section_historique(client, village):
    from apps.beneficiaires.models import Beneficiaire

    connecter(client, Role.COORDINATEUR)
    beneficiaire = Beneficiaire.objects.create(
        nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN, village=village
    )
    reponse = client.get(
        reverse("beneficiaires:detail", args=[beneficiaire.pk])
    )
    assert reponse.status_code == 200
    assert "Aides reçues".encode() in reponse.content
```

- [ ] **Étape 2 : Lancer les tests et vérifier l'échec**

```powershell
pytest apps/beneficiaires/tests/ -v
```

Attendu : ÉCHEC avec `cannot import name 'historique_aides'`.

- [ ] **Étape 3 : Ajouter `historique_aides` aux services des bénéficiaires**

À la fin de `apps/beneficiaires/services.py` :

```python
def historique_aides(utilisateur, identifiant):
    """Aides valides reçues par ce bénéficiaire, de la plus récente à la plus ancienne.

    Répond à l'exigence de vérifier si une personne a déjà été servie — colis
    Ramadan, viande Kurban, vêtements, forage ou bourse — avant de lui
    attribuer une nouvelle aide.

    L'import est local : le module des campagnes importe déjà celui des
    bénéficiaires pour son modèle, et un import croisé en tête de fichier
    empêcherait Django de démarrer.
    """
    from apps.campagnes.services import lister_distributions

    beneficiaire = obtenir_beneficiaire(utilisateur, identifiant)
    return (
        lister_distributions(utilisateur)
        .filter(beneficiaire=beneficiaire)
        .order_by("-date_distribution")
    )
```

`lister_distributions` applique son propre contrôle d'accès et son propre
filtrage par périmètre : l'historique reste donc cohérent avec ce que
l'utilisateur a le droit de voir.

- [ ] **Étape 4 : Afficher l'historique sur la fiche**

Dans `apps/beneficiaires/views.py`, vue `detail`, ajouter au contexte :

```python
            "historique": historique_aides(requete.user, identifiant),
```

et importer `historique_aides`.

Dans `templates/beneficiaires/detail.html`, avant les liens de bas de page :

```html
  <h2>Aides reçues</h2>
  <table>
    <thead>
      <tr><th>Campagne</th><th>Date</th><th>Village</th><th>Quantité</th></tr>
    </thead>
    <tbody>
      {% for aide in historique %}
        <tr>
          <td>{{ aide.campagne }}</td>
          <td>{{ aide.date_distribution }}</td>
          <td>{{ aide.village }}</td>
          <td>{{ aide.quantite }} {{ aide.unite }}</td>
        </tr>
      {% empty %}
        <tr><td colspan="4">Aucune aide enregistrée à ce jour.</td></tr>
      {% endfor %}
    </tbody>
  </table>
```

- [ ] **Étape 5 : Lancer la suite complète**

```powershell
pytest -v
python manage.py check
```

Attendu : SUCCÈS, **244 tests passés** (239 + 5), `check` silencieux.

---

## Tâche 8 : Vues, formulaires et gabarits des distributions

**Fichiers :**
- Créer : `apps/campagnes/{forms,views,urls}.py`,
  `apps/campagnes/tests/test_views.py`,
  `templates/campagnes/{campagnes,distributions,formulaire_distribution}.html`
- Modifier : `config/urls.py`, `templates/base.html`

**Interfaces :**
- Consomme : toutes les fonctions de `apps.campagnes.services`,
  `core.vues.traduire_erreurs_metier`
- Produit : les routes nommées `campagnes:liste`, `campagnes:distributions`,
  `campagnes:enregistrer`, `campagnes:annuler`

- [ ] **Étape 1 : Écrire les tests en échec**

`apps/campagnes/tests/test_views.py` :

```python
"""Vérifie que les vues des distributions appliquent les droits des services."""
import pytest
from django.urls import reverse

from apps.campagnes.models import DistributionAide
from apps.campagnes.services import creer_campagne, enregistrer_distribution
from apps.projets.models import Projet
from core.roles import Role


@pytest.fixture
def coordinateur(creer_utilisateur):
    return creer_utilisateur(Role.COORDINATEUR)


@pytest.fixture
def campagne(coordinateur, type_action, creer_utilisateur):
    projet = Projet.objects.create(
        code="PROJ-2026-001", titre="Distribution", budget_prevu="1000.00",
        date_debut="2026-01-15", type_action=type_action,
        responsable=creer_utilisateur(Role.RESPONSABLE_PROJET, nom="respv"),
    )
    return creer_campagne(
        coordinateur, code="RAM-2026", libelle="Ramadan", annee=2026,
        budget="500.00", date_debut="2026-02-18", projet=projet,
        responsable=coordinateur,
    )


def connecter(client, creer_utilisateur, role, nom="agent"):
    utilisateur = creer_utilisateur(role, nom=nom)
    client.force_login(utilisateur)
    return utilisateur


def test_liste_refusee_a_l_anonyme(client, db):
    reponse = client.get(reverse("campagnes:distributions"), follow=True)
    assert reponse.status_code == 200
    assert b"csrfmiddlewaretoken" in reponse.content


def test_liste_accessible_au_coordinateur(client, creer_utilisateur, campagne):
    connecter(client, creer_utilisateur, Role.COORDINATEUR, nom="c2")
    assert client.get(reverse("campagnes:distributions")).status_code == 200


def test_liste_refusee_au_comptable(client, creer_utilisateur, campagne):
    connecter(client, creer_utilisateur, Role.COMPTABLE, nom="cp2")
    assert client.get(reverse("campagnes:distributions")).status_code == 403


def test_enregistrement_par_un_volontaire(
    client, creer_utilisateur, campagne, beneficiaire, village
):
    connecter(client, creer_utilisateur, Role.VOLONTAIRE, nom="v2")
    reponse = client.post(
        reverse("campagnes:enregistrer"),
        {
            "beneficiaire": beneficiaire.pk, "campagne": campagne.pk,
            "village": village.pk, "date_distribution": "2026-02-20",
            "quantite": "1", "unite": "colis",
        },
    )
    assert reponse.status_code == 302
    assert DistributionAide.objects.count() == 1


def test_doublon_affiche_une_erreur_sans_erreur_serveur(
    client, creer_utilisateur, campagne, beneficiaire, village
):
    """Le doublon doit produire un message lisible, pas une erreur 500."""
    volontaire = connecter(client, creer_utilisateur, Role.VOLONTAIRE, nom="v3")
    enregistrer_distribution(
        volontaire, beneficiaire=beneficiaire, campagne=campagne,
        village=village, date_distribution="2026-02-20",
    )
    reponse = client.post(
        reverse("campagnes:enregistrer"),
        {
            "beneficiaire": beneficiaire.pk, "campagne": campagne.pk,
            "village": village.pk, "date_distribution": "2026-02-25",
            "quantite": "1", "unite": "colis",
        },
    )
    assert reponse.status_code == 200
    assert "déjà reçu".encode() in reponse.content
    assert DistributionAide.objects.count() == 1


def test_distribution_inexistante_donne_404(client, creer_utilisateur, campagne):
    connecter(client, creer_utilisateur, Role.COORDINATEUR, nom="c3")
    reponse = client.post(
        reverse("campagnes:annuler", args=[999999]), {"motif": "Erreur"}
    )
    assert reponse.status_code == 404


def test_annulation_par_le_coordinateur(
    client, creer_utilisateur, campagne, beneficiaire, village
):
    coordinateur = connecter(
        client, creer_utilisateur, Role.COORDINATEUR, nom="c4"
    )
    distribution = enregistrer_distribution(
        coordinateur, beneficiaire=beneficiaire, campagne=campagne,
        village=village, date_distribution="2026-02-20",
    )
    reponse = client.post(
        reverse("campagnes:annuler", args=[distribution.pk]),
        {"motif": "Erreur de saisie"},
    )
    assert reponse.status_code == 302
    assert DistributionAide.objects.count() == 0
    assert DistributionAide.tous.count() == 1
```

- [ ] **Étape 2 : Lancer les tests et vérifier l'échec**

```powershell
pytest apps/campagnes/tests/test_views.py -v
```

Attendu : ÉCHEC avec
`NoReverseMatch: 'campagnes' is not a registered namespace`.

- [ ] **Étape 3 : Écrire `apps/campagnes/forms.py`**

```python
"""Formulaires des distributions.

Le formulaire ne valide que la forme des données. Les règles métier — droits,
prévention des doublons, traçabilité de la saisie — appartiennent à la couche
de services.
"""
from django import forms

from apps.campagnes.models import DistributionAide
from apps.campagnes.services import CHAMPS_DISTRIBUTION

_ORDRE_AFFICHAGE = [
    "beneficiaire", "campagne", "village", "date_distribution",
    "quantite", "unite", "observation",
]


class FormulaireDistribution(forms.ModelForm):
    class Meta:
        model = DistributionAide
        # L'ordre est explicite pour la lisibilité du formulaire ;
        # un test vérifie que l'ensemble coïncide avec CHAMPS_DISTRIBUTION.
        fields = _ORDRE_AFFICHAGE
        widgets = {
            "date_distribution": forms.DateInput(attrs={"type": "date"}),
        }


class FormulaireAnnulation(forms.Form):
    motif = forms.CharField(
        label="Motif de l'annulation",
        max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "Erreur de saisie…"}),
    )
```

> **Une incohérence de la matrice à connaître, qui ne bloque pas cette tâche.**
> Le champ `campagne` du formulaire propose la liste des campagnes, alors que la
> matrice n'accorde au volontaire **aucun** droit sur le module des projets, où
> vivent les campagnes. Le formulaire n'appelle pas `lister_campagnes` — il
> construit son propre choix depuis le modèle — donc rien n'échoue.
>
> Mais un volontaire doit forcément choisir une campagne pour saisir une
> distribution : soit la matrice devrait lui accorder la lecture sur les
> projets, soit le libellé d'une campagne doit être considéré comme relevant du
> module des distributions plutôt que de celui des projets. Une campagne n'étant
> pas une donnée personnelle, le second point de vue paraît le plus juste.
>
> À porter à la liste des points à faire trancher par l'ONG, avec la question de
> l'écriture des données sensibles. Ne modifie **pas** la matrice dans cette
> tâche.

Ajouter à `apps/campagnes/tests/test_views.py` :

```python
def test_champs_du_formulaire_coherents_avec_le_service():
    from apps.campagnes.forms import FormulaireDistribution
    from apps.campagnes.services import CHAMPS_DISTRIBUTION

    assert set(FormulaireDistribution.Meta.fields) == CHAMPS_DISTRIBUTION
```

- [ ] **Étape 4 : Écrire `apps/campagnes/views.py`**

```python
"""Vues des campagnes et des distributions.

Aucune règle métier ici : chaque vue appelle un service. Le décorateur
`traduire_erreurs_metier` convertit les refus d'accès en 403 et les ressources
absentes en 404 ; `RegleMetierViolee` est rattachée au formulaire, car c'est
une erreur de saisie que l'opérateur doit pouvoir corriger.
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.campagnes.forms import FormulaireAnnulation, FormulaireDistribution
from apps.campagnes.services import (
    annuler_distribution,
    enregistrer_distribution,
    lister_campagnes,
    lister_distributions,
)
from core.exceptions import RegleMetierViolee
from core.permissions import Module, peut_ecrire
from core.vues import traduire_erreurs_metier


@login_required
@traduire_erreurs_metier
def campagnes(requete):
    return render(
        requete,
        "campagnes/campagnes.html",
        {"campagnes": lister_campagnes(requete.user)},
    )


@login_required
@traduire_erreurs_metier
def distributions(requete):
    return render(
        requete,
        "campagnes/distributions.html",
        {
            "distributions": lister_distributions(requete.user),
            "peut_enregistrer": peut_ecrire(requete.user, Module.DISTRIBUTIONS),
        },
    )


@login_required
@traduire_erreurs_metier
def enregistrer(requete):
    formulaire = FormulaireDistribution(
        requete.POST if requete.method == "POST" else None
    )

    if requete.method == "POST" and formulaire.is_valid():
        try:
            enregistrer_distribution(requete.user, **formulaire.cleaned_data)
        except RegleMetierViolee as erreur:
            formulaire.add_error(None, str(erreur))
        else:
            return redirect("campagnes:distributions")

    return render(
        requete,
        "campagnes/formulaire_distribution.html",
        {"formulaire": formulaire},
    )


@login_required
@traduire_erreurs_metier
def annuler(requete, identifiant):
    formulaire = FormulaireAnnulation(
        requete.POST if requete.method == "POST" else None
    )

    if requete.method == "POST" and formulaire.is_valid():
        try:
            annuler_distribution(
                requete.user, identifiant, motif=formulaire.cleaned_data["motif"]
            )
        except RegleMetierViolee as erreur:
            formulaire.add_error(None, str(erreur))
        else:
            return redirect("campagnes:distributions")

    return render(
        requete,
        "campagnes/formulaire_distribution.html",
        {"formulaire": formulaire, "annulation": True},
    )
```

- [ ] **Étape 5 : Écrire les routes**

`apps/campagnes/urls.py` :

```python
from django.urls import path

from apps.campagnes import views

app_name = "campagnes"

urlpatterns = [
    path("", views.campagnes, name="liste"),
    path("distributions/", views.distributions, name="distributions"),
    path("distributions/nouvelle/", views.enregistrer, name="enregistrer"),
    path(
        "distributions/<int:identifiant>/annuler/",
        views.annuler,
        name="annuler",
    ),
]
```

Dans `config/urls.py`, ajouter avant la ligne des bénéficiaires :

```python
    path("campagnes/", include("apps.campagnes.urls")),
```

- [ ] **Étape 6 : Écrire les gabarits**

`templates/campagnes/campagnes.html` :

```html
{% extends "base.html" %}
{% block titre %}Campagnes{% endblock %}
{% block contenu %}
  <h1>Campagnes</h1>
  <table>
    <thead>
      <tr><th>Code</th><th>Libellé</th><th>Année</th><th>État</th><th>Projet</th></tr>
    </thead>
    <tbody>
      {% for campagne in campagnes %}
        <tr>
          <td>{{ campagne.code }}</td>
          <td>{{ campagne.libelle }}</td>
          <td>{{ campagne.annee }}</td>
          <td>{{ campagne.get_etat_display }}</td>
          <td>{{ campagne.projet.titre }}</td>
        </tr>
      {% empty %}
        <tr><td colspan="5">Aucune campagne enregistrée.</td></tr>
      {% endfor %}
    </tbody>
  </table>
{% endblock %}
```

`templates/campagnes/distributions.html` :

```html
{% extends "base.html" %}
{% block titre %}Distributions{% endblock %}
{% block contenu %}
  <h1>Distributions</h1>

  {% if peut_enregistrer %}
    <a href="{% url 'campagnes:enregistrer' %}">Enregistrer une distribution</a>
  {% endif %}

  <table>
    <thead>
      <tr>
        <th>Bénéficiaire</th><th>Campagne</th><th>Date</th>
        <th>Village</th><th>Quantité</th><th>Saisie par</th><th></th>
      </tr>
    </thead>
    <tbody>
      {% for distribution in distributions %}
        <tr>
          <td>{{ distribution.beneficiaire }}</td>
          <td>{{ distribution.campagne }}</td>
          <td>{{ distribution.date_distribution }}</td>
          <td>{{ distribution.village }}</td>
          <td>{{ distribution.quantite }} {{ distribution.unite }}</td>
          <td>{{ distribution.saisie_par }}</td>
          <td>
            {% if peut_enregistrer %}
              <a href="{% url 'campagnes:annuler' distribution.pk %}">Annuler</a>
            {% endif %}
          </td>
        </tr>
      {% empty %}
        <tr><td colspan="7">Aucune distribution enregistrée.</td></tr>
      {% endfor %}
    </tbody>
  </table>
{% endblock %}
```

`templates/campagnes/formulaire_distribution.html` :

```html
{% extends "base.html" %}
{% block titre %}
  {% if annulation %}Annuler une distribution{% else %}Nouvelle distribution{% endif %}
{% endblock %}
{% block contenu %}
  <h1>
    {% if annulation %}
      Annuler une distribution
    {% else %}
      Enregistrer une distribution
    {% endif %}
  </h1>

  <form method="post">
    {% csrf_token %}
    {{ formulaire.as_p }}
    <button type="submit">
      {% if annulation %}Confirmer l'annulation{% else %}Enregistrer{% endif %}
    </button>
  </form>

  <a href="{% url 'campagnes:distributions' %}">Retour aux distributions</a>
{% endblock %}
```

Dans `templates/base.html`, ajouter les liens de navigation dans l'en-tête :

```html
    <nav>
      <a href="{% url 'beneficiaires:liste' %}">Bénéficiaires</a>
      <a href="{% url 'campagnes:liste' %}">Campagnes</a>
      <a href="{% url 'campagnes:distributions' %}">Distributions</a>
    </nav>
```

- [ ] **Étape 7 : Lancer la suite complète**

```powershell
pytest -v
python manage.py check
```

Attendu : SUCCÈS, **253 tests passés** (244 + 9), `check` silencieux.

- [ ] **Étape 8 : Vérifier le parcours manuellement**

```powershell
python manage.py runserver
```

Se connecter avec le compte de démonstration `coordo` / `demo12345`. Créer un
type d'action, un projet et une campagne dans l'administration, puis enregistrer
une distribution depuis l'interface.

Vérifier de visu les trois comportements qui comptent :

1. Une seconde distribution pour le même bénéficiaire et la même campagne
   affiche le message « a déjà reçu une aide » et non une erreur serveur.
2. Après annulation motivée, une nouvelle distribution devient possible.
3. La fiche du bénéficiaire montre l'aide dans la section « Aides reçues », et
   l'aide annulée n'y figure plus.

---

## Critères d'achèvement du plan 2

- [ ] `pytest -v` passe intégralement, sans échec ni test ignoré
- [ ] `python manage.py check` ne signale rien
- [ ] `python manage.py makemigrations --check --dry-run` : aucune migration en attente
- [ ] L'index unique partiel `distribution_unique_par_campagne` existe en base
- [ ] Un volontaire enregistre une distribution et ne voit que ses propres saisies
- [ ] Un coordinateur voit toutes les distributions
- [ ] Un doublon produit un message en français, jamais une erreur d'intégrité
- [ ] Une distribution annulée conserve sa trace et libère la place
- [ ] La fiche d'un bénéficiaire liste les aides qu'il a reçues
- [ ] `apps/beneficiaires/services.py` ne contient plus de copie des primitives
      remontées dans `core/`

---

## Ce que ce plan ne couvre pas

| Élément | Plan |
|---|---|
| Campagnes Ramadan (composition des colis, produits) | 3 |
| Campagnes Kurban (zébus, poids, partenaire) | 3 |
| Dons, donateurs, partenaires, volontaires | 4 |
| Bourses et forages | 4 (périmètre de repli) |
| Tableau de bord, statistiques, exports | 5 |
| Assistant IA | 6 |
| Analyse des besoins | 7 |
| Site public et charte graphique | 8 |

Les gabarits de la tâche 8 restent dépouillés : la mise en forme appartient au
dernier plan.

---

## Deux points restés ouverts au lot 1

Ils n'empêchent pas ce plan de démarrer, mais doivent être tranchés avant le
lot consacré à l'assistant IA.

1. **L'écriture des données sensibles n'est contrôlée nulle part.** Un
   coordinateur saisit le numéro CIN alors que la matrice ne lui accorde que la
   lecture sur cette ligne. Décision à prendre avec l'ONG : lui accorder
   l'écriture, ou lui retirer la saisie du CIN.
2. **Un numéro CIN porté par une fiche archivée reste bloqué indéfiniment.** La
   même question se pose désormais pour le couple bénéficiaire-campagne, et ce
   plan y a répondu par la décision D5 — la contrainte ne porte que sur les
   lignes actives. Il serait cohérent d'appliquer la même règle au CIN.
