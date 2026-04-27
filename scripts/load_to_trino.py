"""
Loads Parquet files into Trino Iceberg tables.
Reads from data/parquet/demo_adira_gold/ and data/parquet/demo_adira_raw/.

Usage: python scripts/load_to_trino.py [--gold] [--raw] [--drop]
  --gold  Load only gold schema
  --raw   Load only raw schema
  --drop  Drop existing tables before loading
  No flags = load both schemas, skip tables that already have data
"""
import os
import sys
import time

import pandas as pd
from trino.dbapi import connect

TRINO_HOST = "trino.thelio.app"
TRINO_PORT = 443
TRINO_USER = "thomas.lienard"
CATALOG = "iceberg"
SCHEMA_RAW = "demo_adira_raw"
SCHEMA_GOLD = "demo_adira_gold"

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
PARQUET_DIR = os.path.join(BASE_DIR, "data", "parquet")
GOLD_DIR = os.path.join(PARQUET_DIR, "demo_adira_gold")
RAW_DIR = os.path.join(PARQUET_DIR, "demo_adira_raw")

GOLD_TABLES = {
    "regions": {
        "region_code": "VARCHAR", "nom_region": "VARCHAR",
        "objectif_q1": "DOUBLE", "objectif_q2": "DOUBLE", "objectif_q3": "DOUBLE", "objectif_q4": "DOUBLE",
    },
    "commerciaux": {
        "commercial_id": "INTEGER", "nom_commercial": "VARCHAR", "region_code": "VARCHAR",
        "equipe": "VARCHAR", "date_embauche": "DATE",
    },
    "clients": {
        "client_id": "INTEGER", "nom_client": "VARCHAR", "ville": "VARCHAR", "region_code": "VARCHAR",
        "segment": "VARCHAR", "statut": "VARCHAR", "date_creation": "DATE",
    },
    "commandes": {
        "commande_id": "INTEGER", "client_id": "INTEGER", "commercial_id": "INTEGER",
        "date_commande": "DATE", "statut": "VARCHAR", "devise": "VARCHAR", "conditions_paiement": "VARCHAR",
    },
    "lignes_commande": {
        "commande_id": "INTEGER", "numero_ligne": "INTEGER", "produit_id": "INTEGER",
        "quantite": "INTEGER", "prix_unitaire": "DOUBLE", "remise_pct": "DOUBLE",
        "taux_tva": "DOUBLE", "montant_ligne": "DOUBLE",
    },
    "factures": {
        "facture_id": "INTEGER", "commande_id": "INTEGER", "date_facture": "DATE",
        "date_echeance": "DATE", "statut": "VARCHAR", "montant_total": "DOUBLE",
        "devise": "VARCHAR", "est_payee": "BOOLEAN",
    },
    "paiements": {
        "paiement_id": "INTEGER", "facture_id": "INTEGER", "date_paiement": "DATE",
        "montant": "DOUBLE", "methode": "VARCHAR", "statut": "VARCHAR",
    },
    "produits": {
        "produit_id": "INTEGER", "sku": "VARCHAR", "nom_produit": "VARCHAR", "categorie": "VARCHAR",
        "unite": "VARCHAR", "prix_catalogue": "DOUBLE", "fournisseur_id": "INTEGER", "est_actif": "BOOLEAN",
    },
    "appels_commerciaux_extraits": {
        "appel_id": "INTEGER", "date_appel": "DATE", "commercial": "VARCHAR", "client": "VARCHAR",
        "region": "VARCHAR", "duree_minutes": "INTEGER", "concurrent_cite": "VARCHAR",
        "objection_principale": "VARCHAR", "sentiment": "VARCHAR", "signal_achat": "BOOLEAN",
        "prochaine_etape": "VARCHAR", "resume": "VARCHAR",
    },
    "tickets_service_client_extraits": {
        "ticket_id": "INTEGER", "date_creation": "DATE", "client": "VARCHAR", "region": "VARCHAR",
        "categorie_probleme": "VARCHAR", "produit_concerne": "VARCHAR", "severite": "VARCHAR",
        "delai_resolution_jours": "INTEGER", "sentiment_client": "VARCHAR", "resume": "VARCHAR",
    },
}

