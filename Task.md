# Task: Finish the Reading Room rewrite

## Objective

Finish and harden the in-progress backend/frontend rewrite of the RAG "chat with PDF" app
(replacing the old `rag.py` Gradio prototype, already deleted from the working tree). Close the
functional gaps found in the initial audit, keep everything local-dev-only for now, and cover
the backend with automated tests.

Not a new product, not a rebuild on a different stack — this completes what's already ~90% built
in `backend/app.py` (Flask + MongoDB + JWT) and `frontend/` (React + Vite SPA).

---

## Decisions made (interview log)

| # | Decision | Choice |
|---|---|---|
| 1 | Task scope | Finish the in-progress backend/frontend rewrite already in the working tree |
| 2 | Git baseline | Commit the current uncommitted rewrite as-is, directly (no feature branch), before new work starts |
| 3 | Deployment target | Local only for now (no production hosting concerns this pass) |
| 4 | Document management | Add both: a per-user document list (GET) and delete (DELETE) — currently missing entirely |
| 5 | Admin role scope | User management only (list + deactivate/reactivate) — not document oversight |
| 6 | Admin UI | Full admin panel in the React frontend, not just backend endpoints |
| 7 | Deactivate semantics | Soft-disable: `active: false` blocks login; documents/data untouched; reversible |
| 8 | Session revocation | Immediate — `require_auth` checks `active` in Mongo on every request (not just at login) |
| 9 | Debug mode | Env-controlled via `FLASK_DEBUG` (default off), not hardcoded `True` |
| 10 | Testing scope | Backend unit/integration tests only (pytest); frontend verified manually |
| 11 | Test DB | `mongomock`, not a real MongoDB connection |
| 12 | Test isolation | Mock OpenAI responses and embeddings; Chroma writes to a pytest `tmp_path`, never the real `data/` |
| 13 | Frontend navigation | Simple state-based view toggle (no react-router) |
| 14 | Document list UX | Shown in/near the doc pane; selecting a document loads it and **clears** chat history; delete button per row |
| 15 | Role promotion | Admin panel does NOT promote/demote roles — that stays a deliberate CLI-only action via `create_admin.py` |
| 16 | Self-lockout guard | Deactivate endpoint blocks deactivating yourself, and blocks deactivating the last active admin |
| 17 | `active` field migration | No backfill script — missing field is treated as active (`active is not False`); new users get `active: true` explicitly |
| 18 | Build order | Backend-complete first (incl. tests), then frontend |
| 19 | Plan location | This file |

**Stack stays as-is:** Flask (JSON API) + MongoDB (pymongo) + JWT auth + React/Vite SPA +
ChromaDB (content-hash-keyed collections). A conflicting draft was briefly pasted into this file
describing a SQLite/Jinja-templates/session-auth rebuild — that was a mistake for a different
starting point and does not apply here; discarded.

---

## Data model changes (MongoDB)

**`users` collection** — add field:
- `active: bool` — defaults to `true` on new inserts (`register`, `create_admin.py`). Existing
  docs without the field are treated as active (query as `active: {"$ne": False}`).

**`documents` collection** — no schema change. Already has `owner_id`, `filename`, `pages`,
`chunks`, `created_at` — sufficient for a list view.

**Indexes** — add `documents_col.create_index("owner_id")` alongside the existing
`users_col.create_index("email", unique=True)`.

---

## Backend changes (`backend/app.py`)

1. **Debug mode**: `app.run(port=5000, debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")`.
2. **`active` field on users**:
   - `register()` sets `active: True` on insert.
   - `login()` rejects with a clear error if `active` is `False`.
   - `require_auth` looks up the user by `payload["sub"]` on every request and rejects (401) if
     `active` is `False`. This replaces the current "trust the JWT payload alone" behavior — needs
     a Mongo round trip per request (cheap, indexed by `_id`).
3. **Document list**: `GET /api/documents` → returns the current user's documents (`_id`,
   `filename`, `pages`, `chunks`, `created_at`), sorted by `created_at` descending.
