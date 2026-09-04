"""Vérifie les règles métier et le filtrage par rôle des bénéficiaires."""
import pytest

from apps.beneficiaires.models import Beneficiaire, Sexe
from apps.beneficiaires.services import (
    CHAMPS_COURANTS,
    CHAMPS_SENSIBLES,
    archiver_beneficiaire,
    champs_visibles,
    creer_beneficiaire,
    lister_beneficiaires,
    modifier_beneficiaire,
    obtenir_beneficiaire,
    rechercher_doublons,
)
from apps.geographie.models import Village
from core.exceptions import Introuvable, PermissionRefusee, RegleMetierViolee
from core.roles import Role

# Les fixtures `village` et `creer_utilisateur` sont définies dans le
# conftest.py à la racine du projet.


@pytest.fixture
def coordinateur(creer_utilisateur):
    return creer_utilisateur(Role.COORDINATEUR)


@pytest.fixture
def comptable(creer_utilisateur):
    return creer_utilisateur(Role.COMPTABLE)


@pytest.fixture
def volontaire(creer_utilisateur):
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
    """Un homonyme réel dans un même village reste possible (§8.1).

    La détection avertit — un décompte de doublon avant la seconde création —
    mais ne bloque jamais : la création réussit malgré l'avertissement, et les
    deux fiches coexistent.
    """
    creer_beneficiaire(
        coordinateur, nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN,
        date_naissance="1985-04-12", village=village,
    )

    doublons = rechercher_doublons(
        coordinateur, nom="Rakoto", prenom="Jean",
        date_naissance="1985-04-12", village=village,
    )
    assert doublons.count() == 1

    second = creer_beneficiaire(
        coordinateur, nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN,
        date_naissance="1985-04-12", village=village,
    )
    assert second.pk is not None
    assert Beneficiaire.objects.count() == 2


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


# --- Modification partielle et CIN -----------------------------------------


def test_modification_partielle_ne_touche_pas_au_cin(coordinateur, village):
    """Modifier un champ sans mentionner numero_cin ne doit pas l'effacer."""
    beneficiaire = creer_beneficiaire(
        coordinateur, nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN,
        village=village, numero_cin="101112013000",
    )
    modifier_beneficiaire(coordinateur, beneficiaire.pk, telephone="033 12 345 67")
    beneficiaire.refresh_from_db()
    assert beneficiaire.numero_cin == "101112013000"
    assert beneficiaire.telephone == "033 12 345 67"


# --- Champs acceptés par creer_beneficiaire/modifier_beneficiaire ----------


def test_modifier_beneficiaire_ne_peut_pas_archiver(coordinateur, village):
    """L'archivage a son propre niveau de droit (COMPLET) : le contourner via
    modifier_beneficiaire (PROPRE) doit être structurellement impossible."""
    beneficiaire = creer_beneficiaire(
        coordinateur, nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN,
        village=village,
    )
    with pytest.raises(RegleMetierViolee):
        modifier_beneficiaire(coordinateur, beneficiaire.pk, archive=True)


def test_champ_inconnu_leve_une_exception(coordinateur, village):
    """Une clé mal orthographiée ne doit pas être silencieusement perdue."""
    with pytest.raises(RegleMetierViolee):
        creer_beneficiaire(
            coordinateur, nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN,
            village=village, champ_invalide="valeur",
        )


# --- Doublons et bénéficiaires archivés -------------------------------------


def test_doublon_detecte_avec_beneficiaire_archive(coordinateur, village):
    beneficiaire = creer_beneficiaire(
        coordinateur, nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN,
        date_naissance="1985-04-12", village=village,
    )
    archiver_beneficiaire(coordinateur, beneficiaire.pk)

    doublons = rechercher_doublons(
        coordinateur, nom="Rakoto", prenom="Jean",
        date_naissance="1985-04-12", village=village,
    )
    assert doublons.count() == 1


