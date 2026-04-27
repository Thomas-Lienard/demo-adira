"""
Generates synthetic French B2B sales data as Parquet files.
Creates files for two schemas:
  - demo_adira_raw  (cryptic ERP-style column names)
  - demo_adira_gold (clean French business names)
Also generates raw documents (transcriptions + tickets) as local JSON.

Usage: python scripts/generate_data.py
Output: data/parquet/demo_adira_gold/*.parquet
        data/parquet/demo_adira_raw/*.parquet
        data/documents/transcriptions/*.json
        data/documents/tickets/*.json
"""
import json
import os
import random
from datetime import date, timedelta

import pandas as pd

random.seed(42)

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
PARQUET_DIR = os.path.join(BASE_DIR, "data", "parquet")
GOLD_DIR = os.path.join(PARQUET_DIR, "demo_adira_gold")
RAW_DIR = os.path.join(PARQUET_DIR, "demo_adira_raw")
DOCS_DIR = os.path.join(BASE_DIR, "data", "documents")

# ============================================================
# Reference data
# ============================================================

REGIONS = [
    ("AURA", "Lyon", 1400000, 1450000, 1500000, 1400000),
    ("IDF", "Ile-de-France", 3200000, 3400000, 3500000, 3300000),
    ("PACA", "Provence-Alpes-Cote d'Azur", 680000, 710000, 730000, 700000),
    ("OCC", "Occitanie", 900000, 950000, 980000, 920000),
    ("GE", "Grand Est", 850000, 880000, 910000, 870000),
    ("HDF", "Hauts-de-France", 580000, 610000, 640000, 600000),
    ("NAQ", "Nouvelle-Aquitaine", 1100000, 1150000, 1200000, 1120000),
    ("BRE", "Bretagne", 860000, 900000, 930000, 880000),
]

COMMERCIAUX = [
    (1, "Marie Dubois", "AURA", "Sud", "2021-03-15"),
    (2, "Thomas Martin", "AURA", "Sud", "2020-06-01"),
    (3, "Sophie Laurent", "IDF", "Nord", "2019-09-01"),
    (4, "Pierre Moreau", "IDF", "Nord", "2020-01-15"),
    (5, "Julie Bernard", "IDF", "Nord", "2021-11-01"),
    (6, "Nicolas Petit", "PACA", "Sud", "2020-04-01"),
    (7, "Camille Durand", "PACA", "Sud", "2022-02-01"),
    (8, "Mathieu Robert", "OCC", "Sud", "2019-07-01"),
    (9, "Emilie Richard", "OCC", "Sud", "2021-08-15"),
    (10, "Antoine Leroy", "GE", "Nord", "2020-10-01"),
    (11, "Clara Simon", "GE", "Nord", "2022-05-01"),
    (12, "Julien Michel", "HDF", "Nord", "2020-03-01"),
    (13, "Laura Lefebvre", "HDF", "Nord", "2021-06-01"),
    (14, "Romain Garcia", "NAQ", "Sud", "2019-12-01"),
    (15, "Aurelie Thomas", "NAQ", "Sud", "2022-09-01"),
    (16, "Maxime Bertrand", "BRE", "Nord", "2020-07-01"),
    (17, "Chloe Roux", "BRE", "Nord", "2023-01-15"),
]

VILLES = {
    "AURA": ["Lyon", "Grenoble", "Saint-Etienne", "Clermont-Ferrand", "Annecy"],
    "IDF": ["Paris", "Boulogne-Billancourt", "Saint-Denis", "Nanterre", "Versailles"],
    "PACA": ["Marseille", "Nice", "Aix-en-Provence", "Toulon", "Avignon"],
    "OCC": ["Toulouse", "Montpellier", "Nimes", "Perpignan", "Beziers"],
    "GE": ["Strasbourg", "Metz", "Nancy", "Mulhouse", "Reims"],
    "HDF": ["Lille", "Amiens", "Roubaix", "Tourcoing", "Dunkerque"],
    "NAQ": ["Bordeaux", "Limoges", "Poitiers", "La Rochelle", "Pau"],
    "BRE": ["Rennes", "Brest", "Quimper", "Vannes", "Saint-Brieuc"],
}

