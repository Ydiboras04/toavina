# Conception — Système intelligent de gestion de l'ONG E.F.F.M

**Projet** : NGO Management System — ONG E.F.F.M
**Cadre** : Projet de fin d'études, Master 2 MIAGE — soutenance devant jury
**Document** : conception détaillée (Merise + architecture technique)
**Date** : 4 septembre 2026
**Source** : `Cahier_de_charges_amélioré_SI20210040.docx`
**Statut** : conception validée — implémentation non commencée

---

## 1. Objet du document

Ce document traduit le cahier des charges de l'ONG E.F.F.M en une conception
implémentable : architecture applicative, modèle de données au formalisme Merise,
matrice des rôles et permissions, architecture des modules d'intelligence
artificielle, et découpage du développement.

Il ne contient aucun code. Il précède l'implémentation et sert de référence
commune entre l'étudiant, l'encadrant et l'ONG.

Les références de la forme « §7.3 » renvoient au cahier des charges.

---

## 2. Contraintes retenues

| Contrainte | Valeur | Conséquence sur la conception |
|---|---|---|
| Cadre | PFE M2 avec soutenance | Formalisme documenté, démonstration garantie à date |
| Budget temps | 40 à 60 jours, temps plein | Périmètre de repli identifié à l'avance (§10) |
| Formalisme | Merise (MCD / MLD / MPD) | Modèle conceptuel avant modèles Django |
| Service d'IA | Aucune clé API disponible | Abstraction fournisseur obligatoire (§9.3) |
| Technologie | Python / Django | Imposée par le cahier des charges |
| Base de données | SQLite en développement, PostgreSQL en production | Aucune dépendance à une extension propriétaire |

---

## 3. Principe directeur de l'architecture

Le cahier des charges pose au §13 une exigence dont découle toute l'architecture :

> « Les fonctionnalités IA devront respecter les mêmes règles d'accès que
> l'application. »

Cette phrase interdit une organisation où les règles métier vivraient dans les
vues Django. L'assistant IA n'appelle pas les vues ; il contournerait donc
mécaniquement toute règle qui y serait écrite. On obtiendrait deux jeux de règles
divergents, et l'exigence du §12 — « l'IA ne doit pas révéler de données
auxquelles l'utilisateur n'a pas accès » — deviendrait invérifiable.

La conception place donc **toutes les règles métier dans une couche de services
unique**, appelée aussi bien par les vues que par les outils de l'IA. Une règle
écrite une fois s'applique aux deux par construction.

---

## 4. Architecture en couches

| Couche | Contenu | Règle imposée |
|---|---|---|
| Présentation | vues, formulaires, templates | ne contient aucune règle métier |
| Services métier | `services.py` de chaque application | point d'entrée unique de toute écriture |
| Données | modèles, gestionnaires, abstraits de `core` | contraintes d'intégrité au niveau du SGBD |
| Orchestration IA | prompts, outils, permissions, journalisation | appelle les mêmes services que les vues |

**Règle transversale** : toute fonction de la couche services reçoit
l'utilisateur courant comme premier paramètre obligatoire et retourne des
données déjà filtrées selon ses droits. Cette signature uniforme est ce qui rend
le cloisonnement de l'IA structurel plutôt que déclaratif.

---

## 5. Organisation du projet

```
ong_effm/
├── config/
│   ├── settings/
│   │   ├── base.py          configuration commune
│   │   ├── dev.py           SQLite, débogage, fournisseur IA factice
│   │   └── prod.py          PostgreSQL, secrets externalisés
│   ├── urls.py
│   └── wsgi.py / asgi.py
├── core/                    noyau transversal
│   ├── models.py            abstraits : Horodate, Campagne, Distribution
│   ├── permissions.py       mixins et contrôle par rôle
│   ├── services.py          primitives partagées
│   └── audit.py             piste d'audit
├── apps/
│   ├── public/              site public (§3.1)
│   ├── accounts/            utilisateurs, rôles, authentification
│   ├── dashboard/           tableau de bord et notifications (§6)
│   ├── beneficiaires/       fiches et prévention des doublons (§4.1)
│   ├── projets/             projets et actions (§3.2)
│   ├── dons/                dons et donateurs (§4.2)
│   ├── ramadan/             campagnes et distributions Ramadan (§4.3)
│   ├── kurban/              campagnes et distributions Kurban (§4.4)
│   ├── bourses/             bourses d'étude (§4.5)
│   ├── forages/             forages (§4.6)
│   ├── volontaires/
│   ├── partenaires/
│   ├── galerie/             photos et vidéos (§4.7)
│   ├── documents/           documents et pièces jointes (§4.7)
│   ├── actualites/
│   ├── contact/
│   ├── statistiques/        rapports PDF et exports Excel (§9)
│   ├── assistant_ia/        chatbot et création assistée (§7)
│   └── analyse_besoins/     analyse intelligente des besoins (§8)
├── templates/
├── static/  media/
└── docs/
```

### 5.1 Écart assumé par rapport au §11.1

Le §11.1 énumère dix-huit applications, mais aucune ne peut accueillir les pages
*Accueil*, *Qui sommes-nous*, *Nos actions* et *Faire un don* exigées au §3.1.
Une application `public` est donc ajoutée.

Il s'agit de combler une omission du cahier des charges, non d'étendre le
périmètre : toutes les pages concernées y figurent déjà.

### 5.2 Justification du noyau `core`