4. **Document delete**: `DELETE /api/documents/<file_id>` →
   - 404 if not owned by the requesting user.
   - Deletes the Chroma collection (`_vectorstore_for(file_id).delete_collection()`), the file in
     `uploads/`, and the Mongo record.
5. **Admin guard**: a `require_admin` decorator (wraps `require_auth`) checking `g.user["role"] == "admin"`.
6. **Admin: list users**: `GET /api/admin/users` → all users' `email`, `role`, `active`, `created_at`.
7. **Admin: deactivate/reactivate**: `PATCH /api/admin/users/<user_id>` with `{"active": bool}` →
   - 400 if target is the requesting admin's own id.
   - 400 if target is an admin being deactivated and no other active admin remains.
   - Otherwise sets `active` on the target and returns the updated record.
8. `create_admin.py`: set `active: True` on `$setOnInsert` (new admins default active) — leave
   existing untouched on promotion of an existing account.

---

## Frontend changes

- **`api.js`**: add `listDocuments`, `deleteDocument`, `listUsers` (admin), `setUserActive` (admin).
- **`App.jsx`**: add `view` state (`'desk' | 'admin'`), a nav link to Admin shown only when
  `user.role === 'admin'`; selecting a document from the list loads it into `doc` and clears
  `messages`.
- **`DocumentPanel.jsx`**: render the document list (filename, pages, date, delete ×) above/beside
  the current upload dropzone; clicking a row loads that document.
- **New `AdminPanel.jsx`**: table of all users (email, role, active, created date) with a
  deactivate/reactivate button per row; disabled/hidden for the current admin's own row. The
  last-active-admin guard is enforced server-side; surfacing the resulting error message is
  sufficient — no need to pre-compute this client-side.
- Visual style follows the existing "Reading Room" identity in `index.css` — no new design system.

---

## Testing plan (pytest, backend only)

- `mongomock.MongoClient` patched in at the point `backend/app.py` constructs `MongoClient`.
- OpenAI: patch `openai_client.chat.completions.create` to return a canned completion object.
- Embeddings/Chroma: use a pytest `tmp_path` for `DATA_DIR`; keep the real `HuggingFaceEmbeddings`
  call mocked out (a lightweight fake embedding function) so tests don't download/run the real model.
- Coverage targets:
  - Auth: register (success, duplicate email, weak password), login (success, bad password,
    deactivated account), `/api/auth/me`.
  - Documents: upload → list → get file → delete (and 404s for non-owned/nonexistent ids).
  - Chat: happy path, missing doc, rate-limit 429.
  - Admin: list users (403 for non-admin), deactivate/reactivate (self-lockout guard, last-admin
    guard, 403 for non-admin).

---

## Out of scope for this pass

- Production deployment (WSGI server, HTTPS, hosting, CORS) — deferred until a deploy is actually planned.
- Role promotion/demotion via UI — stays CLI-only (`create_admin.py`).
- Per-document chat history persistence — switching documents clears the chat log.
- Frontend automated tests.
- Admin oversight of other users' documents.
- Rebuilding on SQLite / server-rendered templates — stack stays Mongo + React + JWT.

---

## Ordered steps

1. Commit current uncommitted rewrite as a clean baseline (`backend/`, `frontend/`, `rag.py`
   removal, `README.md`/`requirements.txt`/`.gitignore` changes).
2. Backend: `active` field + login/require_auth checks + Mongo index.
3. Backend: document list + delete endpoints.
4. Backend: admin guard + list-users + deactivate/reactivate endpoints (with guards).
5. Backend: env-controlled debug mode.
6. Backend tests (pytest + mongomock + mocked OpenAI/embeddings) covering all of the above.
7. Frontend: `api.js` additions.
8. Frontend: document list UI wired into `DocumentPanel`/`App`.
9. Frontend: `AdminPanel.jsx` + nav toggle in `App.jsx`.
10. Manual end-to-end pass in the browser (register, upload, ask, list, delete, admin
    deactivate/reactivate, self-lockout guard, re-login as deactivated user).