SEGMENTS = ["PME", "ETI", "Grand Compte"]
SEGMENT_WEIGHTS = [0.60, 0.30, 0.10]

CATEGORIES_PRODUIT = ["Equipement industriel", "Fournitures bureau", "Services maintenance", "Logiciel", "Consommables"]
PRODUITS = []
for i in range(1, 51):
    cat = random.choice(CATEGORIES_PRODUIT)
    prix = round(random.uniform(50, 5000), 2)
    PRODUITS.append((i, f"SKU-{i:04d}", f"Produit {cat[:3]}-{i}", cat, "unite", prix, random.randint(1, 10), True))

NOMS_ENTREPRISES = [
    "Dupont Industries", "Metal Pro", "TechnoVision", "AgroServices", "BatiRenov",
    "LogiTrans", "MediLab", "EcoSolutions", "FoodExpress", "AutoParts Plus",
    "InnoTech", "GreenEnergy", "DataFlow", "AquaPure", "ElectroPro",
    "BioPharm", "ConstrucPlus", "TextiMode", "ChimioLab", "RoboTech",
    "SteelForge", "PackLogic", "AeroSpace", "MarineWorks", "TerraFirma",
    "DigitalWave", "SolarPeak", "PharmaVie", "MecaPrecision", "OptiVision",
]

CONCURRENTS = ["Acme Corp", "NovaTech", "ProVision", "AlphaServices", ""]

REGION_CODE_TO_NAME = {r[0]: r[1] for r in REGIONS}

# ============================================================
# Generate structured data
# ============================================================

def generate_clients(n=250):
    clients = []
    for i in range(1, n + 1):
        region = random.choices([r[0] for r in REGIONS], weights=[15, 25, 12, 10, 10, 10, 10, 8])[0]
        ville = random.choice(VILLES[region])
        seg = random.choices(SEGMENTS, weights=SEGMENT_WEIGHTS)[0]
        nom_base = random.choice(NOMS_ENTREPRISES)
        nom = f"{nom_base} {ville[:3]}-{i}"
        statut = random.choices(["actif", "inactif"], weights=[0.9, 0.1])[0]
        dt = date(2020, 1, 1) + timedelta(days=random.randint(0, 1500))
        clients.append((i, nom, ville, region, seg, statut, dt.isoformat()))
    return clients


def generate_orders_and_lines(clients, commerciaux):
    orders = []
    lines = []
    order_id = 1

    region_commerciaux = {}
    for c in commerciaux:
        region_commerciaux.setdefault(c[2], []).append(c[0])

    months = []
    for yr in [2024, 2025]:
        end_month = 12 if yr == 2024 else 9
        for mo in range(1, end_month + 1):
            months.append((yr, mo))

    for yr, mo in months:
        q = (mo - 1) // 3 + 1
        is_q3_2025 = (yr == 2025 and q == 3)

        for cl in clients:
            cl_id, _, _, region, seg, statut, _ = cl
            if statut == "inactif":
                continue

            base_prob = 0.15
            if seg == "ETI":
                base_prob = 0.25
            elif seg == "Grand Compte":
                base_prob = 0.40

            if is_q3_2025 and region == "AURA":
                if seg == "PME":
                    base_prob *= 0.35
                else:
                    base_prob *= 0.65

            if random.random() > base_prob:
                continue

            avail = region_commerciaux.get(region, [1])
            com_id = random.choice(avail)

            max_day = 28 if mo == 2 else 30 if mo in [4, 6, 9, 11] else 31
            order_date = date(yr, mo, 1) + timedelta(days=random.randint(0, max_day - 1))
            statut_ord = random.choices(["validee", "annulee", "en_cours"], weights=[0.85, 0.05, 0.10])[0]

            orders.append((order_id, cl_id, com_id, order_date.isoformat(), statut_ord, "EUR", "30 jours"))

            n_lines = random.randint(1, 5)
            for ln in range(1, n_lines + 1):
                prod = random.choice(PRODUITS)
                qty = random.randint(1, 20)
                prix = prod[5] * random.uniform(0.8, 1.2)
                remise = random.choice([0, 0, 0, 5, 10, 15])
                tva = 20.0
                montant = round(qty * prix * (1 - remise / 100), 2)
                lines.append((order_id, ln, prod[0], qty, round(prix, 2), remise, tva, montant))

            order_id += 1

    return orders, lines


