import psycopg2

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "sistema_archivos",
    "user": "postgres",
    "password": "Canela25#",
}

def get_db():
    return psycopg2.connect(**DB_CONFIG)
