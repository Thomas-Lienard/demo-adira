import logging
import os
from trino.dbapi import connect

log = logging.getLogger(__name__)

TRINO_ENDPOINTS = [
    {
        "host": os.environ.get("TRINO_HOST", "trino.thelio.app"),
        "port": int(os.environ.get("TRINO_PORT", "443")),
        "scheme": os.environ.get("TRINO_SCHEME", "https"),
    },
    {
        "host": "87.106.122.113",
        "port": 18080,
        "scheme": "http",
    },
]

TRINO_USER = os.environ.get("TRINO_USER", "thomas.lienard")
TRINO_CATALOG = "iceberg"
SCHEMA_RAW = "demo_adira_raw"
SCHEMA_GOLD = "demo_adira_gold"


def _get_connection():
    last_error = None
    for ep in TRINO_ENDPOINTS:
        try:
            conn = connect(
                host=ep["host"],
                port=ep["port"],
                user=TRINO_USER,
                http_scheme=ep["scheme"],
                request_timeout=10,
            )
            conn.cursor().execute("SELECT 1")
            log.info("Connected to Trino at %s:%s (%s)", ep["host"], ep["port"], ep["scheme"])
            return conn
        except Exception as e:
            log.warning("Trino endpoint %s:%s failed: %s", ep["host"], ep["port"], e)
            last_error = e
    raise last_error


def _execute(sql: str) -> list[dict]:
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(sql)
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [dict(zip(columns, row)) for row in rows]


def execute_query_raw(sql: str) -> list[dict]:
    return _execute(sql)


def execute_query_gold(sql: str) -> list[dict]:
    return _execute(sql)


def execute_query(sql: str) -> list[dict]:
    return execute_query_gold(sql)


def get_raw_schema() -> str:
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SHOW TABLES FROM {TRINO_CATALOG}.{SCHEMA_RAW}")
    tables = [row[0] for row in cursor.fetchall()]

    schema_parts = []
    for table_name in tables:
        cursor.execute(f"DESCRIBE {TRINO_CATALOG}.{SCHEMA_RAW}.{table_name}")
        cols = cursor.fetchall()
        col_lines = [f"  {c[0]} {c[1]}" for c in cols]
        schema_parts.append(f"TABLE {TRINO_CATALOG}.{SCHEMA_RAW}.{table_name}:\n" + "\n".join(col_lines))

    cursor.close()
    conn.close()
    return "\n\n".join(schema_parts)


def get_gold_schema() -> str:
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SHOW TABLES FROM {TRINO_CATALOG}.{SCHEMA_GOLD}")
    tables = [row[0] for row in cursor.fetchall()]

    schema_parts = []
    for table_name in tables:
        cursor.execute(f"DESCRIBE {TRINO_CATALOG}.{SCHEMA_GOLD}.{table_name}")
        cols = cursor.fetchall()
        col_lines = [f"  {c[0]} {c[1]}" for c in cols]
        schema_parts.append(f"TABLE {TRINO_CATALOG}.{SCHEMA_GOLD}.{table_name}:\n" + "\n".join(col_lines))

    cursor.close()
    conn.close()
    return "\n\n".join(schema_parts)