def generate_invoices_and_payments(orders, lines):
    invoices = []
    payments = []
    inv_id = 1
    pmt_id = 1

    order_totals = {}
    for ln in lines:
        oid = ln[0]
        order_totals[oid] = order_totals.get(oid, 0) + ln[7]

    for o in orders:
        oid, _, _, ord_date, statut, _, _ = o
        if statut == "annulee":
            continue
        total = round(order_totals.get(oid, 0), 2)
        inv_date = date.fromisoformat(ord_date) + timedelta(days=random.randint(1, 5))
        due_date = inv_date + timedelta(days=30)
        is_paid = random.random() < 0.82
        invoices.append((inv_id, oid, inv_date.isoformat(), due_date.isoformat(), "emise", total, "EUR", is_paid))

        if is_paid:
            pay_date = inv_date + timedelta(days=random.randint(10, 60))
            payments.append((pmt_id, inv_id, pay_date.isoformat(), total, random.choice(["virement", "cheque", "prelevement"]), "recu"))
            pmt_id += 1

        inv_id += 1

    return invoices, payments


# ============================================================
# Generate extracted unstructured data
# ============================================================

def generate_appels(commerciaux, clients, n=50):
    appels = []
    aura_clients = [c for c in clients if c[3] == "AURA"]
    other_clients = [c for c in clients if c[3] != "AURA"]
    aura_coms = [c for c in commerciaux if c[2] == "AURA"]

    for i in range(1, n + 1):
        if i <= 30:
            com = random.choice(aura_coms)
            cl = random.choice(aura_clients)
            region = REGION_CODE_TO_NAME["AURA"]
            is_q3 = i <= 20
            if is_q3:
                d = date(2025, 7, 1) + timedelta(days=random.randint(0, 89))
                concurrent = random.choices(
                    ["Acme Corp", "NovaTech", "ProVision", ""],
                    weights=[55, 10, 5, 30]
                )[0]
                sentiment = random.choices(["negatif", "neutre", "positif"], weights=[55, 30, 15])[0]
            else:
                d = date(2025, 4, 1) + timedelta(days=random.randint(0, 89))
                concurrent = random.choices(
                    ["Acme Corp", "NovaTech", ""],
                    weights=[10, 5, 85]
                )[0]
                sentiment = random.choices(["negatif", "neutre", "positif"], weights=[20, 40, 40])[0]
        else:
            com = random.choice(commerciaux)
            cl = random.choice(other_clients)
            region = REGION_CODE_TO_NAME[cl[3]]
            d = date(2025, 1, 1) + timedelta(days=random.randint(0, 270))
            concurrent = random.choices(["Acme Corp", "NovaTech", ""], weights=[10, 5, 85])[0]
            sentiment = random.choices(["negatif", "neutre", "positif"], weights=[15, 35, 50])[0]

        objections = {
            "negatif": ["pricing trop eleve vs Acme", "delais de livraison inacceptables", "qualite en baisse", "concurrent propose mieux"],
            "neutre": ["en reflexion", "demande de devis comparatif", "budget pas encore valide"],
            "positif": ["satisfait du produit", "pret a renouveler", "interesse par upsell"],
        }
        objection = random.choice(objections[sentiment])
        signal = sentiment == "positif" and random.random() > 0.4
        etapes = ["envoyer nouvelle proposition", "planifier demo", "relancer dans 2 semaines", "escalader au manager", "cloture positive"]
        etape = random.choice(etapes)

        resume_templates = {
            "negatif": f"Le client {cl[1]} compare activement avec {concurrent or 'la concurrence'}. Objection principale : {objection}.",
            "neutre": f"Echange exploratoire avec {cl[1]}. Le client est en phase de reflexion. {objection}.",
            "positif": f"Bon echange avec {cl[1]}. Le client est satisfait et montre des signaux d'achat positifs.",
        }

        appels.append((
            i, d.isoformat(), com[1], cl[1], region,
            random.randint(10, 55), concurrent, objection, sentiment,
            signal, etape, resume_templates[sentiment]
        ))

    return appels


