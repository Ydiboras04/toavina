"""Vérifie les règles métier des distributions, dont la prévention des doublons."""
import pytest

from apps.campagnes.models import CampagneAide, DistributionAide
from apps.campagnes.services import (
    a_deja_recu,
    annuler_distribution,
    creer_campagne,
    enregistrer_distribution,
    historique_beneficiaire,
    lister_campagnes,
    lister_distributions,
    obtenir_campagne,
)
from apps.geographie.models import Village
from apps.projets.models import Projet
from core.exceptions import Introuvable, PermissionRefusee, RegleMetierViolee
from core.models import EtatCampagne
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
    """Un seul village en base laisserait passer un filtre inopérant : on en
    crée un second et on vérifie le cas négatif, comme pour les campagnes."""
    autre_village = Village.objects.create(
        libelle="Ambovoary", commune=village.commune
    )
    enregistrer_distribution(
        volontaire, beneficiaire=beneficiaire, campagne=campagne,
        village=village, date_distribution="2026-02-20",
    )
    assert lister_distributions(volontaire, village=village).count() == 1
    assert lister_distributions(volontaire, village=autre_village).count() == 0


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


# --- IMPORTANT 1 : périmètre, responsable, code unique des campagnes -------
# Calque exactement le patron déjà posé par `apps.projets.services`, pour le
# rôle qui partage le même niveau d'accès (« propre ») sur `Module.PROJETS`.

def test_responsable_de_projet_ne_voit_que_ses_campagnes(
    creer_utilisateur, coordinateur, projet
):
    resp_a = creer_utilisateur(Role.RESPONSABLE_PROJET, nom="respA")
    resp_b = creer_utilisateur(Role.RESPONSABLE_PROJET, nom="respB")
    creer_campagne(
        resp_a, code="RAM-2026-A", libelle="Ramadan", annee=2026,
        budget="500000.00", date_debut="2026-02-18", projet=projet,
        responsable=resp_a,
    )
    creer_campagne(
        resp_b, code="RAM-2026-B", libelle="Ramadan", annee=2026,
        budget="500000.00", date_debut="2026-02-18", projet=projet,
        responsable=resp_b,
    )
    assert lister_campagnes(resp_a).count() == 1
    assert lister_campagnes(coordinateur).count() == 2


def test_responsable_de_projet_ne_peut_pas_creer_de_campagne_pour_un_collegue(
    creer_utilisateur, projet
):
    resp_a = creer_utilisateur(Role.RESPONSABLE_PROJET, nom="respA")
    resp_b = creer_utilisateur(Role.RESPONSABLE_PROJET, nom="respB")
    with pytest.raises(RegleMetierViolee):
        creer_campagne(
            resp_a, code="RAM-2026-C", libelle="Ramadan", annee=2026,
            budget="500000.00", date_debut="2026-02-18", projet=projet,
            responsable=resp_b,
        )


def test_code_de_campagne_deja_utilise_refuse(campagne, coordinateur, projet):
    with pytest.raises(RegleMetierViolee) as erreur:
        creer_campagne(
            coordinateur, code=campagne.code, libelle="Ramadan bis",
            annee=2026, budget="100000.00", date_debut="2026-03-01",
            projet=projet, responsable=coordinateur,
        )
    assert "déjà utilisé" in str(erreur.value)


def test_creer_campagne_avec_date_fin_anterieure_refusee(coordinateur, projet):
    """Premier modèle concret héritant de `Campagne` : sa méthode `clean()`
    n'était couverte par aucun test."""
    with pytest.raises(RegleMetierViolee) as erreur:
        creer_campagne(
            coordinateur, code="RAM-2026-DATES", libelle="Ramadan",
            annee=2026, budget="500000.00", date_debut="2026-02-18",
            date_fin="2026-01-01", projet=projet, responsable=coordinateur,
        )
    assert "__all__" not in str(erreur.value)


# --- IMPORTANT 2 : traçabilité de l'annulation ------------------------------

