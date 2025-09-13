from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import os

# Allow overriding database via environment.
# Default remains the lightweight local sqlite DB used in tests.
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+pysqlite:///./test.db")

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
	pass