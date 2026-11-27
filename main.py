import os
from pathlib import Path
from datetime import datetime, timezone
from fastapi import FastAPI, Request, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select, or_
from docx import Document as DocxDocument
import bleach
from io import BytesIO
from .database import Base, engine, get_db, SessionLocal
from .models import User, Document, DocumentShare
from .security import hash_password, verify_password

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="Ajaia Docs", version="1.0.0")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "change-this-secret-before-deploying"), same_site="lax", https_only=os.getenv("COOKIE_SECURE", "false").lower() == "true")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed = [
            ("Sneha Demo", "sneha@ajaia.demo", "sneha123"),
            ("Alex Reviewer", "alex@ajaia.demo", "alex123"),
        ]
        for name, email, password in seed:
            if not db.scalar(select(User).where(User.email == email)):
                db.add(User(name=name, email=email, password_hash=hash_password(password)))
        db.commit()

def current_user(request: Request, db: Session) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Please sign in")
    user = db.get(User, user_id)
    if not user:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Please sign in")
    return user

def get_access(db: Session, document_id: int, user: User):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.owner_id == user.id:
        return doc, "owner"
    share = db.scalar(select(DocumentShare).where(DocumentShare.document_id == doc.id, DocumentShare.user_id == user.id))
    if not share:
        raise HTTPException(status_code=403, detail="You do not have access to this document")
    return doc, share.permission

def user_or_401(request: Request, db: Session = Depends(get_db)):
    return current_user(request, db)

@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    try:
        user = current_user(request, db)
    except HTTPException:
        return RedirectResponse("/login", status_code=303)
    owned = db.scalars(select(Document).where(Document.owner_id == user.id).order_by(Document.updated_at.desc())).all()
    shared_rows = db.scalars(select(DocumentShare).where(DocumentShare.user_id == user.id)).all()
    shared = [db.get(Document, row.document_id) for row in shared_rows]
    shared = [d for d in shared if d and d.owner_id != user.id]
    return templates.TemplateResponse("index.html", {"request": request, "user": user, "owned": owned, "shared": shared})

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

@app.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Email or password is incorrect."}, status_code=400)
    request.session.clear()
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=303)

@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)

@app.post("/api/documents")
def create_document(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    doc = Document(title="Untitled document", content="<p>Start writing your document...</p>", owner_id=user.id)
    db.add(doc); db.commit(); db.refresh(doc)
    return {"id": doc.id, "url": f"/documents/{doc.id}"}

@app.get("/documents/{document_id}", response_class=HTMLResponse)
def editor_page(document_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    doc, permission = get_access(db, document_id, user)
    can_edit = permission in ("owner", "editor")
    shared_users = db.scalars(select(DocumentShare).where(DocumentShare.document_id == doc.id)).all() if permission == "owner" else []
    return templates.TemplateResponse("editor.html", {"request": request, "user": user, "doc": doc, "permission": permission, "can_edit": can_edit, "shared_users": shared_users})

@app.get("/api/documents/{document_id}")
def read_document(document_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db); doc, permission = get_access(db, document_id, user)
    return {"id": doc.id, "title": doc.title, "content": doc.content, "permission": permission, "updated_at": doc.updated_at.isoformat()}

@app.put("/api/documents/{document_id}")
async def update_document(document_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db); doc, permission = get_access(db, document_id, user)
    if permission not in ("owner", "editor"):
        raise HTTPException(status_code=403, detail="Read-only access")
    data = await request.json()
    title = str(data.get("title", doc.title)).strip()
    allowed_tags = set(bleach.sanitizer.ALLOWED_TAGS) | {"p", "br", "h1", "h2", "h3", "strong", "b", "i", "em", "u", "ul", "ol", "li", "blockquote", "div", "span", "pre", "code", "hr"}
    allowed_attrs = {"a": ["href", "title"], "span": ["style"], "p": ["style"], "h1": ["style"], "h2": ["style"], "h3": ["style"]}
    content = bleach.clean(str(data.get("content", doc.content)), tags=allowed_tags, attributes=allowed_attrs, protocols={"http", "https", "mailto"}, strip=True)
    if not title or len(title) > 200:
        raise HTTPException(status_code=422, detail="Title must be between 1 and 200 characters")
    if len(content) > 1_000_000:
        raise HTTPException(status_code=413, detail="Document is too large")
    doc.title = title; doc.content = content; doc.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True, "updated_at": doc.updated_at.isoformat()}

@app.delete("/api/documents/{document_id}")
def delete_document(document_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db); doc, permission = get_access(db, document_id, user)
    if permission != "owner": raise HTTPException(status_code=403, detail="Only the owner can delete this document")
    db.delete(doc); db.commit(); return {"ok": True}

@app.post("/api/documents/{document_id}/share")
def share_document(document_id: int, request: Request, email: str = Form(...), permission: str = Form("editor"), db: Session = Depends(get_db)):
    user = current_user(request, db); doc, access = get_access(db, document_id, user)
    if access != "owner": raise HTTPException(status_code=403, detail="Only the owner can manage sharing")
    target = db.scalar(select(User).where(User.email == email.strip().lower()))
    if not target: raise HTTPException(status_code=404, detail="No demo user found with that email")
    if target.id == user.id: raise HTTPException(status_code=400, detail="You already own this document")
    if permission not in ("editor", "viewer"): raise HTTPException(status_code=422, detail="Invalid permission")
    share = db.scalar(select(DocumentShare).where(DocumentShare.document_id == doc.id, DocumentShare.user_id == target.id))
    if share: share.permission = permission
    else: db.add(DocumentShare(document_id=doc.id, user_id=target.id, permission=permission))
    db.commit()
    return RedirectResponse(f"/documents/{doc.id}?shared=1", status_code=303)

@app.delete("/api/documents/{document_id}/share/{user_id}")
def revoke_share(document_id: int, user_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db); doc, access = get_access(db, document_id, user)
    if access != "owner": raise HTTPException(status_code=403, detail="Only the owner can manage sharing")
    share = db.scalar(select(DocumentShare).where(DocumentShare.document_id == doc.id, DocumentShare.user_id == user_id))
    if share: db.delete(share); db.commit()
    return {"ok": True}

@app.post("/api/import")
async def import_file(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    user = current_user(request, db)
    filename = file.filename or "upload"
    ext = Path(filename).suffix.lower()
    if ext not in (".txt", ".md", ".docx"):
        raise HTTPException(status_code=415, detail="Supported file types: .txt, .md, .docx")
    raw = await file.read()
    if len(raw) > 2_000_000: raise HTTPException(status_code=413, detail="Maximum upload size is 2 MB")
    try:
        if ext == ".docx":
            parsed = DocxDocument(BytesIO(raw))
            text = "\n".join(p.text for p in parsed.paragraphs)
        else:
            text = raw.decode("utf-8-sig")
    except Exception:
        raise HTTPException(status_code=422, detail="Could not read this file. Please use a valid UTF-8 text, Markdown or DOCX file.")
    escaped = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    html = "".join(f"<p>{line or '&nbsp;'}</p>" for line in escaped.splitlines()) or "<p></p>"
    title = Path(filename).stem[:200] or "Imported document"
    doc = Document(title=title, content=html, owner_id=user.id)
    db.add(doc); db.commit(); db.refresh(doc)
    return {"id": doc.id, "url": f"/documents/{doc.id}"}

@app.get("/health")
def health(): return {"status": "ok"}
