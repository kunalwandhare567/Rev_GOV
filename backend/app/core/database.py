"""
Database Engine & Session Management
Uses SQLite for on-premise POC (no Docker required).
"""
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# SQLite engine — WAL mode for concurrent reads
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,  # Set to False to prevent cp1252 console logging crashes on unicode parameters
)

# Enable WAL mode and foreign keys on each connection
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def auto_migrate_schema():
    """Dynamically add missing columns to SQLite tables if database file existed prior to schema updates."""
    from sqlalchemy import text
    with engine.connect() as conn:
        # Check users table
        res = conn.execute(text("PRAGMA table_info(users)")).fetchall()
        user_cols = [r[1] for r in res]
        if "citizen_ref" not in user_cols:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN citizen_ref VARCHAR(64)"))
                conn.commit()
            except Exception:
                pass

        # Check citizens table
        res = conn.execute(text("PRAGMA table_info(citizens)")).fetchall()
        citizen_cols = [r[1] for r in res]
        cols_to_add = [
            ("name", "VARCHAR(128)"),
            ("phone", "VARCHAR(32)"),
            ("email", "VARCHAR(128)"),
            ("address", "TEXT"),
        ]
        for col_name, col_type in cols_to_add:
            if col_name not in citizen_cols:
                try:
                    conn.execute(text(f"ALTER TABLE citizens ADD COLUMN {col_name} {col_type}"))
                    conn.commit()
                except Exception:
                    pass

try:
    auto_migrate_schema()
except Exception:
    pass


def get_db():
    """FastAPI dependency: yields a database session and closes on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