# --- Unicité du CIN vérifiée en service (indépendamment du formulaire) -----


def test_creation_refuse_cin_deja_utilise(coordinateur, village):
    creer_beneficiaire(
        coordinateur, nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN,
        village=village, numero_cin="101112013000",
    )
    with pytest.raises(RegleMetierViolee):
        creer_beneficiaire(
            coordinateur, nom="Rabe", prenom="Paul", sexe=Sexe.MASCULIN,
            village=village, numero_cin="101112013000",
        )


def test_modification_conserve_son_propre_cin(coordinateur, village):
    """Renvoyer le même CIN sur sa propre fiche ne doit pas être refusé."""
    beneficiaire = creer_beneficiaire(
        coordinateur, nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN,
        village=village, numero_cin="101112013000",
    )
    modifie = modifier_beneficiaire(
        coordinateur, beneficiaire.pk, numero_cin="101112013000",
    )
    assert modifie.numero_cin == "101112013000"


# --- Doublon non masqué par une date de naissance manquante en base --------


def test_doublon_detecte_quand_date_naissance_absente_en_base(coordinateur, village):
    """Une fiche existante sans date de naissance doit quand même remonter
    face à une nouvelle saisie qui, elle, en comporte une."""
    creer_beneficiaire(
        coordinateur, nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN,
        village=village,
    )
    doublons = rechercher_doublons(
        coordinateur, nom="Rakoto", prenom="Jean",
        date_naissance="1985-04-12", village=village,
    )
    assert doublons.count() == 1


# --- Contrôle des droits sur chaque fonction du service --------------------


def test_obtenir_beneficiaire_refuse_un_comptable(comptable):
    with pytest.raises(PermissionRefusee):
        obtenir_beneficiaire(comptable, 1)


def test_modifier_beneficiaire_refuse_un_volontaire(volontaire, coordinateur, village):
    beneficiaire = creer_beneficiaire(
        coordinateur, nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN,
        village=village,
    )
    with pytest.raises(PermissionRefusee):
        modifier_beneficiaire(volontaire, beneficiaire.pk, telephone="033 00 000 00")


def test_archiver_beneficiaire_refuse_un_volontaire(volontaire, coordinateur, village):
    beneficiaire = creer_beneficiaire(
        coordinateur, nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN,
        village=village,
    )
    with pytest.raises(PermissionRefusee):
        archiver_beneficiaire(volontaire, beneficiaire.pk)


def test_rechercher_doublons_refuse_un_comptable(comptable, village):
    with pytest.raises(PermissionRefusee):
        rechercher_doublons(
            comptable, nom="Rakoto", prenom="Jean",
            date_naissance="1985-04-12", village=village,
        )


def test_lister_beneficiaires_filtre_par_village(coordinateur, village):
    autre = Village.objects.create(libelle="Ampasy", commune=village.commune)
    creer_beneficiaire(
        coordinateur, nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN,
        village=village,
    )
    creer_beneficiaire(
        coordinateur, nom="Rabe", prenom="Paul", sexe=Sexe.MASCULIN,
        village=autre,
    )
    assert lister_beneficiaires(coordinateur, village=village).count() == 1


def test_champs_visibles_gere_le_revenu_selon_le_role(coordinateur, volontaire):
    """Le revenu est le plus délicat des trois champs sensibles pour une ONG."""
    assert "revenu" in champs_visibles(coordinateur)
    assert "revenu" not in champs_visibles(volontaire)


# --- Ressource introuvable (identifiant inexistant ou fiche archivée) ------
#
# `obtenir_beneficiaire` interroge `Beneficiaire.objects`, qui masque les
# fiches archivées : sans traduction explicite de `Beneficiaire.DoesNotExist`,
# une URL encore en circulation vers une fiche entre-temps archivée
# planterait en erreur serveur plutôt que d'afficher un 404 ordinaire.
# L'archivage remplace la suppression dans tout ce projet (§8 du MPD) : cette
# conséquence sur les URL déjà partagées doit donc être maîtrisée.