Les modules Ramadan, Kurban, Bourses et Forages suivent un patron identique :
une campagne (budget, dates, responsable, état) produisant des distributions
vers des bénéficiaires. Écrire ce patron quatre fois multiplierait par quatre le
code, les tests et les occasions d'erreur — en particulier sur la règle
anti-doublon, qui est un critère de réception (§17).

Le noyau `core` porte les classes abstraites communes ; chaque module métier
n'écrit que ce qui lui est propre.

---

## 6. Modèle conceptuel de données (MCD)

### 6.1 Décisions de modélisation structurantes

**D1 — La géographie est normalisée en entités, non en champs texte.**

Le §4.1 place *village, commune, district, région* comme quatre champs de la
fiche bénéficiaire. En texte libre, « Morondava » connaîtrait autant
d'orthographes que d'opérateurs de saisie. Or le §8.1 exige d'« identifier les
zones ou villages ayant une couverture d'aide plus faible » : cette agrégation
est impossible de façon fiable sur du texte libre.

La hiérarchie devient une chaîne d'entités reliées, et l'analyse des besoins
remonte les niveaux par jointure. Sans cette décision, le module du §8 ne peut
pas produire de résultats corrects.

**D2 — Une entité DISTRIBUTION centrale, et non une par campagne.**

Le §4.1 demande de vérifier si une personne a déjà reçu un colis Ramadan, de la
viande Kurban, des vêtements, un forage ou une bourse. Cinq vérifications
réparties sur cinq tables offriraient cinq occasions de laisser passer un
doublon.

Une entité DISTRIBUTION unique reliant BENEFICIAIRE et CAMPAGNE porte une
contrainte d'unicité sur le couple. Le doublon devient impossible au niveau du
SGBD et non seulement au niveau applicatif : le critère de réception du §17 est
alors structurellement satisfait.

**D3 — CAMPAGNE générique, spécialisée par type d'aide.**

CAMPAGNE porte le tronc commun. CAMPAGNE_RAMADAN ajoute la composition des
colis, CAMPAGNE_KURBAN le nombre de zébus et le poids. C'est la traduction
conceptuelle du noyau `core` décrit en 5.2.

**D4 — L'IA n'écrit jamais directement en base.**

Le cahier des charges pose comme principe important que l'IA propose et que
l'humain valide. Si l'assistant appelait les services d'écriture, ce principe
reposerait sur la seule discipline du développeur.

L'entité PROPOSITION_IA le matérialise : elle porte le contenu proposé, son
état, son demandeur et son validateur. Aucune donnée métier n'existe tant qu'un
utilisateur habilité n'a pas transformé la proposition en enregistrement réel.
Le §7.3 et le §12 sont satisfaits par construction, et la traçabilité exigée au
§12 découle du même objet.

### 6.2 Vue d'ensemble

```
RÉFÉRENTIEL   PAYS ─< REGION ─< DISTRICT ─< COMMUNE ─< VILLAGE
              TYPE_ACTION      CATEGORIE_BESOIN      PRODUIT

PERSONNES     UTILISATEUR   BENEFICIAIRE   DONATEUR
              VOLONTAIRE    PARTENAIRE

OPÉRATIONNEL  PROJET ─< CAMPAGNE ─< DISTRIBUTION >─ BENEFICIAIRE
              PROJET ─< DON >─ DONATEUR
              PROJET ─< FORAGE           PROJET ─< BOURSE

CONTENU       ACTUALITE   MEDIA   DOCUMENT   MESSAGE_CONTACT

IA            CONVERSATION_IA ─< MESSAGE_IA ─< PROPOSITION_IA
              JOURNAL_IA
              BESOIN >─ CATEGORIE_BESOIN
              ANALYSE_BESOIN ─< INDICATEUR_BESOIN
              ANALYSE_BESOIN ─< RECOMMANDATION
```

### 6.3 Entités du référentiel

| Entité | Attributs |
|---|---|
| PAYS | `id_pays`, code_iso, libelle |
| REGION | `id_region`, libelle |
| DISTRICT | `id_district`, libelle |
| COMMUNE | `id_commune`, libelle |
| VILLAGE | `id_village`, libelle, latitude, longitude |
| TYPE_ACTION | `id_type_action`, libelle, description |
| CATEGORIE_BESOIN | `id_categorie`, libelle, description |
| PRODUIT | `id_produit`, libelle, unite, categorie |

TYPE_ACTION est alimentée par les douze types du §3.2 : distribution
alimentaire, distribution de vêtements, kurban, forage d'eau, construction de
mosquées, construction d'écoles, bourses d'étude, parrainage d'orphelins,
urgences humanitaires, santé, éducation, développement rural.

CATEGORIE_BESOIN reprend les catégories du §8.1 : alimentation, eau, éducation,
santé, logement, urgence.

PRODUIT couvre à la fois les composants de colis du §4.3 (riz, huile, sucre,
farine, lait, pâtes, savon, dattes) et la « création de produits ou matériels »
demandée au §7.2.

**Associations**

| Association | Entités | Cardinalités |
|---|---|---|
| APPARTIENT | REGION → PAYS | (1,1) — (0,n) |
| APPARTIENT | DISTRICT → REGION | (1,1) — (0,n) |
| APPARTIENT | COMMUNE → DISTRICT | (1,1) — (0,n) |
| APPARTIENT | VILLAGE → COMMUNE | (1,1) — (0,n) |

### 6.4 Entités « personnes »