def test_annulation_renseigne_qui_et_quand(
    volontaire, coordinateur, campagne, beneficiaire, village
):
    distribution = enregistrer_distribution(
        volontaire, beneficiaire=beneficiaire, campagne=campagne,
        village=village, date_distribution="2026-02-20",
    )
    annulee = annuler_distribution(
        coordinateur, distribution.pk, motif="Erreur de saisie"
    )
    assert annulee.annulee_par == coordinateur
    assert annulee.date_annulation is not None


def test_champs_annulation_nuls_avant_annulation(
    volontaire, campagne, beneficiaire, village
):
    distribution = enregistrer_distribution(
        volontaire, beneficiaire=beneficiaire, campagne=campagne,
        village=village, date_distribution="2026-02-20",
    )
    assert distribution.annulee_par is None
    assert distribution.date_annulation is None


def test_annulation_refuse_un_motif_uniquement_fait_d_espaces(
    volontaire, campagne, beneficiaire, village
):
    distribution = enregistrer_distribution(
        volontaire, beneficiaire=beneficiaire, campagne=campagne,
        village=village, date_distribution="2026-02-20",
    )
    with pytest.raises(RegleMetierViolee):
        annuler_distribution(volontaire, distribution.pk, motif="   ")


# --- IMPORTANT 3 : la course entre la vérification et l'écriture -----------

def test_conflit_concurrent_convertit_l_integrityerror_en_regle_metier_violee(
    volontaire, campagne, beneficiaire, village, monkeypatch
):
    """Simule deux volontaires servant le même bénéficiaire au même instant :
    la vérification préalable est neutralisée ici pour reproduire fidèlement
    ce qu'elle verrait dans une vraie course (« pas encore de doublon »),
    alors qu'une distribution active existe déjà réellement en base. Seule la
    contrainte du SGBD arrête alors l'écriture, sous la forme d'une
    `IntegrityError` que le service doit convertir en `RegleMetierViolee`.
    """
    enregistrer_distribution(
        volontaire, beneficiaire=beneficiaire, campagne=campagne,
        village=village, date_distribution="2026-02-20",
    )
    monkeypatch.setattr(
        "apps.campagnes.services.a_deja_recu", lambda *a, **k: False
    )
    with pytest.raises(RegleMetierViolee) as erreur:
        enregistrer_distribution(
            volontaire, beneficiaire=beneficiaire, campagne=campagne,
            village=village, date_distribution="2026-02-25",
        )
    assert "déjà reçu" in str(erreur.value)


# --- IMPORTANT 4 : une campagne close ne reçoit plus de distribution -------

def test_refus_distribution_sur_campagne_annulee(
    volontaire, coordinateur, projet, beneficiaire, village
):
    campagne_annulee = creer_campagne(
        coordinateur, code="RAM-2026-ANN", libelle="Ramadan", annee=2026,
        budget="500000.00", date_debut="2026-02-18", projet=projet,
        responsable=coordinateur, etat=EtatCampagne.ANNULEE,
    )
    with pytest.raises(RegleMetierViolee):
        enregistrer_distribution(
            volontaire, beneficiaire=beneficiaire, campagne=campagne_annulee,
            village=village, date_distribution="2026-02-20",
        )


def test_distribution_acceptee_sur_campagne_en_cours(
    volontaire, coordinateur, projet, beneficiaire, village
):
    campagne_en_cours = creer_campagne(
        coordinateur, code="RAM-2026-EC", libelle="Ramadan", annee=2026,
        budget="500000.00", date_debut="2026-02-18", projet=projet,
        responsable=coordinateur, etat=EtatCampagne.EN_COURS,
    )
    distribution = enregistrer_distribution(
        volontaire, beneficiaire=beneficiaire, campagne=campagne_en_cours,
        village=village, date_distribution="2026-02-20",
    )
    assert distribution.pk is not None


# --- IMPORTANT 5 : trois comportements corrects mais non verrouillés -------

