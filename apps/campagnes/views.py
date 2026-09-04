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