**UTILISATEUR** — `id_utilisateur`, identifiant, mot_de_passe, nom, prenom,
email, telephone, role, actif, creation_ia_autorisee, date_creation,
derniere_connexion

`role` prend ses valeurs dans : super_admin, president, coordinateur,
comptable, responsable_projet, volontaire, visiteur (§5).

`creation_ia_autorisee` matérialise l'exigence du §12 : « possibilité de
désactiver certaines actions IA pour certains rôles ».

**BENEFICIAIRE** — `id_beneficiaire`, nom, prenom, sexe, date_naissance,
telephone, adresse, profession, nombre_enfants, situation_familiale, revenu,
photo, numero_cin, numero_passeport, statut, date_enregistrement

Tous les champs du §4.1 sont repris, à l'exception de la localisation qui passe
par l'association avec VILLAGE (décision D1).

**DONATEUR** — `id_donateur`, nom, type_donateur, email, telephone, adresse, pays

**PARTENAIRE** — `id_partenaire`, nom, type_partenaire, pays, contact, email,
telephone, logo, date_convention

**VOLONTAIRE** — `id_volontaire`, nom, prenom, telephone, email, competences,
disponibilite, date_adhesion, actif

**Associations**

| Association | Entités | Cardinalités |
|---|---|---|
| RESIDE | BENEFICIAIRE → VILLAGE | (1,1) — (0,n) |
| RESIDE | VOLONTAIRE → VILLAGE | (0,1) — (0,n) |
| EST_LIE | VOLONTAIRE → UTILISATEUR | (0,1) — (0,1) |

### 6.5 Entités opérationnelles

**PROJET** — `id_projet`, code, titre, description, budget_prevu,
budget_consomme, date_debut, date_fin, etat

La localisation du projet passe par une association avec REGION, conformément à
la décision D1 — elle n'est pas portée par des champs texte.

**CAMPAGNE** — `id_campagne`, code, libelle, annee, budget, date_debut,
date_fin, etat

**CAMPAGNE_RAMADAN** — spécialise CAMPAGNE : nombre_colis_prevus

**CAMPAGNE_KURBAN** — spécialise CAMPAGNE : nombre_zebus, poids_total_kg

**COMPOSITION_COLIS** — association porteuse entre CAMPAGNE_RAMADAN et
PRODUIT : quantite, unite

**DISTRIBUTION** — `id_distribution`, date_distribution, quantite, unite,
observation, statut

**DON** — `id_don`, reference, montant, devise, date_don, mode_paiement

**FORAGE** — `id_forage`, nom, latitude, longitude, budget, date_debut,
date_fin, entreprise, etat

**BOURSE** — `id_bourse`, universite, pays_etudes, formation, niveau,
date_debut, date_fin, numero_passeport, numero_visa, etat

**Associations**

| Association | Entités | Cardinalités |
|---|---|---|
| RELEVE_DE | PROJET → TYPE_ACTION | (1,1) — (0,n) |
| PILOTE | PROJET → UTILISATEUR (responsable) | (1,1) — (0,n) |
| SITUE | PROJET → REGION | (0,1) — (0,n) |
| SOUTIENT | PARTENAIRE ↔ PROJET | (0,n) — (0,n) |
| RATTACHE | CAMPAGNE → PROJET | (1,1) — (0,n) |
| ANIME | CAMPAGNE → UTILISATEUR (responsable) | (1,1) — (0,n) |
| COMPOSE | CAMPAGNE_RAMADAN ↔ PRODUIT | (0,n) — (0,n) |
| CONFIE_A | CAMPAGNE_KURBAN → PARTENAIRE | (0,1) — (0,n) |
| CONCERNE | DISTRIBUTION → BENEFICIAIRE | (1,1) — (0,n) |
| RELEVE_DE | DISTRIBUTION → CAMPAGNE | (1,1) — (0,n) |
| LIEU | DISTRIBUTION → VILLAGE | (1,1) — (0,n) |
| SAISIE_PAR | DISTRIBUTION → UTILISATEUR | (1,1) — (0,n) |
| EFFECTUE | DON → DONATEUR | (1,1) — (0,n) |
| FINANCE | DON → PROJET | (0,1) — (0,n) |
| IMPLANTE | FORAGE → VILLAGE | (1,1) — (0,n) |
| BENEFICIE | BOURSE → BENEFICIAIRE | (1,1) — (0,n) |

> **Contrainte d'intégrité majeure** — unicité du couple
> (`id_beneficiaire`, `id_campagne`) dans DISTRIBUTION. C'est la traduction
> technique de la prévention des doublons exigée aux §4.1, §4.3, §13 et §17.

**Note sur l'association LIEU.** DISTRIBUTION est reliée à VILLAGE alors que
BENEFICIAIRE l'est déjà. Il ne s'agit pas d'une duplication au sens du §13 : le
§4.3 impose d'enregistrer le village de distribution, qui peut différer du
village de résidence — une distribution se tient fréquemment sur un point de
collecte desservant plusieurs villages. Conserver les deux permet de distinguer
« aide reçue par les habitants d'un village » de « aide distribuée dans un
village », distinction dont le module d'analyse des besoins (§8.1) a besoin pour
mesurer correctement la couverture d'une zone.

### 6.6 Entités de contenu

| Entité | Attributs |
|---|---|
| ACTUALITE | `id_actualite`, titre, slug, resume, contenu, image, date_publication, publiee |
| MEDIA | `id_media`, type_media, fichier, legende, categorie, date_prise |
| DOCUMENT | `id_document`, titre, type_document, fichier, confidentiel, date_document |
| MESSAGE_CONTACT | `id_message`, nom, email, telephone, sujet, message, date_envoi, traite |

