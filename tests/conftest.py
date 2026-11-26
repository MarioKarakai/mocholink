import os

# Debe fijarse antes de importar la app: así ni el engine global ni el lifespan tocan mocholink.db.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401  (registra los modelos en Base.metadata)
from app.database import Base, get_db
from app.main import app


@pytest.fixture(autouse=True)
def test_engine() -> Generator[Engine, None, None]:
    # Un engine en memoria nuevo por test: cada prueba empieza con la BD vacía y no deja residuos.
    # StaticPool comparte una única conexión, necesario para que :memory: sea visible entre hilos.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session(test_engine: Engine) -> Generator[Session, None, None]:
    testing_session_local = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, follow_redirects=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()
