"""Vérifie la matrice des droits du §9.1 de la spécification."""
from types import MappingProxyType

import pytest

from core.exceptions import PermissionRefusee
from core.permissions import (
    MATRICE,
    Acces,
    Module,
    acces,
    exiger,
    perimetre_restreint,
    peut_ecrire,
    peut_lire,
)
from core.roles import Role

# Transcription à la main du tableau du §9.1 (section « Matrice des droits »)
# du brief — volontairement indépendante de `MATRICE` : ce tableau doit
# détecter une régression de `core.permissions.MATRICE`, pas la reproduire.
_A, _L, _P, _C = Acces.AUCUN, Acces.LECTURE, Acces.PROPRE, Acces.COMPLET

TABLEAU_ATTENDU = {
    Role.SUPER_ADMIN: {
        Module.BENEFICIAIRES: _C,
        Module.DONNEES_SENSIBLES: _C,
        Module.PROJETS: _C,
        Module.DISTRIBUTIONS: _C,
        Module.FINANCES: _C,
        Module.DOCUMENTS: _C,
        Module.STATISTIQUES: _C,
        Module.UTILISATEURS: _C,
        Module.ASSISTANT_IA: _C,
        Module.ANALYSE_BESOINS: _C,
        Module.VALIDATION_IA: _C,
    },
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
    Role.VISITEUR: {
        Module.BENEFICIAIRES: _A,
        Module.DONNEES_SENSIBLES: _A,
        Module.PROJETS: _A,
        Module.DISTRIBUTIONS: _A,
        Module.FINANCES: _A,
        Module.DOCUMENTS: _A,
        Module.STATISTIQUES: _A,
        Module.UTILISATEURS: _A,
        Module.ASSISTANT_IA: _A,
        Module.ANALYSE_BESOINS: _A,
        Module.VALIDATION_IA: _A,
    },
}

# 7 rôles x 11 modules = 77 cellules attendues.
CELLULES = [
    pytest.param(role, module, valeur, id=f"{role.value}/{module.value}")
    for role, colonnes in TABLEAU_ATTENDU.items()
    for module, valeur in colonnes.items()
]


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


def test_volontaire_limite_a_ses_propres_conversations_ia():
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


def test_matrice_declare_les_onze_modules_pour_chaque_role():
    """Verrou d'exhaustivité : un module oublié retomberait sur AUCUN.

    Si un douzième module était ajouté à `Module`, les rôles dont les
    entrées sont écrites à la main (tous sauf SUPER_ADMIN et VISITEUR,
    construits par compréhension) tomberaient silencieusement à AUCUN sur
    cette nouvelle entrée. Ce test rend l'incohérence bruyante.
    """
    for role in Role:
        for module in Module:
            assert module in MATRICE[role], (
                f"Le module {module} est absent de la ligne {role} de MATRICE."
            )


@pytest.mark.parametrize("role,module,attendu", CELLULES)
def test_cellule_de_la_matrice(role, module, attendu):
    """Épingle les 77 cellules du tableau du §9.1, une à une."""
    utilisateur = UtilisateurFactice(role)
    assert acces(utilisateur, module) == attendu


def test_matrice_est_non_modifiable():
    utilisateur = UtilisateurFactice(Role.VISITEUR)
    assert isinstance(MATRICE, MappingProxyType)
    assert isinstance(MATRICE[Role.VISITEUR], MappingProxyType)

    with pytest.raises(TypeError):
        MATRICE[Role.VISITEUR][Module.FINANCES] = Acces.COMPLET

    with pytest.raises(TypeError):
        MATRICE[Role.VISITEUR] = {}

    # Aucune élévation de privilège n'a eu lieu.
    assert acces(utilisateur, Module.FINANCES) == Acces.AUCUN


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