RAW_TABLES = {
    "tbl_rgn_mstr": {
        "rgn_cd": "VARCHAR", "rgn_nm": "VARCHAR",
        "tgt_q1_amt": "DOUBLE", "tgt_q2_amt": "DOUBLE", "tgt_q3_amt": "DOUBLE", "tgt_q4_amt": "DOUBLE",
    },
    "tbl_sl_emp": {
        "sl_emp_id": "INTEGER", "emp_nm": "VARCHAR", "rgn_cd": "VARCHAR", "tm_cd": "VARCHAR", "hr_dt": "DATE",
    },
    "tbl_cst_acct": {
        "cst_id": "INTEGER", "cst_nm": "VARCHAR", "cst_cty": "VARCHAR", "rgn_cd": "VARCHAR",
        "seg_cd": "VARCHAR", "sts_cd": "VARCHAR", "cr_dt": "DATE",
    },
    "tbl_ord_hdr": {
        "ord_id": "INTEGER", "cst_id": "INTEGER", "sl_emp_id": "INTEGER",
        "ord_dt": "DATE", "sts_cd": "VARCHAR", "ccy_cd": "VARCHAR", "pmt_trm": "VARCHAR",
    },
    "tbl_ord_ln": {
        "ord_id": "INTEGER", "ln_no": "INTEGER", "itm_id": "INTEGER",
        "qty": "INTEGER", "un_prc": "DOUBLE", "disc_pct": "DOUBLE", "tx_rt": "DOUBLE", "ln_amt": "DOUBLE",
    },
    "tbl_inv_hdr": {
        "inv_id": "INTEGER", "ord_id": "INTEGER", "inv_dt": "DATE", "due_dt": "DATE",
        "sts_cd": "VARCHAR", "ttl_amt": "DOUBLE", "ccy_cd": "VARCHAR", "is_pd": "BOOLEAN",
    },
    "tbl_pmt": {
        "pmt_id": "INTEGER", "inv_id": "INTEGER", "pmt_dt": "DATE",
        "amt": "DOUBLE", "mth_cd": "VARCHAR", "sts_cd": "VARCHAR",
    },
    "tbl_itm_mstr": {
        "itm_id": "INTEGER", "sku": "VARCHAR", "prd_nm": "VARCHAR", "cat_cd": "VARCHAR",
        "uom": "VARCHAR", "lst_prc": "DOUBLE", "sup_id": "INTEGER", "is_act": "BOOLEAN",
    },
}

DATE_COLS = {
    "date_embauche", "date_creation", "date_commande", "date_facture",
    "date_echeance", "date_paiement", "date_appel",
    "hr_dt", "cr_dt", "ord_dt", "inv_dt", "due_dt", "pmt_dt",
}


def get_conn():
    return connect(host=TRINO_HOST, port=TRINO_PORT, user=TRINO_USER, http_scheme="https")


def exec_sql(cursor, sql, label=""):
    tag = f" [{label}]" if label else ""
    print(f"  SQL{tag}: {sql[:120]}...")
    for attempt in range(7):
        try:
            cursor.execute(sql)
            try:
                return cursor.fetchall()
            except Exception:
                return []
        except Exception as e:
            err = str(e).lower()
            retryable = "503" in err or "connection" in err or "resolve" in err or "getaddrinfo" in err or "timeout" in err
            if retryable and attempt < 6:
                wait = 4 * (attempt + 1)
                print(f"    Error (attempt {attempt + 1}/7), retrying in {wait}s: {str(e)[:80]}")
                time.sleep(wait)
                try:
                    cursor.close()
                except Exception:
                    pass
                conn = get_conn()
                cursor = conn.cursor()
            else:
                raise
    return []


def format_val(val, col_name, col_type):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "NULL"
    if col_type == "BOOLEAN":
        return "true" if val else "false"
    if col_type in ("INTEGER", "DOUBLE"):
        return str(val)
    s = str(val).replace("'", "''")
    if col_name in DATE_COLS or col_type == "DATE":
        return f"DATE '{s}'"
    return f"'{s}'"