def test_volontaire_ne_peut_pas_annuler_la_saisie_d_un_collegue(
    volontaire, creer_utilisateur, campagne, beneficiaire, village
):
    distribution = enregistrer_distribution(
        volontaire, beneficiaire=beneficiaire, campagne=campagne,
        village=village, date_distribution="2026-02-20",
    )
    collegue = creer_utilisateur(Role.VOLONTAIRE, nom="vol2")
    with pytest.raises(Introuvable):
        annuler_distribution(collegue, distribution.pk, motif="Erreur de saisie")


def test_saisie_par_n_est_pas_falsifiable(
    volontaire, creer_utilisateur, campagne, beneficiaire, village
):
    autre = creer_utilisateur(Role.VOLONTAIRE, nom="vol3")
    with pytest.raises(RegleMetierViolee):
        enregistrer_distribution(
            volontaire, beneficiaire=beneficiaire, campagne=campagne,
            village=village, date_distribution="2026-02-20", saisie_par=autre,
        )


def test_a_deja_recu_voit_au_dela_du_perimetre(
    volontaire, creer_utilisateur, campagne, beneficiaire, village
):
    """C'est la décision de conception la plus délicate du module. Un test
    qui interroge avec l'auteur de la saisie passerait même si la fonction
    était filtrée par périmètre : celui-ci interroge depuis un autre
    volontaire pour le prouver réellement."""
    autre = creer_utilisateur(Role.VOLONTAIRE, nom="vol4")
    enregistrer_distribution(
        autre, beneficiaire=beneficiaire, campagne=campagne,
        village=village, date_distribution="2026-02-20",
    )
    assert a_deja_recu(volontaire, beneficiaire, campagne) is True


# --- historique_beneficiaire : même raisonnement que a_deja_recu, pour la ---
# --- vue d'ensemble plutôt qu'une seule campagne. ---------------------------


def test_historique_beneficiaire_voit_au_dela_du_perimetre(
    volontaire, creer_utilisateur, campagne, beneficiaire, village
):
    """Même preuve que `test_a_deja_recu_voit_au_dela_du_perimetre` : la
    saisie est faite par un autre volontaire, et interrogée par celui-ci —
    un test qui interrogerait avec l'auteur de la saisie passerait même si
    la fonction était (à tort) filtrée par périmètre."""
    autre = creer_utilisateur(Role.VOLONTAIRE, nom="vol5")
    enregistrer_distribution(
        autre, beneficiaire=beneficiaire, campagne=campagne,
        village=village, date_distribution="2026-02-20",
    )
    historique = historique_beneficiaire(volontaire, beneficiaire)
    assert historique.count() == 1
    assert historique.first().saisie_par == autre


def test_historique_beneficiaire_refuse_a_un_comptable(
    creer_utilisateur, beneficiaire
):
    comptable = creer_utilisateur(Role.COMPTABLE)
    with pytest.raises(PermissionRefusee):
        historique_beneficiaire(comptable, beneficiaire)


# --- IMPORTANT 6 : le niveau « propre » d'un responsable de projet couvre --
# --- aussi son périmètre, pas seulement ses saisies (§9.1 : « ses propres ---
# --- objets ou son périmètre »). Sans quoi la liste des distributions est --
# --- vide pour lui, alors qu'il répond des campagnes de son projet. -------

def test_responsable_de_projet_voit_les_saisies_de_son_perimetre(
    creer_utilisateur, coordinateur, type_action, village, beneficiaire
):
    """Une distribution saisie par un volontaire, sur une campagne d'un
    projet dont l'utilisateur est responsable, doit lui être visible — même
    s'il n'en est pas lui-même l'auteur."""
    resp = creer_utilisateur(Role.RESPONSABLE_PROJET, nom="resp_perim")
    volontaire = creer_utilisateur(Role.VOLONTAIRE, nom="vol_perim")
    projet = Projet.objects.create(
        code="PROJ-2026-PERIM", titre="Projet du périmètre",
        budget_prevu="1000000.00", date_debut="2026-01-15",
        type_action=type_action, responsable=resp,
    )
    campagne = creer_campagne(
        coordinateur, code="RAM-2026-PERIM", libelle="Ramadan", annee=2026,
        budget="500000.00", date_debut="2026-02-18", projet=projet,
        responsable=coordinateur,
    )
    distribution = enregistrer_distribution(
        volontaire, beneficiaire=beneficiaire, campagne=campagne,
        village=village, date_distribution="2026-02-20",
    )

    resultats = lister_distributions(resp)
    assert resultats.count() == 1
    assert resultats.first().pk == distribution.pk
    assert resultats.first().saisie_par == volontaire


