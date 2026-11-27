# AI workflow note

## Tools used

OpenAI ChatGPT was used as an AI coding assistant to help plan the architecture, scaffold the FastAPI application, draft UI templates and styles, and produce initial test and documentation drafts.

## Where AI accelerated the work

- Turned the open-ended brief into a small prioritized product slice.
- Accelerated repetitive scaffolding across SQLAlchemy models, FastAPI routes, Jinja templates and CSS.
- Helped draft the integration test and reviewer setup instructions.

## Judgment applied / output changed

- Kept the implementation Python-first (FastAPI + server-rendered pages) rather than introducing a separate React toolchain, to reduce setup and deployment risk inside the 4–6 hour constraint.
- Did not claim real-time collaboration. Shared access is implemented with explicit owner/editor/viewer permissions.
- Added server-side authorization rather than relying only on disabled UI controls.
- Added HTML allow-list sanitization before saving editor content.
- Limited file import to TXT, Markdown and DOCX, and documented the DOCX formatting limitations.
- Rejected the temptation to add comments, presence indicators or version history before the core save/share flows were complete.

## Verification performed / required before submission

The automated test covers login, create, save, share and viewer write rejection. Before submitting, run `pytest -q`, manually test both seeded accounts in a browser, test all three supported file types and an unsupported file, and verify that a viewer cannot modify a document by calling the API directly.

AI-generated code is a starting point, not proof of correctness. The developer submitting this assignment should personally inspect the implementation, run the checks, fix any environment-specific issues, and update this note to accurately reflect the tools and verification actually used.
