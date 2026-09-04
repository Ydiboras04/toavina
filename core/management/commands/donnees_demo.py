"""Charge un jeu de données de démonstration.

Sans référentiel géographique, aucun bénéficiaire ne peut être créé : la
fiche exige un village, qui exige une commune, un district, une région et un
pays. Saisir tout cela à la main dans l'administration avant de pouvoir
essayer quoi que ce soit décourage — d'où cette commande.

Elle sert aussi à recharger un jeu propre avant une démonstration.

La commande est idempotente : la relancer ne crée pas de doublons, elle
complète ce qui manque. Les mots de passe sont volontairement simples et
écrits en clair ci-dessous : ce sont des comptes de démonstration, destinés
à une base locale jetable. Ne jamais lancer cette commande sur une base de
production.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.beneficiaires.models import Beneficiaire, Sexe, SituationFamiliale
from apps.campagnes.models import CampagneAide, DistributionAide
from apps.geographie.models import Commune, District, Pays, Region, Village
from apps.projets.models import EtatProjet, Projet, TypeAction
from core.models import EtatCampagne
from core.roles import Role

MOT_DE_PASSE_DEMO = "demo12345"

# Les douze types d'action prévus par le cahier des charges de l'ONG.
TYPES_ACTION = [
    "Distribution alimentaire",
    "Distribution de vêtements",
    "Kurban",
    "Forage d'eau",
    "Construction de mosquées",
    "Construction d'écoles",
    "Bourses d'étude",
    "Parrainage d'orphelins",
    "Urgences humanitaires",
    "Santé",
    "Éducation",
    "Développement rural",
]

# Un compte par rôle, pour pouvoir constater de visu ce que chacun voit.
COMPTES = [
    ("admin", Role.SUPER_ADMIN, "Sitraka", "Rakotondrabe"),
    ("president", Role.PRESIDENT, "Hery", "Randrianarisoa"),
    ("coordo", Role.COORDINATEUR, "Miora", "Rasoanaivo"),
    ("comptable", Role.COMPTABLE, "Tahina", "Andrianina"),
    ("chefprojet", Role.RESPONSABLE_PROJET, "Fanja", "Ravelojaona"),
    ("volontaire", Role.VOLONTAIRE, "Naina", "Rakotoson"),
]

VILLAGES = ["Betania", "Ampasy", "Andranomena", "Antanandava"]

BENEFICIAIRES = [
    ("Rakoto", "Jean", Sexe.MASCULIN, "1985-04-12", 4, SituationFamiliale.MARIE),
    ("Rabe", "Paul", Sexe.MASCULIN, "1978-11-03", 6, SituationFamiliale.MARIE),
    ("Razafy", "Vola", Sexe.FEMININ, "1990-07-21", 2, SituationFamiliale.VEUF),
    ("Randria", "Soa", Sexe.FEMININ, "1996-02-14", 1, SituationFamiliale.CELIBATAIRE),
    ("Rasoa", "Hanta", Sexe.FEMININ, "1982-09-30", 5, SituationFamiliale.MARIE),
]


class Command(BaseCommand):
    help = (
        "Charge un jeu de données de démonstration : référentiel géographique, "
        "comptes par rôle, projet, campagne, bénéficiaires et distributions."
    )

    def add_arguments(self, analyseur):
        analyseur.add_argument(
            "--vider",
            action="store_true",
            help=(
                "Supprime les données de démonstration existantes avant de les "
                "recréer. À n'utiliser que sur une base locale."
            ),
        )

    def handle(self, *args, **options):
        from django.conf import settings

        if not settings.DEBUG:
            raise CommandError(
                "Cette commande est réservée au développement : elle crée des "
                "comptes dont le mot de passe est public. Refus d'exécution "
                "avec DEBUG désactivé."
            )

        if options["vider"]:
            self._vider()

        pays = self._geographie()
        types = self._types_action()
        comptes = self._comptes()
        projet = self._projet(types, comptes)
        campagne = self._campagne(projet, comptes)
        beneficiaires = self._beneficiaires()
        self._distributions(campagne, beneficiaires, comptes)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Données de démonstration chargées."))
        self.stdout.write("")
        self.stdout.write("Comptes disponibles — mot de passe : " + MOT_DE_PASSE_DEMO)
        for identifiant, role, _, _ in COMPTES:
            self.stdout.write(f"  {identifiant:<12} {Role(role).label}")
        self.stdout.write("")
        self.stdout.write(
            "Connectez-vous sur /comptes/login/ puis ouvrez /beneficiaires/ "
            "ou /campagnes/distributions/."
        )
        self.stdout.write(
            "Comparez ce que voient « coordo » et « volontaire » : le second "
            "ne voit que les distributions qu'il a lui-même saisies."
        )

    # --- étapes ----------------------------------------------------------

    def _vider(self):
        DistributionAide.tous.all().delete()
        CampagneAide.tous.all().delete()
        Projet.tous.all().delete()
        Beneficiaire.tous.all().delete()
        Village.objects.all().delete()
        Commune.objects.all().delete()
        District.objects.all().delete()
        Region.objects.all().delete()
        Pays.objects.all().delete()
        TypeAction.objects.all().delete()
        get_user_model().objects.filter(
            username__in=[identifiant for identifiant, _, _, _ in COMPTES]
        ).delete()
        self.stdout.write("Données de démonstration supprimées.")

    def _geographie(self):
        pays, _ = Pays.objects.get_or_create(
            libelle="Madagascar", defaults={"code_iso": "MDG"}
        )
        region, _ = Region.objects.get_or_create(libelle="Menabe", pays=pays)
        district, _ = District.objects.get_or_create(
            libelle="Morondava", region=region
        )
        commune, _ = Commune.objects.get_or_create(
            libelle="Analaiva", district=district
        )
        for libelle in VILLAGES:
            Village.objects.get_or_create(libelle=libelle, commune=commune)
        self.stdout.write(f"Géographie : {Village.objects.count()} villages.")
        return pays

    def _types_action(self):
        types = {}
        for libelle in TYPES_ACTION:
            types[libelle], _ = TypeAction.objects.get_or_create(libelle=libelle)
        self.stdout.write(f"Types d'action : {len(types)}.")
        return types

    def _comptes(self):
        Utilisateur = get_user_model()
        comptes = {}
        for identifiant, role, prenom, nom in COMPTES:
            compte = Utilisateur.objects.filter(username=identifiant).first()
            if compte is None:
                if role == Role.SUPER_ADMIN:
                    compte = Utilisateur.objects.create_superuser(
                        username=identifiant,
                        password=MOT_DE_PASSE_DEMO,
                        email=f"{identifiant}@effm.mg",
                    )
                else:
                    compte = Utilisateur.objects.create_user(
                        username=identifiant,
                        password=MOT_DE_PASSE_DEMO,
                        email=f"{identifiant}@effm.mg",
                        role=role,
                    )
                compte.first_name = prenom
                compte.last_name = nom
                compte.save()
            comptes[role] = compte
        self.stdout.write(f"Comptes : {len(comptes)}.")
        return comptes

    def _projet(self, types, comptes):
        projet, _ = Projet.objects.get_or_create(
            code="PROJ-2026-001",
            defaults={
                "titre": "Distribution alimentaire dans le Menabe",
                "description": (
                    "Distribution de colis alimentaires aux familles du "
                    "district de Morondava pendant le mois de Ramadan."
                ),
                "budget_prevu": "15000000.00",
                "budget_consomme": "2500000.00",
                "date_debut": "2026-01-15",
                "date_fin": "2026-12-31",
                "etat": EtatProjet.EN_COURS,
                "type_action": types["Distribution alimentaire"],
                "responsable": comptes[Role.RESPONSABLE_PROJET],
                "region": Region.objects.get(libelle="Menabe"),
            },
        )
        self.stdout.write(f"Projet : {projet.code}.")
        return projet

    def _campagne(self, projet, comptes):
        campagne, _ = CampagneAide.objects.get_or_create(
            code="RAM-2026",
            defaults={
                "libelle": "Ramadan",
                "annee": 2026,
                "budget": "5000000.00",
                "date_debut": "2026-02-18",
                "date_fin": "2026-03-19",
                "etat": EtatCampagne.EN_COURS,
                "projet": projet,
                "responsable": comptes[Role.COORDINATEUR],
            },
        )
        self.stdout.write(f"Campagne : {campagne}.")
        return campagne

    def _beneficiaires(self):
        villages = list(Village.objects.order_by("libelle"))
        crees = []
        for index, (nom, prenom, sexe, naissance, enfants, situation) in enumerate(
            BENEFICIAIRES
        ):
            beneficiaire, _ = Beneficiaire.objects.get_or_create(
                nom=nom,
                prenom=prenom,
                village=villages[index % len(villages)],
                defaults={
                    "sexe": sexe,
                    "date_naissance": naissance,
                    "nombre_enfants": enfants,
                    "situation_familiale": situation,
                    "profession": "Agriculteur",
                    "numero_cin": f"1012345678{index:02d}",
                },
            )
            crees.append(beneficiaire)
        self.stdout.write(f"Bénéficiaires : {len(crees)}.")
        return crees

    def _distributions(self, campagne, beneficiaires, comptes):
        # Seuls les trois premiers sont servis : les deux derniers restent
        # disponibles pour essayer une saisie depuis l'interface.
        nombre = 0
        for beneficiaire in beneficiaires[:3]:
            _, cree = DistributionAide.objects.get_or_create(
                beneficiaire=beneficiaire,
                campagne=campagne,
                defaults={
                    "village": beneficiaire.village,
                    "date_distribution": "2026-02-20",
                    "quantite": 1,
                    "unite": "colis",
                    "saisie_par": comptes[Role.VOLONTAIRE],
                },
            )
            nombre += int(cree)
        self.stdout.write(
            f"Distributions : {DistributionAide.objects.count()} "
            f"({nombre} créées à l'instant)."
        )
