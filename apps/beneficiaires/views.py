"""Vues des bénéficiaires.

Aucune règle métier ici : chaque vue appelle un service et laisse le
décorateur `@traduire_erreurs_metier` (core/vues.py) traduire ses exceptions
en réponses HTTP — PermissionRefusee en 403, Introuvable en 404 (§4 de la
spécification).

Une vue intercepte elle-même RegleMetierViolee — levée par la couche services
pour un numéro CIN déjà attribué ou une clé de champ non autorisée — sans
passer par le décorateur : il s'agit d'une erreur de saisie, pas d'un refus
de droit, et seule la vue sait rattacher le message au formulaire, qui est
ré-affiché pour que l'opérateur puisse corriger.
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.beneficiaires.forms import FormulaireBeneficiaire
from apps.beneficiaires.services import (
    champs_visibles,
    creer_beneficiaire,
    historique_aides,
    lister_beneficiaires,
    modifier_beneficiaire,
    obtenir_beneficiaire,
    rechercher_doublons,
)
from core.exceptions import RegleMetierViolee
from core.permissions import Acces, Module, exiger, peut_ecrire
from core.vues import traduire_erreurs_metier


@login_required
@traduire_erreurs_metier
def liste(requete):
    recherche = requete.GET.get("recherche", "")
    beneficiaires = lister_beneficiaires(requete.user, recherche=recherche)

    return render(
        requete,
        "beneficiaires/liste.html",
        {
            "beneficiaires": beneficiaires,
            "recherche": recherche,
            "peut_modifier": peut_ecrire(requete.user, Module.BENEFICIAIRES),
        },
    )


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
            "historique": historique_aides(requete.user, beneficiaire),
        },
    )


@login_required
@traduire_erreurs_metier
def creer(requete):
    est_post = requete.method == "POST"
    formulaire = FormulaireBeneficiaire(
        requete.POST if est_post else None,
        requete.FILES if est_post else None,
        utilisateur=requete.user,
    )
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
        except RegleMetierViolee as erreur:
            formulaire.add_error(None, str(erreur))
            return render(
                requete,
                "beneficiaires/formulaire.html",
                {"formulaire": formulaire, "doublons": doublons},
            )

        return redirect("beneficiaires:detail", identifiant=beneficiaire.pk)

    return render(
        requete,
        "beneficiaires/formulaire.html",
        {"formulaire": formulaire, "doublons": doublons},
    )


@login_required
@traduire_erreurs_metier
def modifier(requete, identifiant):
    beneficiaire = obtenir_beneficiaire(requete.user, identifiant)
    # Contrôle d'autorisation (pas une règle métier) : sans lui, un
    # utilisateur qui n'a que le droit de lecture (volontaire,
    # responsable de projet) pourrait afficher le formulaire pré-rempli
    # en GET, avant même que le POST n'échoue en 403.
    exiger(requete.user, Module.BENEFICIAIRES, Acces.PROPRE)

    est_post = requete.method == "POST"
    formulaire = FormulaireBeneficiaire(
        requete.POST if est_post else None,
        requete.FILES if est_post else None,
        instance=beneficiaire,
        utilisateur=requete.user,
    )

    if requete.method == "POST" and formulaire.is_valid():
        try:
            modifier_beneficiaire(
                requete.user, identifiant, **formulaire.cleaned_data
            )
        except RegleMetierViolee as erreur:
            formulaire.add_error(None, str(erreur))
            return render(
                requete,
                "beneficiaires/formulaire.html",
                {"formulaire": formulaire, "beneficiaire": beneficiaire, "doublons": []},
            )

        return redirect("beneficiaires:detail", identifiant=identifiant)

    return render(
        requete,
        "beneficiaires/formulaire.html",
        {"formulaire": formulaire, "beneficiaire": beneficiaire, "doublons": []},
    )