`categorie` de MEDIA reprend les catégories du §4.7 : Ramadan, Kurban, Forages,
Construction, Bourses, Urgence.

`type_document` reprend celles du §4.7 : contrat, rapport, budget, convention,
lettre.

L'attribut `confidentiel` de DOCUMENT sert le §12 (« protection des documents et
données sensibles ») : il conditionne à la fois l'accès applicatif et
l'indexation par la recherche documentaire de l'assistant.

**Associations**

| Association | Entités | Cardinalités |
|---|---|---|
| REDIGE | ACTUALITE → UTILISATEUR | (1,1) — (0,n) |
| ILLUSTRE | MEDIA → PROJET | (0,1) — (0,n) |
| JOINT_A | DOCUMENT → PROJET | (0,1) — (0,n) |

Le §4.7 impose que chaque photo puisse être associée à un projet : d'où la
cardinalité (0,1) côté MEDIA.

### 6.7 Entités du domaine IA

**CONVERSATION_IA** — `id_conversation`, titre, date_creation, archivee

**MESSAGE_IA** — `id_message_ia`, emetteur (utilisateur | assistant), contenu,
outils_appeles, date_envoi

**PROPOSITION_IA** — `id_proposition`, type_objet, contenu_propose, etat,
motif_decision, date_creation, date_decision

`etat` prend ses valeurs dans : en_attente, validee, rejetee.
`contenu_propose` conserve les valeurs soumises sous forme structurée.

**JOURNAL_IA** — `id_journal`, action, objet_cible, donnees, date_action,
adresse_ip

**BESOIN** — `id_besoin`, description, date_signalement, urgence, statut

**ANALYSE_BESOIN** — `id_analyse`, periode_debut, periode_fin, date_generation,
parametres

**INDICATEUR_BESOIN** — `id_indicateur`, libelle, valeur, unite, methode_calcul

**RECOMMANDATION** — `id_recommandation`, titre, texte, priorite, sources, etat

L'attribut `sources` de RECOMMANDATION conserve les références des
enregistrements ayant fondé la recommandation. Il répond directement à
l'exigence du §8.2 : « recommandations opérationnelles explicables, avec
indication des données ayant servi à leur production ».

**Associations**

| Association | Entités | Cardinalités |
|---|---|---|
| MENE | CONVERSATION_IA → UTILISATEUR | (1,1) — (0,n) |
| CONTIENT | MESSAGE_IA → CONVERSATION_IA | (1,1) — (1,n) |
| ISSUE_DE | PROPOSITION_IA → MESSAGE_IA | (0,1) — (0,n) |
| DEMANDE_PAR | PROPOSITION_IA → UTILISATEUR | (1,1) — (0,n) |
| DECIDE_PAR | PROPOSITION_IA → UTILISATEUR | (0,1) — (0,n) |
| TRACE | JOURNAL_IA → UTILISATEUR | (1,1) — (0,n) |
| CLASSE | BESOIN → CATEGORIE_BESOIN | (1,1) — (0,n) |
| LOCALISE | BESOIN → VILLAGE | (1,1) — (0,n) |
| EXPRIME_PAR | BESOIN → BENEFICIAIRE | (0,1) — (0,n) |
| SIGNALE_PAR | BESOIN → UTILISATEUR | (1,1) — (0,n) |
| GENEREE_PAR | ANALYSE_BESOIN → UTILISATEUR | (1,1) — (0,n) |
| PRODUIT | INDICATEUR_BESOIN → ANALYSE_BESOIN | (1,1) — (1,n) |
| PORTE_SUR | INDICATEUR_BESOIN → CATEGORIE_BESOIN | (0,1) — (0,n) |
| PORTE_SUR | INDICATEUR_BESOIN → VILLAGE | (0,1) — (0,n) |
| PRODUIT | RECOMMANDATION → ANALYSE_BESOIN | (1,1) — (0,n) |

La cardinalité (0,1) de DECIDE_PAR traduit qu'une proposition en attente n'a pas
encore de validateur.

---

## 7. Modèle logique de données (MLD)

Traduction relationnelle du MCD. Les clés primaires sont soulignées par la
notation `#`, les clés étrangères préfixées par `→`.