def test_obtenir_beneficiaire_leve_introuvable_pour_un_identifiant_inexistant(
    coordinateur,
):
    with pytest.raises(Introuvable):
        obtenir_beneficiaire(coordinateur, 999999)


def test_obtenir_beneficiaire_leve_introuvable_pour_une_fiche_archivee(
    coordinateur, village
):
    beneficiaire = creer_beneficiaire(
        coordinateur, nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN,
        village=village,
    )
    archiver_beneficiaire(coordinateur, beneficiaire.pk)

    with pytest.raises(Introuvable):
        obtenir_beneficiaire(coordinateur, beneficiaire.pk)


# --- Validation des données, indépendante du formulaire ---------------------
#
# Le formulaire vérifie aujourd'hui les listes de choix et les longueurs
# maximales, mais un appelant qui n'emprunte pas le formulaire — un futur
# outil de l'assistant IA, par exemple — passerait à travers ce filet. La
# couche services doit donc appliquer les mêmes règles elle-même, via
# `full_clean()`, et les traduire en RegleMetierViolee.


def test_creer_beneficiaire_refuse_un_sexe_hors_liste_de_choix(coordinateur, village):
    with pytest.raises(RegleMetierViolee):
        creer_beneficiaire(
            coordinateur, nom="Rakoto", prenom="Jean", sexe="ZZZ",
            village=village,
        )


def test_creer_beneficiaire_refuse_un_nombre_denfants_negatif(coordinateur, village):
    with pytest.raises(RegleMetierViolee):
        creer_beneficiaire(
            coordinateur, nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN,
            village=village, nombre_enfants=-1,
        )


# --- Exhaustivité des ensembles de champs -----------------------------------


def test_ensemble_des_champs_couvre_tous_les_champs_du_modele():
    """Un futur champ ajouté au modèle doit appartenir à l'un des deux
    ensembles, sous peine de fuiter silencieusement au lieu d'être classé."""
    champs_exclus = {"archive", "date_creation", "date_modification"}
    champs_modele = {
        champ.name for champ in Beneficiaire._meta.concrete_fields
    } - champs_exclus
    assert champs_modele == CHAMPS_COURANTS | CHAMPS_SENSIBLES


# --- Historique des aides reçues --------------------------------------------


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


def test_historique_aides_voit_au_dela_du_perimetre(
    volontaire, coordinateur, beneficiaire, village, type_action, creer_utilisateur
):
    """Verrou de la correction demandée par le coordinateur : sans elle,
    `historique_aides` passerait par `lister_distributions` et un volontaire
    ne verrait que ses propres saisies — une aide reçue par le bénéficiaire
    mais servie par un collègue resterait invisible, alors que c'est
    exactement ce que cette fonction doit garantir (§8.1)."""
    from apps.beneficiaires.services import historique_aides
    from apps.campagnes.services import creer_campagne, enregistrer_distribution
    from apps.projets.models import Projet
    from core.roles import Role

    projet = Projet.objects.create(
        code="PROJ-2026-003", titre="Distribution", budget_prevu="1000.00",
        date_debut="2026-01-15", type_action=type_action,
        responsable=creer_utilisateur(Role.RESPONSABLE_PROJET, nom="resp11"),
    )
    campagne = creer_campagne(
        coordinateur, code="RAM-2028", libelle="Ramadan", annee=2028,
        budget="500.00", date_debut="2028-02-18", projet=projet,
        responsable=coordinateur,
    )
    collegue = creer_utilisateur(Role.VOLONTAIRE, nom="volB")
    enregistrer_distribution(
        collegue, beneficiaire=beneficiaire, campagne=campagne,
        village=village, date_distribution="2028-02-20",
    )

    historique = historique_aides(volontaire, beneficiaire.pk)
    assert historique.count() == 1
