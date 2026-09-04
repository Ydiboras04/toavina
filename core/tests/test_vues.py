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