```
PAYS(#id_pays, code_iso, libelle)
REGION(#id_region, libelle, →id_pays)
DISTRICT(#id_district, libelle, →id_region)
COMMUNE(#id_commune, libelle, →id_district)
VILLAGE(#id_village, libelle, latitude, longitude, →id_commune)
TYPE_ACTION(#id_type_action, libelle, description)
CATEGORIE_BESOIN(#id_categorie, libelle, description)
PRODUIT(#id_produit, libelle, unite, categorie)

UTILISATEUR(#id_utilisateur, identifiant, mot_de_passe, nom, prenom, email,
            telephone, role, actif, creation_ia_autorisee, date_creation,
            derniere_connexion)
BENEFICIAIRE(#id_beneficiaire, nom, prenom, sexe, date_naissance, telephone,
             adresse, profession, nombre_enfants, situation_familiale, revenu,
             photo, numero_cin, numero_passeport, statut, date_enregistrement,
             →id_village)
DONATEUR(#id_donateur, nom, type_donateur, email, telephone, adresse, pays)
PARTENAIRE(#id_partenaire, nom, type_partenaire, pays, contact, email,
           telephone, logo, date_convention)
VOLONTAIRE(#id_volontaire, nom, prenom, telephone, email, competences,
           disponibilite, date_adhesion, actif, →id_village, →id_utilisateur)

PROJET(#id_projet, code, titre, description, budget_prevu, budget_consomme,
       date_debut, date_fin, etat, →id_type_action, →id_responsable,
       →id_region)
PROJET_PARTENAIRE(#id_projet, #id_partenaire, role_partenaire, montant)
CAMPAGNE(#id_campagne, code, libelle, annee, budget, date_debut, date_fin,
         etat, type_campagne, →id_projet, →id_responsable)
CAMPAGNE_RAMADAN(#id_campagne, nombre_colis_prevus)
CAMPAGNE_KURBAN(#id_campagne, nombre_zebus, poids_total_kg, →id_partenaire)
COMPOSITION_COLIS(#id_campagne, #id_produit, quantite, unite)
DISTRIBUTION(#id_distribution, date_distribution, quantite, unite, observation,
             statut, →id_beneficiaire, →id_campagne, →id_village,
             →id_saisie_par)
   CONTRAINTE UNIQUE (id_beneficiaire, id_campagne)
DON(#id_don, reference, montant, devise, date_don, mode_paiement,
    →id_donateur, →id_projet)
FORAGE(#id_forage, nom, latitude, longitude, budget, date_debut, date_fin,
       entreprise, etat, →id_village, →id_projet)
BOURSE(#id_bourse, universite, pays_etudes, formation, niveau, date_debut,
       date_fin, numero_passeport, numero_visa, etat, →id_beneficiaire,
       →id_projet)

ACTUALITE(#id_actualite, titre, slug, resume, contenu, image,
          date_publication, publiee, →id_auteur)
MEDIA(#id_media, type_media, fichier, legende, categorie, date_prise,
      →id_projet)
DOCUMENT(#id_document, titre, type_document, fichier, confidentiel,
         date_document, →id_projet)
MESSAGE_CONTACT(#id_message, nom, email, telephone, sujet, message,
                date_envoi, traite)

CONVERSATION_IA(#id_conversation, titre, date_creation, archivee,
                →id_utilisateur)
MESSAGE_IA(#id_message_ia, emetteur, contenu, outils_appeles, date_envoi,
           →id_conversation)
PROPOSITION_IA(#id_proposition, type_objet, contenu_propose, etat,
               motif_decision, date_creation, date_decision,
               →id_demandeur, →id_validateur, →id_message_ia)
JOURNAL_IA(#id_journal, action, objet_cible, donnees, date_action,
           adresse_ip, →id_utilisateur)
BESOIN(#id_besoin, description, date_signalement, urgence, statut,
       →id_categorie, →id_village, →id_beneficiaire, →id_signale_par)
ANALYSE_BESOIN(#id_analyse, periode_debut, periode_fin, date_generation,
               parametres, →id_utilisateur)
INDICATEUR_BESOIN(#id_indicateur, libelle, valeur, unite, methode_calcul,
                  →id_analyse, →id_categorie, →id_village)
RECOMMANDATION(#id_recommandation, titre, texte, priorite, sources, etat,
               →id_analyse)
```

### 7.1 Note sur la spécialisation CAMPAGNE

La relation d'héritage du MCD est traduite par la solution « table par
sous-type » : CAMPAGNE porte le tronc commun, CAMPAGNE_RAMADAN et
CAMPAGNE_KURBAN portent les attributs spécifiques et partagent la clé primaire
de la table mère.

Cette traduction est retenue plutôt que la table unique parce que les attributs
spécifiques sont obligatoires dans leur sous-type — le nombre de zébus n'a aucun
sens pour une campagne Ramadan. Une table unique produirait des colonnes
systématiquement nulles et rendrait impossible toute contrainte de non-nullité.

C'est également la traduction directe de l'héritage abstrait de `core`.

### 7.2 Note sur l'association PROJET_PARTENAIRE

L'association de cardinalité (0,n) — (0,n) entre PROJET et PARTENAIRE devient
une table de jonction, porteuse du rôle du partenaire et de son éventuelle
contribution financière.

---

## 8. Modèle physique de données (MPD)

| Sujet | Décision |
|---|---|
| SGBD de développement | SQLite, sans extension particulière |
| SGBD de production | PostgreSQL |
| Portabilité | aucune fonctionnalité propre à PostgreSQL dans le modèle, afin que la migration reste une opération de transfert |
| Clés primaires | entiers auto-incrémentés |
| Index | sur toutes les clés étrangères, sur `numero_cin`, et sur (`id_beneficiaire`, `id_campagne`) |
| Contrainte d'unicité | (`id_beneficiaire`, `id_campagne`) sur DISTRIBUTION |
| Unicité partielle | `numero_cin` unique lorsqu'il est renseigné |
| Suppressions | interdites sur les données historisées ; un indicateur d'archivage remplace la suppression |
| Fichiers | stockés hors base, organisés par module et par projet (§11) |
| Horodatage | `date_creation` et `date_modification` sur toutes les tables métier, hérités de l'abstrait `Horodate` |

### 8.1 Note sur l'identification des bénéficiaires

Le §4.1 demande une « attention particulière à la prévention des doublons » de
personnes, distincte de la prévention des doublons de distributions.

Le numéro de CIN constitue l'identifiant naturel, mais il ne peut pas être rendu
strictement obligatoire : une partie des bénéficiaires n'en dispose pas. La
conception retient donc :

