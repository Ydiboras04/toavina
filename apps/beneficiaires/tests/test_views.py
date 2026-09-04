"""Vérifie que les vues appliquent bien les droits de la couche services."""
import pytest
from django.urls import reverse

from apps.beneficiaires.forms import FormulaireBeneficiaire
from apps.beneficiaires.models import Beneficiaire, Sexe
from core.roles import Role

# La fixture `village` et la fabrique `creer_utilisateur` sont définies dans
# le conftest.py à la racine du projet.


@pytest.fixture
def connecter(client, creer_utilisateur):
    """Retourne une fonction `role -> Utilisateur` qui crée un utilisateur de
    ce rôle et le connecte au client de test."""

    def _connecter(role):
        utilisateur = creer_utilisateur(role)
        client.force_login(utilisateur)
        return utilisateur

    return _connecter


def test_liste_refusee_a_l_utilisateur_anonyme(client, db):
    """Un utilisateur anonyme est redirigé vers la page de connexion plutôt
    que de voir la liste (`@login_required`). `follow=True` est nécessaire
    ici : sans lui, le test ne vérifierait que la redirection 302 initiale,
    pas que la page vers laquelle elle pointe existe et répond réellement —
    un LOGIN_URL incohérent avec les routes montées sous « comptes/ »
    produirait un 404 à cette étape qui, sans `follow`, passerait inaperçu."""
    reponse = client.get(reverse("beneficiaires:liste"), follow=True)
    assert reponse.status_code == 200
    assert b"csrfmiddlewaretoken" in reponse.content


def test_liste_accessible_au_coordinateur(client, connecter, village):
    connecter(Role.COORDINATEUR)
    reponse = client.get(reverse("beneficiaires:liste"))
    assert reponse.status_code == 200


def test_liste_refusee_au_comptable(client, connecter, village):
    connecter(Role.COMPTABLE)
    reponse = client.get(reverse("beneficiaires:liste"))
    assert reponse.status_code == 403


def test_creation_refusee_au_volontaire(client, connecter, village):
    connecter(Role.VOLONTAIRE)
    reponse = client.post(
        reverse("beneficiaires:creer"),
        {"nom": "Rakoto", "prenom": "Jean", "sexe": Sexe.MASCULIN,
         "village": village.pk, "nombre_enfants": 0, "statut": "actif"},
    )
    assert reponse.status_code == 403
    assert Beneficiaire.objects.count() == 0


def test_creation_reussie_par_le_coordinateur(client, connecter, village):
    connecter(Role.COORDINATEUR)
    reponse = client.post(
        reverse("beneficiaires:creer"),
        {"nom": "Rakoto", "prenom": "Jean", "sexe": Sexe.MASCULIN,
         "village": village.pk, "nombre_enfants": 0, "statut": "actif"},
    )
    assert reponse.status_code == 302
    assert Beneficiaire.objects.count() == 1


def test_modification_par_le_coordinateur(client, connecter, village):
    connecter(Role.COORDINATEUR)
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


def test_modification_refusee_au_volontaire(client, connecter, village):
    connecter(Role.VOLONTAIRE)
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


def test_cin_masque_au_volontaire(client, connecter, village):
    beneficiaire = Beneficiaire.objects.create(
        nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN, village=village,
        numero_cin="101234567890",
    )
    connecter(Role.VOLONTAIRE)

    reponse = client.get(
        reverse("beneficiaires:detail", args=[beneficiaire.pk])
    )
    assert reponse.status_code == 200
    assert b"101234567890" not in reponse.content


def test_cin_visible_par_le_coordinateur(client, connecter, village):
    connecter(Role.COORDINATEUR)
    beneficiaire = Beneficiaire.objects.create(
        nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN, village=village,
        numero_cin="101234567890",
    )
    reponse = client.get(
        reverse("beneficiaires:detail", args=[beneficiaire.pk])
    )
    assert b"101234567890" in reponse.content


def test_creation_avec_cin_deja_utilise_reaffiche_le_formulaire(client, connecter, village):
    """Un CIN en double est une erreur de saisie (RegleMetierViolee), pas un
    refus de droit : la vue doit ré-afficher le formulaire avec une erreur,
    jamais laisser fuir une erreur 500 ni créer de second bénéficiaire."""
    Beneficiaire.objects.create(
        nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN, village=village,
        numero_cin="101234567890",
    )
    connecter(Role.COORDINATEUR)

    reponse = client.post(
        reverse("beneficiaires:creer"),
        {"nom": "Rabe", "prenom": "Marie", "sexe": Sexe.FEMININ,
         "village": village.pk, "nombre_enfants": 0, "statut": "actif",
         "numero_cin": "101234567890"},
    )

    assert reponse.status_code == 200
    assert Beneficiaire.objects.count() == 1


def test_modification_refusee_en_lecture_seule_des_l_affichage(client, connecter, village):
    """Le droit d'écriture doit être vérifié avant même de construire le
    formulaire, y compris sur un simple GET. Un volontaire n'a que le droit
    de lecture sur les bénéficiaires (Acces.LECTURE) : sans ce contrôle
    explicite, il passerait la vérification d'`obtenir_beneficiaire` (qui
    n'exige que LECTURE) et pourrait afficher le formulaire pré-rempli, alors
    que son POST échouerait de toute façon en 403 — la fuite se produirait
    dès l'affichage, pas seulement à la soumission."""
    connecter(Role.VOLONTAIRE)
    beneficiaire = Beneficiaire.objects.create(
        nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN, village=village,
        numero_cin="101234567890",
    )
    reponse = client.get(
        reverse("beneficiaires:modifier", args=[beneficiaire.pk])
    )
    assert reponse.status_code == 403


