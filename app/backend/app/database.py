from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

from .config import DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_lightweight_migrations():
    """Ajoute les colonnes manquantes sur une base SQLite existante.

    SQLAlchemy's create_all() ne cree que les tables absentes ; il ne modifie
    jamais une table deja existante. Comme cette appli evolue et que la base
    des utilisateurs persiste d'une version a l'autre, on verifie ici les
    colonnes attendues et on les ajoute si besoin (ALTER TABLE ... ADD COLUMN,
    supporte nativement par SQLite).
    """
    expected_columns = {
        "tenders": {
            "deadline_iso": "VARCHAR(10)",
            "is_relevant": "BOOLEAN NOT NULL DEFAULT 1",
        },
        "users": {
            "email": "VARCHAR(200)",
        },
    }

    inspector = inspect(engine)
    tables = inspector.get_table_names()
    with engine.begin() as conn:
        for table, columns in expected_columns.items():
            if table not in tables:
                continue  # la table sera creee par Base.metadata.create_all()
            existing_columns = {col["name"] for col in inspector.get_columns(table)}
            for name, sql_type in columns.items():
                if name not in existing_columns:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}"))