1. une unicité sur `numero_cin` lorsqu'il est renseigné ;
2. à l'enregistrement, une recherche de similarité sur le triplet (nom, prénom,
   date de naissance) restreinte au même village, présentée à l'opérateur sous
   forme d'avertissement ;
3. la décision finale reste humaine — un homonyme réel dans un même village est
   possible et ne doit pas être bloqué.

Ce point est signalé comme une règle de gestion à confirmer avec l'ONG (§13).

---

## 9. Rôles, permissions et sécurité

### 9.1 Matrice des droits

Le §5 nomme sept rôles mais reste volontairement imprécis sur leurs droits, et
le §13 impose que les fonctionnalités non définies soient validées avant
implémentation. **La matrice ci-dessous est une proposition de conception à
faire valider par l'ONG.**

| Module | S.Admin | Président | Coord. | Comptable | Resp. projet | Volontaire | Visiteur |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| Bénéficiaires (fiche) | ● | ○ | ● | — | ○ | ○ | — |
| Données sensibles (CIN, passeport) | ● | ○ | ○ | — | — | — | — |
| Projets et campagnes | ● | ○ | ● | ○ | ◐ | — | — |
| Distributions | ● | ○ | ● | — | ◐ | ◐ | — |
| Dons et finances | ● | ○ | ○ | ● | ○ | — | — |
| Documents | ● | ○ | ● | ◐ | ◐ | — | — |
| Statistiques et rapports | ● | ○ | ○ | ○ | ◐ | — | — |
| Utilisateurs | ● | ○ | — | — | — | — | — |
| Assistant IA | ● | ● | ● | ● | ● | ◐ | — |
| Analyse des besoins | ● | ● | ● | ○ | ○ | — | — |
| Validation des propositions IA | ● | ● | ● | ◐ | ◐ | — | — |

`●` accès complet · `◐` limité à ses propres objets ou à son périmètre ·
`○` lecture seule · `—` aucun accès

### 9.2 Trois niveaux de contrôle

Les permissions natives de Django répondent à la question « cet utilisateur
peut-il accéder au module Projets ? », mais non à « ce responsable peut-il
modifier *ce* projet précis ? ». Or le §5 précise que le responsable projet gère
« les projets qui lui sont attribués ».

Trois niveaux se superposent donc :

| Niveau | Question traitée | Moyen |
|---|---|---|
| Fonctionnel | quels modules ? | groupes et permissions Django |
| Objet | quels enregistrements ? | requêtes filtrées dans la couche services |
| Champ | quels attributs ? | masquage des données sensibles du §12 |

### 9.3 Le mécanisme qui protège l'IA

Chaque fonction de la couche services reçoit l'utilisateur comme premier
paramètre et retourne des données déjà filtrées. Les outils de l'assistant
appellent ces mêmes fonctions avec l'utilisateur courant.

L'assistant ne dispose d'aucun accès direct à la base. Il ne peut donc pas voir
plus que son utilisateur, non par convention mais parce qu'aucune source de
données non filtrée ne lui est accessible. L'exigence du §12 cesse d'être une
promesse et devient une propriété vérifiable du code.

### 9.4 Validation des propositions

Règle retenue : **peut valider une proposition l'utilisateur qui a le droit de
créer l'objet proposé.** Un comptable valide une proposition de don, non une
fiche bénéficiaire.

Cette règle évite d'introduire une famille de permissions supplémentaire à
maintenir en cohérence avec la première.

### 9.5 Autres mesures de sécurité (§12)

- Les clés et secrets sont lus depuis l'environnement, jamais dans le dépôt.
- Les données transmises au service de langage sont limitées au strict
  nécessaire : les outils retournent des agrégats et des champs explicitement
  autorisés, jamais des fiches complètes.
- Les documents marqués confidentiels sont exclus de l'indexation documentaire.
- L'indicateur `creation_ia_autorisee` permet de désactiver la création assistée
  par rôle tout en conservant la consultation.
- Toute action IA validée est journalisée avant d'être appliquée.

---

## 10. Architecture des modules d'intelligence artificielle

### 10.1 Pipeline de l'assistant

Traduction directe des huit étapes du §7.3 :

```
Question en langage naturel
   ▼
Identification de l'utilisateur
   ▼
Chargement de ses permissions
   ▼
Extraction de l'intention et des paramètres
   ▼
Exécution d'un outil (services filtrés par l'utilisateur)
   ▼
Réponse rédigée   OU   Proposition créée
   ▼
Validation humaine (si proposition)
   ▼
Journalisation
```

### 10.2 Catalogue d'outils

L'assistant ne formule aucune requête sur les données. Il choisit un outil dans
un catalogue déclaré et fournit ses paramètres ; l'outil est une fonction de la
couche services, donc filtrée par l'utilisateur.

| Famille | Outils | Exigence servie |
|---|---|---|
| Consultation | lister_projets, etat_projet, budget_restant | §7.1 |
| Bénéficiaires | rechercher_beneficiaire, historique_aides | §7.1 |
| Distributions | compter_distributions, distributions_par_village | §7.1 |
| Finances | total_dons_periode, dons_par_projet | §7.1 |
| Documents | rechercher_document | §7.1 |
| Rapports | synthese_periode, comparer_periodes | §7.1, §9 |
| Création assistée | proposer_projet, proposer_produit, proposer_utilisateur, proposer_campagne | §7.2 |

La surface d'accès de l'IA est donc exactement cette liste — un périmètre fini,
lisible et démontrable, ce qui rend le §12 auditable.

