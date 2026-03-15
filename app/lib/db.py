from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from app.configs.database_configuration import DatabaseConfiguration
from typing import Generator

Base = declarative_base()

db_config = DatabaseConfiguration()

# TODO: Setting up the engine with environment variables
engine = create_engine(
    db_config.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
)

SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine
)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
from enum import Enum

def enum_values(enum_cls: type[Enum]) -> list[str]:
    return [e.value for e in enum_cls]