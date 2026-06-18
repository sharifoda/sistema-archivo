import os
import re
from urllib.parse import parse_qs, unquote, unquote_plus, urlparse

import pyodbc
from dotenv import load_dotenv
load_dotenv()


RETURNING_RE = re.compile(
    r"(?is)^\s*insert\s+into\s+([^\(]+)\((.*?)\)\s*values\s*\((.*?)\)\s*returning\s+([a-zA-Z_][\w]*)\s*;?\s*$"
)
LIMIT_RE = re.compile(r"(?is)\s+limit\s+(\d+)\s*;?\s*$")

SQL_NAME_REPLACEMENTS = [
    (r"\busuarios_grupos\b", "usuariosempresas"),
    (r"\bgrupos\b", "empresas"),
    (r"\blogs\b", "auditoria"),
    (r"\bgrupo_origen_id\b", "empresa_origen"),
    (r"\bgrupo_id\b", "empresa"),
    (r"\busuario_id\b", "usuarioid"),
    (r"\bpuede_eliminar\b", "eliminar"),
    (r"\bpuede_editar\b", "editar"),
]


def _replace_password_column(sql: str) -> str:
    return re.sub(r"(?<!\[)\bpassword\b(?!\])", "[contraseña]", sql, flags=re.IGNORECASE)


def _translate_limit(sql: str) -> str:
    match = LIMIT_RE.search(sql)
    if not match:
        return sql
    limit = match.group(1)
    sql = LIMIT_RE.sub("", sql)
    if re.search(r"(?is)\border\s+by\b", sql):
        return f"{sql} OFFSET 0 ROWS FETCH NEXT {limit} ROWS ONLY"
    return re.sub(r"(?is)^\s*select\b", f"SELECT TOP {limit}", sql, count=1)


def translate_sql(sql: str) -> str:
    sql = _replace_password_column(sql)
    for pattern, replacement in SQL_NAME_REPLACEMENTS:
        sql = re.sub(pattern, replacement, sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bTRUE\b", "1", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bFALSE\b", "0", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bNOW\(\)", "SYSDATETIME()", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bILIKE\b", "LIKE", sql, flags=re.IGNORECASE)

    match = RETURNING_RE.match(sql)
    if match:
        table_name, columns, values, returning_col = match.groups()
        sql = f"INSERT INTO {table_name}({columns}) OUTPUT INSERTED.{returning_col} VALUES ({values})"

    sql = _translate_limit(sql)
    return sql.replace("%s", "?")


class SqlServerCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, params=None):
        translated = translate_sql(sql)
        if params is None:
            self._cursor.execute(translated)
        else:
            self._cursor.execute(translated, params)
        return self

    def executemany(self, sql, seq_params):
        translated = translate_sql(sql)
        self._cursor.fast_executemany = True
        self._cursor.executemany(translated, seq_params)
        return self

    def __iter__(self):
        return iter(self._cursor)

    def __getattr__(self, item):
        return getattr(self._cursor, item)


class SqlServerConnection:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return SqlServerCursor(self._conn.cursor())

    def __getattr__(self, item):
        return getattr(self._conn, item)


def _build_connection_string(url: str) -> str:
    parsed = urlparse(url)
    dbname = unquote(parsed.path.lstrip("/"))
    if not dbname:
        raise RuntimeError("DATABASE_URL no contiene nombre de base de datos")

    query = parse_qs(parsed.query)
    driver = unquote_plus(query.get("driver", [os.environ.get("SQLSERVER_DRIVER", "ODBC Driver 17 for SQL Server")])[0])
    host = parsed.hostname or "localhost"
    port = parsed.port or 1433

    parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={host},{port}",
        f"DATABASE={dbname}",
        "TrustServerCertificate=yes",
    ]

    username = unquote(parsed.username) if parsed.username else None
    password = unquote(parsed.password) if parsed.password else None

    if username:
        parts.append(f"UID={username}")
    if password:
        parts.append(f"PWD={password}")
    else:
        parts.append("Trusted_Connection=yes")

    return ";".join(parts)


def get_db():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL no está definido")

    parsed = urlparse(url)
    if parsed.scheme.lower() not in {"sqlserver", "mssql"}:
        raise RuntimeError(
            "DATABASE_URL debe usar esquema sqlserver:// o mssql:// para SQL Server"
        )

    conn = pyodbc.connect(_build_connection_string(url))
    conn.autocommit = False
    return SqlServerConnection(conn)