def test_responsable_de_projet_ne_voit_pas_les_distributions_d_un_autre_projet(
    creer_utilisateur, coordinateur, type_action, village, beneficiaire
):
    from apps.beneficiaires.models import Beneficiaire

    resp_a = creer_utilisateur(Role.RESPONSABLE_PROJET, nom="respA_perim")
    resp_b = creer_utilisateur(Role.RESPONSABLE_PROJET, nom="respB_perim")
    volontaire = creer_utilisateur(Role.VOLONTAIRE, nom="vol_perim2")

    projet_a = Projet.objects.create(
        code="PROJ-2026-PERIM-A", titre="Projet A",
        budget_prevu="1000000.00", date_debut="2026-01-15",
        type_action=type_action, responsable=resp_a,
    )
    projet_b = Projet.objects.create(
        code="PROJ-2026-PERIM-B", titre="Projet B",
        budget_prevu="1000000.00", date_debut="2026-01-15",
        type_action=type_action, responsable=resp_b,
    )
    campagne_b = creer_campagne(
        coordinateur, code="RAM-2026-PERIM-B", libelle="Ramadan", annee=2026,
        budget="500000.00", date_debut="2026-02-18", projet=projet_b,
        responsable=coordinateur,
    )
    autre_beneficiaire = Beneficiaire.objects.create(
        nom="Rasoa", prenom="Marie", sexe="F", village=village
    )
    enregistrer_distribution(
        volontaire, beneficiaire=autre_beneficiaire, campagne=campagne_b,
        village=village, date_distribution="2026-02-20",
    )

    assert projet_a.pk is not None  # projet_a existe, mais n'a aucune campagne
    assert lister_distributions(resp_a).count() == 0
    assert lister_distributions(resp_b).count() == 1


def test_volontaire_ne_voit_toujours_que_ses_propres_saisies(
    creer_utilisateur, coordinateur, type_action, village, beneficiaire
):
    """Le périmètre élargi du responsable de projet ne doit rien changer au
    comportement du volontaire : il reste limité à ce qu'il a lui-même saisi,
    même quand une campagne de son propre projet reçoit une saisie d'un
    collègue."""
    from apps.beneficiaires.models import Beneficiaire

    resp = creer_utilisateur(Role.RESPONSABLE_PROJET, nom="resp_perim3")
    volontaire = creer_utilisateur(Role.VOLONTAIRE, nom="vol_perim3")
    collegue = creer_utilisateur(Role.VOLONTAIRE, nom="collegue_perim3")
    projet = Projet.objects.create(
        code="PROJ-2026-PERIM3", titre="Projet du volontaire",
        budget_prevu="1000000.00", date_debut="2026-01-15",
        type_action=type_action, responsable=resp,
    )
    campagne = creer_campagne(
        coordinateur, code="RAM-2026-PERIM3", libelle="Ramadan", annee=2026,
        budget="500000.00", date_debut="2026-02-18", projet=projet,
        responsable=coordinateur,
    )
    autre_beneficiaire = Beneficiaire.objects.create(
        nom="Randria", prenom="Luc", sexe="M", village=village
    )
    enregistrer_distribution(
        volontaire, beneficiaire=beneficiaire, campagne=campagne,
        village=village, date_distribution="2026-02-20",
    )
    enregistrer_distribution(
        collegue, beneficiaire=autre_beneficiaire, campagne=campagne,
        village=village, date_distribution="2026-02-21",
    )

    resultats = lister_distributions(volontaire)
    assert resultats.count() == 1
    assert resultats.first().saisie_par == volontaire