Les outils de la famille « création assistée » ne créent jamais l'objet final :
ils produisent une PROPOSITION_IA à l'état *en attente*.

### 10.3 Abstraction du fournisseur de modèle

Aucune clé API n'est disponible au moment de la conception, et le §11 laisse le
choix ouvert (« selon la solution retenue »). Une interface unique est donc
définie, avec trois implémentations :

| Implémentation | Usage | Propriété |
|---|---|---|
| Fournisseur factice | développement et tests — **par défaut** | déterministe, sans réseau, sans coût |
| API Claude | production | qualité de réponse |
| Modèle local | repli | aucune donnée ne quitte les serveurs de l'ONG |

Le développement et les tests se déroulent intégralement sans clé. Le
branchement du service réel relève de la configuration, non du code.

Ce choix sert aussi une exigence de fond : les données de bénéficiaires sont des
données personnelles, et l'option d'un traitement entièrement local doit rester
ouverte pour l'ONG.

### 10.4 Le module d'analyse des besoins ne conclut pas par le modèle de langage

C'est la décision la plus importante de cette section.

Le §8.2 exige des « recommandations opérationnelles explicables, avec indication
des données ayant servi à leur production ». Une conclusion produite par un
modèle de langage ne satisfait pas cette exigence : elle n'est ni reproductible,
ni traçable, et serait légitimement contestée par un jury.

L'architecture sépare donc le calcul de la rédaction :

| Étape | Moyen | Propriété |
|---|---|---|
| Calcul des indicateurs (couverture par zone, fréquence des besoins, écarts entre besoins exprimés et aides distribuées) | requêtes d'agrégation | déterministe, reproductible, chiffré |
| Classement et détection des écarts | règles explicites paramétrées par l'ONG | auditable, justifiable |
| Rédaction de la synthèse | modèle de langage | confort de lecture uniquement |

Le modèle met en forme des chiffres déjà calculés ; il ne les produit pas.
Chaque recommandation conserve dans son attribut `sources` les enregistrements
qui l'ont fondée.

**Conséquence pratique** : le module d'analyse fonctionne intégralement sans
aucune clé API. Seule la qualité rédactionnelle de la synthèse s'en trouverait
améliorée.

### 10.5 Prévention des réponses inventées

Le §12 impose de « privilégier les données du système pour les questions métier
et signaler les informations indisponibles ».

Règle retenue : lorsqu'aucun outil ne retourne de donnée, la réponse imposée est
que l'information n'est pas disponible dans le système. Aucune reformulation
plausible n'est autorisée. Cette règle est testable, donc testée (§12 du présent
document).

---

## 11. Découpage du développement

Base de référence : 50 jours, milieu de la fourchette annoncée.

| # | Lot | Jours | Apport |
|:--:|---|:--:|---|
| 0 | Socle : projet, `core`, utilisateur, rôles | 4 | débloque tout le reste |
| 1 | Référentiel géographique et bénéficiaires | 6 | cible de toutes les aides |
| 2 | Projets, campagnes, distributions | 6 | **règle anti-doublon** |
| 3 | Ramadan et Kurban | 5 | **démonstration métier complète (j. 21)** |
| 4 | Dons, donateurs, partenaires, volontaires | 4 | volet financier |
| 5 | Bourses et forages | 4 | périmètre métier complet |
| 6 | Tableau de bord, statistiques, PDF et Excel | 5 | livrables du §9 |
| 7 | Assistant IA : outils, propositions, journal | 8 | **cœur du mémoire (j. 44)** |
| 8 | Analyse des besoins | 5 | second module IA |
| 9 | Site public, galerie, actualités, contact | 5 | première impression du jury |
| 10 | Documents, sécurité, tests, documentation | 4 | critères de réception du §17 |
| | **Total** | **56** | |

### 11.1 Le plan dépasse la cible, et c'est assumé

56 jours estimés contre 50 disponibles au milieu de la fourchette. Une
estimation de projet de fin d'études dérive presque toujours vers le haut. Le
dépassement est donc affiché plutôt que masqué par une compression artificielle
des chiffres.

**Périmètre de repli désigné à l'avance : le lot 5** (bourses et forages). Ces
deux modules réutilisent le patron de campagne déjà démontré au lot 3 et
n'apportent aucune idée nouvelle au mémoire. Leur retrait ramène le plan à 52
jours sans rien retirer à la démonstration.

Le §13 autorise explicitement qu'une fonctionnalité soit conçue et documentée
sans être implémentée. Les lots retirés restent donc couverts par le présent
document.

### 11.2 Risque principal et contre-mesures

L'assistant IA distingue ce mémoire et se situe au jour 44 : tout retard
accumulé en amont le comprime en premier.

Deux contre-mesures sont intégrées à la conception :

1. le fournisseur factice permet de développer et de tester l'assistant sans
   clé API, supprimant toute dépendance externe bloquante ;
2. le module d'analyse (lot 8) fonctionne sans modèle de langage.

Même dans le scénario le plus défavorable, la soutenance présente un module
d'IA opérationnel.

### 11.3 Points de contrôle

| Jour | Attendu |
|---|---|
| 21 | démonstration métier complète : bénéficiaires, campagnes, distributions sans doublon |
| 44 | assistant IA fonctionnel de bout en bout, validation humaine comprise |
| 52 | gel des fonctionnalités — place aux tests, à la sécurité et à la documentation |

---

## 12. Stratégie de tests

