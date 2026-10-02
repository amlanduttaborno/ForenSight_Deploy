from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_sqlite_schema() -> None:
    """Small forward-only migration for the local demo database.

    SQLAlchemy's create_all creates new tables but deliberately does not add
    columns to an existing SQLite table.  Keeping this migration here makes an
    update safe for the already-created forensight_demo.db used in the demo.
    """
    if not settings.database_url.startswith("sqlite"):
        return
    additions = {
        "analyses": {
            "user_id": "VARCHAR(36)",
            "review_status": "VARCHAR(30) NOT NULL DEFAULT 'unreviewed'",
            "review_note": "TEXT NOT NULL DEFAULT ''",
        },
        "users": {
            "avatar_filename": "VARCHAR(255)",
            "referral_code": "VARCHAR(24)",
            "referred_by_id": "VARCHAR(36)",
        },
    }
    with engine.begin() as connection:
        for table, columns in additions.items():
            existing = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(" + table + ")")}
            for name, definition in columns.items():
                if name not in existing:
                    connection.exec_driver_sql("ALTER TABLE " + table + " ADD COLUMN " + name + " " + definition)
        # SQLite only permits unique indexes to be added separately.
        connection.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_referral_code ON users (referral_code)")
