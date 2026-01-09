import os
import psycopg2
from urllib.parse import urlparse

def get_db():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL no está definido")

    r = urlparse(url)
    return psycopg2.connect(
        dbname=r.path.lstrip("/"),
        user=r.username,
        password=r.password,
        host=r.hostname,
        port=r.port or 5432,
    )
