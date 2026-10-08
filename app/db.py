from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    f"sqlite:///{settings.db_path}",
    connect_args={"check_same_thread": False, "timeout": 15},
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _record):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _upgrade_schema() -> None:
    """Eski sürümle oluşturulmuş veritabanına sonradan eklenen sütunları ekler.

    Tam bir geçiş aracı değil; yalnızca "sütun yoksa ekle" türü zararsız adımlar içindir.
    """
    from .icons import guess_icon

    # Denetim ve değişiklik aynı bağlantıda, tek işlemde yapılır; böylece ikisi de
    # veritabanının aynı halini görür.
    with engine.begin() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(categories)"))}
        if columns and "icon" not in columns:
            conn.execute(text("ALTER TABLE categories ADD COLUMN icon VARCHAR(20) NOT NULL DEFAULT 'etiket'"))
            for cid, name, kind in conn.execute(text("SELECT id, name, kind FROM categories")).all():
                conn.execute(
                    text("UPDATE categories SET icon = :icon WHERE id = :id"),
                    {"icon": guess_icon(name, kind), "id": cid},
                )


def init_db() -> None:
    from . import models  # noqa: F401  (tabloların kaydolması için)

    Base.metadata.create_all(engine)
    _upgrade_schema()
    with SessionLocal() as db:
        models.seed_defaults(db)