def generate_tickets(clients, n=50):
    tickets = []
    aura_clients = [c for c in clients if c[3] == "AURA"]
    other_clients = [c for c in clients if c[3] != "AURA"]

    categories = ["retard_livraison", "qualite_produit", "facturation", "support_technique"]

    for i in range(1, n + 1):
        if i <= 25:
            cl = random.choice(aura_clients)
            region = REGION_CODE_TO_NAME["AURA"]
            if i <= 18:
                d = date(2025, 6, 1) + timedelta(days=random.randint(0, 120))
                cat = random.choices(categories, weights=[55, 20, 15, 10])[0]
                severite = random.choices(["critique", "haute", "moyenne", "basse"], weights=[20, 40, 30, 10])[0]
            else:
                d = date(2025, 1, 1) + timedelta(days=random.randint(0, 150))
                cat = random.choices(categories, weights=[25, 25, 25, 25])[0]
                severite = random.choices(["critique", "haute", "moyenne", "basse"], weights=[5, 20, 45, 30])[0]
        else:
            cl = random.choice(other_clients)
            region = REGION_CODE_TO_NAME[cl[3]]
            d = date(2025, 1, 1) + timedelta(days=random.randint(0, 270))
            cat = random.choices(categories, weights=[25, 25, 25, 25])[0]
            severite = random.choices(["critique", "haute", "moyenne", "basse"], weights=[5, 15, 50, 30])[0]

        prod = random.choice(PRODUITS)
        delai = random.randint(1, 15) if random.random() < 0.7 else None

        sentiments = {
            "critique": "tres mecontent",
            "haute": "mecontent",
            "moyenne": "neutre",
            "basse": "satisfait de la resolution",
        }

        resume_templates = {
            "retard_livraison": f"Commande livree avec {random.randint(5, 20)} jours de retard. Le client {cl[1]} signale un impact sur sa production.",
            "qualite_produit": f"Le client {cl[1]} signale un defaut sur {prod[2]}. Demande de remplacement ou avoir.",
            "facturation": f"Erreur sur la facture du client {cl[1]}. Montant incorrect, demande de regularisation.",
            "support_technique": f"Le client {cl[1]} rencontre un probleme technique avec {prod[2]}. Assistance demandee.",
        }

        tickets.append((
            i, d.isoformat(), cl[1], region, cat, prod[2],
            severite, delai, sentiments[severite], resume_templates[cat]
        ))

    return tickets


# ============================================================
# Raw documents (for before/after visual)
# ============================================================

