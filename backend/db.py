import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 기본 DB 경로 (필요하면 env로 덮어쓰기)
# 예: export DATABASE_URL="sqlite:///./data/app.db"
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    future=True,
)

Base = declarative_base()


def init_db() -> None:
    # models import가 먼저 되어야 테이블이 등록됨
    import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