### 12.1 Trois règles développées en test d'abord

Ce sont les trois que le §17 érige en critères de réception :

1. **Prévention des doublons de distribution** — un bénéficiaire ne peut
   recevoir deux fois la même campagne. Vérifié au niveau de la contrainte de
   base et au niveau du service.
2. **Cloisonnement des permissions** — pour chaque rôle, ce qui est accessible
   *et* ce qui ne l'est pas, éprouvé par les vues **et** par les outils de
   l'assistant.
3. **Validation obligatoire des propositions** — aucun chemin de code ne permet
   à l'assistant d'écrire une donnée métier sans décision humaine.

### 12.2 Le reste

Tests classiques, sans développement piloté par les tests : opérations de
création, lecture, modification et suppression ; validation des formulaires ;
imports et exports ; génération des rapports. Ces parties portent un risque
faible et le budget temps ne justifie pas d'y appliquer la même rigueur.

### 12.3 Tests des modules IA

Le fournisseur factice rend les scénarios de conversation reproductibles,
gratuits et hors réseau. Les tests d'analyse partent de jeux de données connus
vers des indicateurs attendus — possible précisément parce que le calcul est
déterministe (§10.4).

Cas d'erreur explicitement couverts : demande hors périmètre de permissions,
donnée inexistante, proposition rejetée, service de langage indisponible.

---

## 13. Gestion des erreurs

| Situation | Comportement retenu |
|---|---|
| Service de langage indisponible | l'assistant s'affiche en mode dégradé ; l'application métier continue de fonctionner normalement |
| Donnée absente | réponse « information non disponible dans le système » ; aucune reformulation plausible |
| Demande hors permissions | refus explicite, sans révéler l'existence de la donnée |
| Doublon de distribution | rejet au niveau de la base, message métier explicite |
| Doublon de bénéficiaire probable | avertissement à l'opérateur, décision humaine |
| Action IA validée | journalisation avant application |

Les erreurs métier et les erreurs techniques sont distinguées : les premières
sont présentées à l'utilisateur en langage clair, les secondes sont journalisées
et présentées de façon générique.

---

## 14. Écarts et compléments par rapport au cahier des charges

| Point | Nature | Justification |
|---|---|---|
| Application `public` ajoutée | complément | les pages du §3.1 n'ont aucune application d'accueil dans la liste du §11.1 |
| Noyau `core` ajouté | complément | factorise le patron de campagne, garantit un point unique pour la règle anti-doublon |
| Géographie normalisée en entités | écart de modélisation | les champs texte du §4.1 rendraient impossible l'analyse par zone du §8.1 |
| Entité DISTRIBUTION unique | écart de modélisation | rend la prévention des doublons structurelle plutôt que procédurale |
| Entité PROPOSITION_IA | complément | matérialise la validation humaine exigée aux §7.3 et §12 |
| Analyse des besoins non fondée sur le modèle de langage | choix d'architecture | seule façon de satisfaire l'exigence d'explicabilité du §8.2 |
| Entités PRODUIT et CATEGORIE_BESOIN | complément | requises par les §4.3, §7.2 et §8.1, non listées au §10 |
| Notifications SMS | hors périmètre | le §6 les mentionne comme une possibilité ultérieure |

---

## 15. Points à valider avant implémentation

Le §13 impose que les fonctionnalités non définies précisément soient validées
avant d'être implémentées. Les points suivants relèvent de cette catégorie.

1. **Matrice des droits (§9.1)** — proposition de conception. Deux lectures en
   particulier méritent confirmation : le comptable est privé d'accès aux fiches
   bénéficiaires (principe de minimisation des données personnelles), et le rôle
   visiteur est interprété comme un compte de consultation externe.
2. **Règle de détection des doublons de bénéficiaires (§8.1)** — le périmètre de
   la recherche de similarité et le caractère bloquant ou non de
   l'avertissement.
3. **Critères de classement des zones (§8.1)** — l'ONG doit fournir les critères
   de priorisation. La conception les rend paramétrables plutôt que d'en figer
   un jeu arbitraire.
4. **Origine des besoins exprimés (§8)** — le cahier des charges suppose des
   besoins signalés sans préciser leur canal de collecte. L'entité BESOIN est
   prévue ; le processus de saisie reste à définir.
5. **Choix du fournisseur de modèle de langage** — arbitrage entre qualité de
   réponse et confidentialité des données personnelles. L'abstraction du §10.3
   permet de différer cette décision sans bloquer le développement.
6. **Devises et taux de change (§4.2)** — le don porte une devise ; la
   consolidation financière multi-devises n'est pas spécifiée.

---

## 16. Correspondance avec les livrables attendus (§15)

| Livrable du §15 | Traitement |
|---|---|
| Code source complet | lots 0 à 10 |
| Base de données et migrations | lots 0 à 5 |
| Interfaces du site public | lot 9 |
| Application de gestion interne | lots 1 à 6 |
| Module chatbot IA | lot 7 |
| Module d'analyse des besoins | lot 8 |
| Documentation technique | présent document, complété au lot 10 |
| Guide utilisateur | lot 10 |
| Rapports PDF et exports Excel | lot 6 |
| Procédure d'installation et de déploiement | lot 10 |
| Documentation des règles d'usage de l'IA | §9 et §10 du présent document |

---

## 17. Suite

Ce document constitue la conception validée. L'étape suivante est la rédaction
d'un plan d'implémentation détaillé, lot par lot, avant toute écriture de code.
