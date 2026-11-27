# Architecture & product decisions

## Product slice

Ajaia Docs focuses on the core loop: create a document, edit it with familiar formatting, save it, import existing text, and share it with a teammate. The app uses a two-account demo workspace so a reviewer can verify ownership and shared access without an external auth provider or email service.

## System overview

```text
Browser
  ├── Jinja-rendered HTML pages + CSS
  ├── contenteditable editor + autosave JavaScript
  └── multipart file import
          │ HTTP / JSON / form posts
          ▼
FastAPI application
  ├── Session middleware (signed cookie)
  ├── Authentication + authorization helpers
  ├── Document CRUD and sharing routes
  ├── Upload parser (TXT / MD / DOCX)
  └── Bleach HTML allow-list sanitizer
          │ SQLAlchemy ORM
          ▼
SQLite (local) / PostgreSQL (hosted)
  ├── users
  ├── documents
  └── document_shares
```

## Data model

- `User`: seeded demo identity and PBKDF2 password hash.
- `Document`: title, HTML content, owner, timestamps.
- `DocumentShare`: document/user relationship and `editor` or `viewer` permission. A unique constraint prevents duplicate shares.

## Authorization model

Every document API request resolves access on the server. The owner has full control. A shared editor can read and update. A shared viewer can only read. Only the owner can delete a document or manage its shares. Hiding the editor toolbar is only a UX affordance; the API independently rejects unauthorized writes with HTTP 403.

## Prioritization and tradeoffs

1. **End-to-end reliability over feature breadth.** CRUD, persistence and permission enforcement are the highest-value reviewer flows.
2. **Usable rich text without a heavy editor dependency.** Native `contenteditable` and browser formatting commands reduce setup and build time. A production iteration should replace this with TipTap/ProseMirror for deterministic document schemas, paste handling and extension support.
3. **Import as a real workflow.** TXT/MD are decoded as UTF-8; DOCX paragraph text is extracted. Unsupported files and oversized uploads receive clear errors.
4. **No pretend real-time collaboration.** The assignment allows scope cuts. This build provides persisted sharing and permissions, not simultaneous editing or conflict resolution.
5. **Practical persistence.** SQLite keeps local setup simple; `DATABASE_URL` supports a hosted PostgreSQL deployment. Persistent disk or managed Postgres is required for durable hosted data.

## Next 2–4 hours

- Replace `contenteditable` with TipTap and store structured JSON.
- Add optimistic concurrency/version numbers to prevent silent overwrites.
- Add a real registration/invitation flow and email delivery.
- Add migration management with Alembic and stronger integration coverage.
- Add document activity history and a small autosave retry queue.