def generate_raw_transcriptions(appels):
    docs = []
    for appel in appels[:8]:
        _, dt, commercial, client_name, region, duree, concurrent, objection, sentiment, _, etape, resume = appel
        doc = {
            "id": f"TR-{appel[0]:04d}",
            "type": "transcription",
            "metadata": {"date": dt, "commercial": commercial, "client": client_name, "region": region},
            "raw_text": f"""TRANSCRIPTION D'APPEL COMMERCIAL
=================================
Date : {dt}
Commercial : {commercial}
Client : {client_name}
Region : {region}
Duree : {duree} minutes

--- DEBUT DE TRANSCRIPTION ---

{commercial} : Bonjour, c'est {commercial} de chez nous. Je vous appelle suite a notre dernier echange
concernant le renouvellement de votre contrat annuel. Comment allez-vous aujourd'hui ?

{client_name} : Bonjour {commercial.split()[0]}. Ecoutez, justement je voulais vous en parler.
On a recu une proposition de {concurrent or 'un de vos concurrents'} la semaine derniere et franchement,
leurs conditions sont plus interessantes que les votres.

{commercial} : Je comprends. Pouvez-vous me donner plus de details sur ce qu'ils proposent ?

{client_name} : Alors principalement, {objection}. Et puis il y a aussi le sujet des delais.
On a eu plusieurs retards ces derniers mois, et ca nous pose de vrais problemes en production.
Mon directeur des achats commence a perdre patience.

{commercial} : Je comprends votre frustration et je prends note de ces points. Concernant les delais,
nous avons mis en place un nouveau process de suivi logistique depuis le mois dernier qui devrait
ameliorer la situation. Pour les conditions tarifaires, je vais regarder ce qu'on peut faire.
Est-ce que vous seriez disponible pour un rendez-vous la semaine prochaine ?

{client_name} : Il faut que ce soit rapide parce qu'on a prevu de prendre une decision d'ici fin du mois.
Le budget est deja arbitre, et si on ne voit pas d'amelioration concrete de votre cote, on partira
chez {concurrent or 'la concurrence'}. C'est pas de gaite de coeur parce qu'on travaille ensemble depuis
5 ans, mais la realite economique est ce qu'elle est.

{commercial} : Je comprends parfaitement. Je vous envoie une proposition revisee d'ici jeudi, et on
programme un point la semaine prochaine pour en discuter. Est-ce que mardi vous conviendrait ?

{client_name} : Mardi apres-midi ca peut le faire. Mais venez avec du concret, pas juste un PowerPoint.

{commercial} : Entendu. Merci pour votre franchise, {client_name.split()[0]}. A mardi.

--- FIN DE TRANSCRIPTION ---

Notes post-appel ({commercial}) :
- Client en phase de comparaison active avec {concurrent or 'concurrent inconnu'}
- Objection principale : {objection}
- Risque de perte du compte : {'ELEVE' if sentiment == 'negatif' else 'MOYEN' if sentiment == 'neutre' else 'FAIBLE'}
- Action : {etape}
- Prochaine etape prevue : semaine prochaine

Contexte supplementaire :
Ce client represente un CA annuel d'environ {random.randint(80, 350)}K EUR. La perte de ce compte
aurait un impact significatif sur les objectifs de la region {region}. Le commercial note que
le ton du client s'est durci par rapport aux echanges precedents. La pression concurrentielle
sur le segment {'PME' if random.random() < 0.6 else 'ETI'} dans la region {region} s'est
intensifiee depuis le debut de l'annee, en particulier depuis que {concurrent or 'un concurrent'}
a lance sa nouvelle offre {"agressivement positionnee en prix" if concurrent == "Acme Corp" else "innovante"}.
""",
            "extracted_fields": {
                "date_appel": dt,
                "commercial": commercial,
                "client": client_name,
                "duree_minutes": duree,
                "concurrent_cite": concurrent,
                "objection_principale": objection,
                "sentiment": sentiment,
                "signal_achat": appel[9],
                "prochaine_etape": etape,
                "resume": resume,
            }
        }
        docs.append(doc)
    return docs


