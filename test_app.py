from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.database import Base, get_db
from app.main import app
from app.models import User
from app.security import hash_password

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)

def override_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_db
with TestingSession() as db:
    if not db.query(User).filter_by(email="owner@test.local").first():
        db.add_all([
            User(name="Owner", email="owner@test.local", password_hash=hash_password("owner-pass")),
            User(name="Guest", email="guest@test.local", password_hash=hash_password("guest-pass")),
        ])
        db.commit()


def test_document_creation_persistence_and_sharing_permissions():
    with TestClient(app) as owner_client:
        login = owner_client.post("/login", data={"email": "owner@test.local", "password": "owner-pass"}, follow_redirects=False)
        assert login.status_code == 303
        created = owner_client.post("/api/documents")
        assert created.status_code == 200
        doc_id = created.json()["id"]
        saved = owner_client.put(f"/api/documents/{doc_id}", json={"title": "Sprint plan", "content": "<h2>Goals</h2><p><strong>Ship</strong> the editor</p>"})
        assert saved.status_code == 200
        share = owner_client.post(f"/api/documents/{doc_id}/share", data={"email": "guest@test.local", "permission": "viewer"}, follow_redirects=False)
        assert share.status_code == 303
    with TestClient(app) as guest_client:
        guest_client.post("/login", data={"email": "guest@test.local", "password": "guest-pass"})
        read = guest_client.get(f"/api/documents/{doc_id}")
        assert read.status_code == 200
        assert read.json()["title"] == "Sprint plan"
        denied = guest_client.put(f"/api/documents/{doc_id}", json={"title": "Hijack", "content": "<p>no</p>"})
        assert denied.status_code == 403