def load_table(cursor, fq_table, columns_spec, df, batch_size=500):
    col_names = list(columns_spec.keys())
    col_types = list(columns_spec.values())
    total = len(df)
    loaded = 0

    for i in range(0, total, batch_size):
        batch = df.iloc[i:i + batch_size]
        values_list = []
        for _, row in batch.iterrows():
            vals = ", ".join(
                format_val(row[col], col, typ)
                for col, typ in zip(col_names, col_types)
            )
            values_list.append(f"({vals})")

        sql = f"INSERT INTO {fq_table} ({', '.join(col_names)}) VALUES {', '.join(values_list)}"

        for attempt in range(7):
            try:
                cursor.execute(sql)
                try:
                    cursor.fetchall()
                except Exception:
                    pass
                break
            except Exception as e:
                err = str(e).lower()
                retryable = "503" in err or "connection" in err or "resolve" in err or "getaddrinfo" in err or "timeout" in err
                if retryable and attempt < 6:
                    wait = 4 * (attempt + 1)
                    print(f"    Batch {i//batch_size} error (attempt {attempt + 1}/7), retry in {wait}s...")
                    time.sleep(wait)
                else:
                    raise

        loaded += len(batch)

    print(f"  -> {fq_table}: {loaded}/{total} rows loaded")


def load_schema(cursor, schema_name, tables_spec, parquet_dir, drop_existing):
    fq_schema = f"{CATALOG}.{schema_name}"
    exec_sql(cursor, f"CREATE SCHEMA IF NOT EXISTS {fq_schema}", "schema")

    for table_name, columns_spec in tables_spec.items():
        fq_table = f"{fq_schema}.{table_name}"
        parquet_path = os.path.join(parquet_dir, f"{table_name}.parquet")

        if not os.path.exists(parquet_path):
            print(f"  SKIP {table_name}: {parquet_path} not found")
            continue

        if drop_existing:
            print(f"\n  Dropping {fq_table} (if exists)...")
            exec_sql(cursor, f"DROP TABLE IF EXISTS {fq_table}", "drop")
        else:
            try:
                rows = exec_sql(cursor, f"SELECT COUNT(*) FROM {fq_table}", "check")
                count = rows[0][0] if rows else 0
                if count > 0:
                    print(f"\n  SKIP {table_name}: already has {count} rows")
                    continue
            except Exception:
                pass

        col_defs = ", ".join(f"{col} {typ}" for col, typ in columns_spec.items())
        print(f"\n  Creating {fq_table}...")
        exec_sql(cursor, f"CREATE TABLE IF NOT EXISTS {fq_table} ({col_defs})", "create")

        df = pd.read_parquet(parquet_path)
        for col in df.columns:
            if col in DATE_COLS:
                df[col] = df[col].astype(str)

        print(f"  Loading {len(df)} rows...")
        load_table(cursor, fq_table, columns_spec, df)


def main():
    args = set(sys.argv[1:])
    do_gold = "--gold" in args or (not args - {"--drop"})
    do_raw = "--raw" in args or (not args - {"--drop"})
    drop_existing = "--drop" in args

    print("=== Loading Parquet files into Trino ===\n")
    if drop_existing:
        print("Mode: DROP existing tables before loading\n")

    conn = get_conn()
    cursor = conn.cursor()

    if do_gold:
        print(f"--- Loading GOLD schema ({SCHEMA_GOLD}) ---")
        load_schema(cursor, SCHEMA_GOLD, GOLD_TABLES, GOLD_DIR, drop_existing)

    if do_raw:
        print(f"\n--- Loading RAW schema ({SCHEMA_RAW}) ---")
        load_schema(cursor, SCHEMA_RAW, RAW_TABLES, RAW_DIR, drop_existing)

    cursor.close()
    conn.close()
    print("\n=== Done! ===")


if __name__ == "__main__":
    main()