def generate_raw_tickets(tickets_data):
    docs = []
    for ticket in tickets_data[:8]:
        _, dt, client_name, region, cat, produit, severite, delai, sent, resume = ticket
        doc = {
            "id": f"TK-{ticket[0]:04d}",
            "type": "ticket",
            "metadata": {"date": dt, "client": client_name, "region": region, "categorie": cat},
            "raw_text": f"""TICKET SERVICE CLIENT #{ticket[0]:04d}
=====================================
Date d'ouverture : {dt}
Client : {client_name}
Region : {region}
Categorie : {cat}
Severite : {severite}
Produit concerne : {produit}

--- HISTORIQUE DU TICKET ---

[{dt} 09:15] Client ({client_name}) :
Bonjour, je vous contacte car nous avons un probleme {
    "urgent avec notre derniere livraison. La commande reference CMD-" + str(random.randint(10000, 99999)) + " devait etre livree il y a " + str(random.randint(5, 20)) + " jours et nous n'avons toujours rien recu. C'est la troisieme fois ce trimestre que ca arrive. Notre chaine de production est impactee et on a du retarder deux commandes client a cause de ca. C'est inacceptable."
    if cat == "retard_livraison" else
    "avec le produit " + produit + " que nous avons recu. Apres inspection, plusieurs unites presentent des defauts de fabrication. Les tolerances ne sont pas respectees et nos equipes qualite ont rejete le lot. On ne peut pas utiliser ca en production."
    if cat == "qualite_produit" else
    "sur notre derniere facture. Le montant facture ne correspond pas au bon de commande. Il y a un ecart de " + str(random.randint(500, 5000)) + " EUR que nous ne comprenons pas. Merci de regulariser rapidement."
    if cat == "facturation" else
    "technique avec " + produit + ". L'equipement ne fonctionne plus correctement depuis la derniere mise a jour. Nos techniciens ont essaye plusieurs procedures de depannage sans succes. On a besoin d'une intervention rapide."
}

[{dt} 10:30] Support (Equipe SAV) :
Bonjour, nous avons bien recu votre demande et nous la traitons en priorite {severite}.
{
    "Nous avons contacte notre service logistique pour localiser votre colis et accelerer la livraison. Un point de situation vous sera communique sous 24h."
    if cat == "retard_livraison" else
    "Nous allons organiser un retour du lot defectueux et lancer un remplacement en priorite. Un responsable qualite vous contactera demain."
    if cat == "qualite_produit" else
    "Nous avons escalade votre demande au service facturation. Une facture corrective sera emise sous 48h."
    if cat == "facturation" else
    "Nous planifions une intervention technique sur site dans les 48h. En attendant, veuillez debrancher l'equipement pour eviter tout dommage supplementaire."
}

[{(date.fromisoformat(dt) + timedelta(days=random.randint(1, 5))).isoformat()} 14:22] Client ({client_name}) :
{
    "Merci pour le retour mais ce n'est pas suffisant. J'ai besoin de garanties que ca ne se reproduira plus. On evalue serieusement des alternatives fournisseur."
    if severite in ["critique", "haute"] else
    "OK merci pour la prise en charge rapide. J'attends votre retour."
}

{"[" + (date.fromisoformat(dt) + timedelta(days=delai)).isoformat() + " 16:00] Support (Equipe SAV) : Ticket resolu. " + resume if delai else "[En cours] Ticket toujours ouvert."}

--- FIN DU TICKET ---

Metriques internes :
- Temps de premiere reponse : 1h15
- Temps de resolution : {str(delai) + ' jours' if delai else 'en cours'}
- Satisfaction client post-resolution : {sent}
- Escalade manager : {'oui' if severite in ['critique', 'haute'] else 'non'}
- Impact business estime : {random.choice(['faible', 'moyen', 'eleve', 'critique'])}
""",
            "extracted_fields": {
                "date_creation": dt,
                "client": client_name,
                "categorie_probleme": cat,
                "produit_concerne": produit,
                "severite": severite,
                "delai_resolution_jours": delai,
                "sentiment_client": sent,
                "resume": resume,
            }
        }
        docs.append(doc)
    return docs


# ============================================================
# Parquet writers
# ============================================================

def write_parquet(df, directory, filename):
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, filename)
    df.to_parquet(path, engine="pyarrow", index=False)
    print(f"  {path} ({len(df)} rows)")