def test_champ_cin_absent_du_formulaire_sans_acces_aux_donnees_sensibles(
    village, creer_utilisateur
):
    """Le formulaire retire lui-même les champs sensibles (CIN, passeport,
    revenu) que l'utilisateur n'a pas le droit de lire, pour que
    `{{ formulaire.as_p }}` ne pré-remplisse jamais leur attribut `value=""`
    avec la valeur réelle.

    Remarque : aucun des sept rôles du référentiel actuel (§9.1) ne combine
    à la fois un droit d'écriture sur les bénéficiaires (Acces.PROPRE ou
    plus, requis pour atteindre la vue `modifier`) et l'absence d'accès aux
    données sensibles — seuls le coordinateur et le super administrateur
    peuvent écrire, et tous deux ont accès aux données sensibles. Ce test
    vérifie donc directement le comportement du formulaire — la même classe
    qu'utilise la vue `modifier` — avec un rôle sans accès aux données
    sensibles (volontaire), indépendamment du contrôle d'autorisation de la
    vue déjà couvert par le test précédent.
    """
    beneficiaire = Beneficiaire.objects.create(
        nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN, village=village,
        numero_cin="101234567890",
    )
    utilisateur = creer_utilisateur(Role.VOLONTAIRE)

    formulaire = FormulaireBeneficiaire(instance=beneficiaire, utilisateur=utilisateur)

    assert "numero_cin" not in formulaire.fields
    assert "101234567890" not in str(formulaire)


def test_fiche_introuvable_renvoie_404(client, connecter, village):
    """Un identifiant qui ne correspond à aucun bénéficiaire doit produire un
    404 ordinaire, jamais une erreur serveur : `obtenir_beneficiaire` traduit
    `Beneficiaire.DoesNotExist` en `Introuvable`, que la vue traduit à son
    tour en `Http404`."""
    connecter(Role.COORDINATEUR)
    reponse = client.get(reverse("beneficiaires:detail", args=[999999]))
    assert reponse.status_code == 404


def test_fiche_archivee_renvoie_404_et_non_500(client, connecter, village):
    """Archiver une fiche la retire du manager par défaut (`Beneficiaire.
    objects`) qu'interroge `obtenir_beneficiaire` : une URL de détail ou de
    modification encore en circulation vers une fiche désormais archivée doit
    donc afficher un 404, pas planter en 500 — l'archivage remplace la
    suppression dans tout ce projet, la conséquence d'un archivage sur les
    URL déjà partagées doit donc être maîtrisée."""
    connecter(Role.COORDINATEUR)
    beneficiaire = Beneficiaire.objects.create(
        nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN, village=village,
    )
    beneficiaire.archive = True
    beneficiaire.save(update_fields=["archive"])

    reponse_detail = client.get(
        reverse("beneficiaires:detail", args=[beneficiaire.pk])
    )
    reponse_modifier = client.get(
        reverse("beneficiaires:modifier", args=[beneficiaire.pk])
    )

    assert reponse_detail.status_code == 404
    assert reponse_modifier.status_code == 404


def test_lien_nouveau_beneficiaire_absent_pour_un_volontaire(client, connecter, village):
    """Un volontaire n'a que le droit de lecture sur les bénéficiaires : le
    lien « Nouveau bénéficiaire » mènerait systématiquement à un 403 s'il
    était affiché, la liste ne doit donc pas le proposer."""
    connecter(Role.VOLONTAIRE)
    reponse = client.get(reverse("beneficiaires:liste"))
    assert reponse.status_code == 200
    assert "Nouveau bénéficiaire".encode() not in reponse.content


def test_lien_nouveau_beneficiaire_visible_pour_un_coordinateur(client, connecter, village):
    connecter(Role.COORDINATEUR)
    reponse = client.get(reverse("beneficiaires:liste"))
    assert reponse.status_code == 200
    assert "Nouveau bénéficiaire".encode() in reponse.content


def test_la_fiche_affiche_la_section_historique(client, connecter, village):
    """Le brief appelle `connecter(client, Role.COORDINATEUR)`, mais dans ce
    fichier `connecter` est une fixture qui ferme déjà sur `client` et ne
    prend que le rôle en argument (voir sa définition en tête de fichier) —
    contrairement à la fonction `connecter(client, role)` utilisée dans
    d'autres suites du dépôt. Adapté à la convention locale."""
    from apps.beneficiaires.models import Beneficiaire

    connecter(Role.COORDINATEUR)
    beneficiaire = Beneficiaire.objects.create(
        nom="Rakoto", prenom="Jean", sexe=Sexe.MASCULIN, village=village
    )
    reponse = client.get(
        reverse("beneficiaires:detail", args=[beneficiaire.pk])
    )
    assert reponse.status_code == 200
    assert "Aides reçues".encode() in reponse.content