def save_gold(clients, commerciaux_list, orders, lines, invoices, payments, appels, tickets_data):
    print("\nWriting GOLD parquet files...")

    # Regions
    df = pd.DataFrame(REGIONS, columns=["region_code", "nom_region", "objectif_q1", "objectif_q2", "objectif_q3", "objectif_q4"])
    df[["objectif_q1", "objectif_q2", "objectif_q3", "objectif_q4"]] = df[["objectif_q1", "objectif_q2", "objectif_q3", "objectif_q4"]].astype(float)
    write_parquet(df, GOLD_DIR, "regions.parquet")

    # Commerciaux
    df = pd.DataFrame(commerciaux_list, columns=["commercial_id", "nom_commercial", "region_code", "equipe", "date_embauche"])
    df["date_embauche"] = pd.to_datetime(df["date_embauche"]).dt.date
    write_parquet(df, GOLD_DIR, "commerciaux.parquet")

    # Clients
    df = pd.DataFrame(clients, columns=["client_id", "nom_client", "ville", "region_code", "segment", "statut", "date_creation"])
    df["date_creation"] = pd.to_datetime(df["date_creation"]).dt.date
    write_parquet(df, GOLD_DIR, "clients.parquet")

    # Commandes
    df = pd.DataFrame(orders, columns=["commande_id", "client_id", "commercial_id", "date_commande", "statut", "devise", "conditions_paiement"])
    df["date_commande"] = pd.to_datetime(df["date_commande"]).dt.date
    write_parquet(df, GOLD_DIR, "commandes.parquet")

    # Lignes commande
    df = pd.DataFrame(lines, columns=["commande_id", "numero_ligne", "produit_id", "quantite", "prix_unitaire", "remise_pct", "taux_tva", "montant_ligne"])
    write_parquet(df, GOLD_DIR, "lignes_commande.parquet")

    # Factures
    df = pd.DataFrame(invoices, columns=["facture_id", "commande_id", "date_facture", "date_echeance", "statut", "montant_total", "devise", "est_payee"])
    df["date_facture"] = pd.to_datetime(df["date_facture"]).dt.date
    df["date_echeance"] = pd.to_datetime(df["date_echeance"]).dt.date
    write_parquet(df, GOLD_DIR, "factures.parquet")

    # Paiements
    df = pd.DataFrame(payments, columns=["paiement_id", "facture_id", "date_paiement", "montant", "methode", "statut"])
    df["date_paiement"] = pd.to_datetime(df["date_paiement"]).dt.date
    write_parquet(df, GOLD_DIR, "paiements.parquet")

    # Produits
    df = pd.DataFrame(PRODUITS, columns=["produit_id", "sku", "nom_produit", "categorie", "unite", "prix_catalogue", "fournisseur_id", "est_actif"])
    write_parquet(df, GOLD_DIR, "produits.parquet")

    # Appels extraits
    df = pd.DataFrame(appels, columns=["appel_id", "date_appel", "commercial", "client", "region",
                                        "duree_minutes", "concurrent_cite", "objection_principale",
                                        "sentiment", "signal_achat", "prochaine_etape", "resume"])
    df["date_appel"] = pd.to_datetime(df["date_appel"]).dt.date
    write_parquet(df, GOLD_DIR, "appels_commerciaux_extraits.parquet")

    # Tickets extraits
    df = pd.DataFrame(tickets_data, columns=["ticket_id", "date_creation", "client", "region",
                                              "categorie_probleme", "produit_concerne", "severite",
                                              "delai_resolution_jours", "sentiment_client", "resume"])
    df["date_creation"] = pd.to_datetime(df["date_creation"]).dt.date
    write_parquet(df, GOLD_DIR, "tickets_service_client_extraits.parquet")


def save_raw(clients, commerciaux_list, orders, lines, invoices, payments):
    print("\nWriting RAW parquet files...")

    seg_map = {"PME": "P", "ETI": "E", "Grand Compte": "G"}
    sts_map = {"actif": "A", "inactif": "I"}
    sts_ord_map = {"validee": "V", "annulee": "X", "en_cours": "P"}
    mth_map = {"virement": "VIR", "cheque": "CHQ", "prelevement": "PRV"}

    # tbl_rgn_mstr — keep full administrative names in raw schema
    RAW_REGION_NAMES = {"Lyon": "Auvergne-Rhone-Alpes"}
    df = pd.DataFrame(REGIONS, columns=["rgn_cd", "rgn_nm", "tgt_q1_amt", "tgt_q2_amt", "tgt_q3_amt", "tgt_q4_amt"])
    df["rgn_nm"] = df["rgn_nm"].replace(RAW_REGION_NAMES)
    df[["tgt_q1_amt", "tgt_q2_amt", "tgt_q3_amt", "tgt_q4_amt"]] = df[["tgt_q1_amt", "tgt_q2_amt", "tgt_q3_amt", "tgt_q4_amt"]].astype(float)
    write_parquet(df, RAW_DIR, "tbl_rgn_mstr.parquet")

    # tbl_sl_emp
    df = pd.DataFrame(commerciaux_list, columns=["sl_emp_id", "emp_nm", "rgn_cd", "tm_cd", "hr_dt"])
    df["hr_dt"] = pd.to_datetime(df["hr_dt"]).dt.date
    write_parquet(df, RAW_DIR, "tbl_sl_emp.parquet")

    # tbl_cst_acct
    raw_clients = [(c[0], c[1], c[2], c[3], seg_map.get(c[4], c[4]), sts_map.get(c[5], c[5]), c[6]) for c in clients]
    df = pd.DataFrame(raw_clients, columns=["cst_id", "cst_nm", "cst_cty", "rgn_cd", "seg_cd", "sts_cd", "cr_dt"])
    df["cr_dt"] = pd.to_datetime(df["cr_dt"]).dt.date
    write_parquet(df, RAW_DIR, "tbl_cst_acct.parquet")

    # tbl_ord_hdr
    raw_orders = [(o[0], o[1], o[2], o[3], sts_ord_map.get(o[4], o[4]), o[5], o[6]) for o in orders]
    df = pd.DataFrame(raw_orders, columns=["ord_id", "cst_id", "sl_emp_id", "ord_dt", "sts_cd", "ccy_cd", "pmt_trm"])
    df["ord_dt"] = pd.to_datetime(df["ord_dt"]).dt.date
    write_parquet(df, RAW_DIR, "tbl_ord_hdr.parquet")

    # tbl_ord_ln
    df = pd.DataFrame(lines, columns=["ord_id", "ln_no", "itm_id", "qty", "un_prc", "disc_pct", "tx_rt", "ln_amt"])
    write_parquet(df, RAW_DIR, "tbl_ord_ln.parquet")

    # tbl_inv_hdr
    df = pd.DataFrame(invoices, columns=["inv_id", "ord_id", "inv_dt", "due_dt", "sts_cd", "ttl_amt", "ccy_cd", "is_pd"])
    df["inv_dt"] = pd.to_datetime(df["inv_dt"]).dt.date
    df["due_dt"] = pd.to_datetime(df["due_dt"]).dt.date
    write_parquet(df, RAW_DIR, "tbl_inv_hdr.parquet")

    # tbl_pmt
    raw_payments = [(p[0], p[1], p[2], p[3], mth_map.get(p[4], p[4]), p[5]) for p in payments]
    df = pd.DataFrame(raw_payments, columns=["pmt_id", "inv_id", "pmt_dt", "amt", "mth_cd", "sts_cd"])
    df["pmt_dt"] = pd.to_datetime(df["pmt_dt"]).dt.date
    write_parquet(df, RAW_DIR, "tbl_pmt.parquet")

    # tbl_itm_mstr
    df = pd.DataFrame(PRODUITS, columns=["itm_id", "sku", "prd_nm", "cat_cd", "uom", "lst_prc", "sup_id", "is_act"])
    write_parquet(df, RAW_DIR, "tbl_itm_mstr.parquet")


# ============================================================
# Main
# ============================================================

def main():
    print("=== Generating synthetic data ===\n")

    print("1. Generating base data...")
    clients = generate_clients(250)
    orders, lines = generate_orders_and_lines(clients, COMMERCIAUX)
    invoices, payments = generate_invoices_and_payments(orders, lines)
    appels = generate_appels(COMMERCIAUX, clients, 50)
    tickets_data = generate_tickets(clients, 50)

    print(f"   Clients: {len(clients)}")
    print(f"   Orders: {len(orders)}, Lines: {len(lines)}")
    print(f"   Invoices: {len(invoices)}, Payments: {len(payments)}")
    print(f"   Appels extraits: {len(appels)}")
    print(f"   Tickets extraits: {len(tickets_data)}")

    print("\n2. Writing Parquet files...")
    save_gold(clients, COMMERCIAUX, orders, lines, invoices, payments, appels, tickets_data)
    save_raw(clients, COMMERCIAUX, orders, lines, invoices, payments)

    print("\n3. Generating raw documents...")
    os.makedirs(os.path.join(DOCS_DIR, "transcriptions"), exist_ok=True)
    os.makedirs(os.path.join(DOCS_DIR, "tickets"), exist_ok=True)

    transcription_docs = generate_raw_transcriptions(appels)
    for doc in transcription_docs:
        path = os.path.join(DOCS_DIR, "transcriptions", f"{doc['id']}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
    print(f"   Generated {len(transcription_docs)} transcriptions")

    ticket_docs = generate_raw_tickets(tickets_data)
    for doc in ticket_docs:
        path = os.path.join(DOCS_DIR, "tickets", f"{doc['id']}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
    print(f"   Generated {len(ticket_docs)} tickets")

    print("\n=== Done! ===")
    print(f"\nParquet files: {PARQUET_DIR}")
    print(f"Documents:     {DOCS_DIR}")


if __name__ == "__main__":
    main()
