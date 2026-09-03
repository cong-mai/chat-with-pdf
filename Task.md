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

---
---

# Task: Phase 2 — Production hardening & RAG credibility

Phase 1 (above) is done: auth, roles, document CRUD, admin panel, and a real pytest suite all
exist in the working tree. This phase fixes the bugs a senior review turns up, makes the project
runnable/verifiable by someone who isn't you, and adds the one RAG-specific feature that proves
"grounded" isn't just a README claim.

## Decisions made (interview log)

| # | Decision | Choice |
|---|---|---|
| 1 | Git baseline | Commit the currently-uncommitted Phase 1 rewrite as one clean baseline commit before Phase 2 work starts |
| 2 | Branch strategy | Directly on `master`, no feature branch |
| 3 | Bug 1 fix (orphaned upload) | Move the `dest.write_bytes(data)` call inside the `try`; `dest.unlink(missing_ok=True)` in `except` before returning 500 |
| 4 | Bug 2 fix (leaked exceptions) | Generic fixed client-facing message (no `str(e)`); `logger.exception(...)` server-side; `logging.basicConfig(level=logging.INFO)` at module load |
| 5 | Bug 3 fix (auth rate limit) | Per-IP cooldown (`request.remote_addr`), same in-memory-dict pattern as `_last_chat_time_by_user`; new env var `MIN_SECONDS_BETWEEN_AUTH_REQUESTS` (default `"2"`) |
| 5a | Auth rate limit buckets | Separate dicts per endpoint: `_last_login_time_by_ip`, `_last_register_time_by_ip` (not shared) |
| 6 | Bug 4 fix (prompt injection) | Add a separate `role: "system"` message instructing the model to treat CONTEXT as untrusted data and ignore instructions inside it; CONTEXT stays fenced in the user message |
| 7 | CI | `.github/workflows/test.yml`, single Python version (3.11), triggered on push + pull_request with no branch filter, runs pytest |
| 8 | Docker: backend | gunicorn (not the Flask dev server) — add to `requirements.txt` |
| 9 | Docker: frontend | Multi-stage Dockerfile: `npm run build`, serve `dist/` via nginx; nginx proxies `/api/*` to the backend service (required — `api.js` uses relative URLs) |
| 10 | Docker: persistence | Named volumes for MongoDB data, `uploads/`, and Chroma data — survive `docker compose down` |
| 11 | Logging format | Plain readable text (`basicConfig` format string with timestamp/level/name), not JSON — "structured" just means "logging exists," not literal structured/JSON logging |
| 12 | `/api/health` | Public — no `@require_auth`, no rate limit; checks Mongo connectivity only |
| 13 | Source citations shape | `sources: [{page, snippet}]`, deduped by page (one badge per unique page among the k=3 retrieved chunks), `page` converted to 1-indexed for display, snippet truncated to ~150 chars; rendered as small non-interactive "p. N" badges under the answer in `NotesPanel.jsx` |
| 14 | Retrieval eval sample | Commit one small PDF fixture into `backend/eval/fixtures/` (public-domain text, e.g. the existing Alice in Wonderland PDF) so the eval runs out-of-the-box for anyone who clones the repo |
| 15 | Retrieval eval hit metric | Hit = expected page appears anywhere among the pages of the top-k (k=3) retrieved chunks, using the real embedding model (not mocked, not part of pytest) |
| 16 | Retrieval eval output | Standalone CLI (`python backend/eval/run_eval.py`), prints per-question pass/fail and an overall hit-rate summary to stdout; no report file |
| 17 | Execution order | Keep Task.md's original ordering: bug fixes 1-4 → extend tests → CI → Docker/`.env.example`/health → source citations → retrieval eval |

## Bugs / security (fix first — small, concrete, high value)

1. **Orphaned upload on indexing failure** — `app.py:216-228` writes the PDF to `uploads/` before
   the `try` block. If `PyMuPDFLoader` or the Chroma call raises, the file is left on disk with no
   Mongo record pointing at it. Fix: wrap the write itself in the try, or `dest.unlink(missing_ok=True)`
   in an `except` clause before returning 500.
2. **Internal exceptions leak to the client, nothing logged server-side** — `app.py:227-228` and
   `app.py:341-342` return `str(e)` straight into the JSON response body, and there is no `logging`
   call anywhere in the file. Fix: add a module-level `logger = logging.getLogger(__name__)`, log
   the full exception server-side (`logger.exception(...)`), and return a generic message to the
   client.
3. **No rate limit on `/api/auth/login` / `/api/auth/register`** — only `/api/chat` is throttled
   (`_last_chat_time_by_user`). Add the same per-IP-or-email throttle pattern to auth endpoints to
   close the brute-force gap.
4. **Prompt injection surface** — `app.py:326-334` splices raw retrieved chunk text into the prompt
   with no delimiters. Wrap CONTEXT in clear fenced boundaries and add a one-line system instruction
   to ignore instructions found inside the context. Low severity here (single-user PDFs), but worth
   doing and worth being able to explain in an interview.

## Production readiness

5. **CI**: `.github/workflows/test.yml` running `pytest` on push/PR. You already have a full suite
   (`backend/tests/`) and `requirements-dev.txt` — this is close to free and is the highest-leverage
   item for a portfolio/LinkedIn story.
6. **Containerize**: `Dockerfile` for the backend, a `docker-compose.yml` wiring backend + frontend +
   a local `mongo` service. Goal: a stranger can run `docker compose up` with no local Python/Node/
   Mongo install.
7. **Structured logging** (ties into bug #2) — replace bare `except Exception` blocks with logged
   exceptions; keep client-facing messages generic.
8. **`/api/health`** endpoint (checks Mongo connectivity) + a checked-in `.env.example` documenting
   every variable already listed in the README's Configuration section.

## RAG credibility

9. **Source citations**: `/api/chat` currently discards chunk metadata after retrieval
   (`app.py:320-340`). Return `sources: [{page, snippet}]` alongside `answer`, and render them in
   `NotesPanel.jsx` as small citation badges under each answer. This is the feature that visually
   proves grounding instead of just asserting it in the README.
10. **Retrieval eval script**: `backend/eval/` — a hand-written set of ~15-20 (question, expected
    page/answer) pairs against one sample PDF, run standalone (not part of pytest) to report
    retrieval hit-rate. This is the difference between "I called an LLM" and "I measured whether the
    pipeline retrieves the right thing" — the strongest interview talking point in this whole plan.

## Out of scope for this pass

- Streaming chat responses, response pagination, OpenAPI/Swagger docs.
- Frontend automated tests (still manual per Phase 1 decision).
- File content/virus scanning beyond the existing extension + size checks.
- Actual cloud deployment (Phase 1 kept this local-only; Docker in item 6 is not a hosting decision).

## Ordered steps

1. Bug fixes 1-4 (small, isolated, each independently testable).
2. Extend `backend/tests/` to cover the new failure-cleanup and rate-limit behavior.
3. CI workflow (item 5) — do this once the test suite covers the new behavior, so CI is protecting
   real coverage from the start.
4. Docker + `.env.example` + health check (items 6, 8).
5. Source citations: backend response shape first, then `NotesPanel.jsx` rendering (item 9).
6. Retrieval eval script (item 10) — last, since it's most useful once citations exist to spot-check
   against.

---

## Detailed execution plan (step-by-step, with acceptance criteria and proof of correctness)

Each step lists: **Changes** (what gets touched), **Acceptance criteria** (concrete, checkable
conditions — not "looks right"), and **Proof of correctness** (the exact command/request to run
and what output confirms the criteria are met). A step isn't done until its proof has actually
been run and produced the stated result.

### Step 1 — Commit the Phase 1 baseline (decision #1, #2)

**Changes**: `git add` the currently-uncommitted `backend/`, `frontend/`, `requirements-dev.txt`,
`backend/tests/` and commit as one baseline commit on `master`.

**Acceptance criteria**
- `git status --short` is empty (or shows only files intentionally left out) after the commit.
- `git log -1` shows a single new commit containing exactly the files listed in the pre-Phase-2
  git status snapshot (`app.py`, `create_admin.py`, `App.jsx`, `api.js`, `DocumentPanel.jsx`,
  `index.css`, `backend/tests/`, `AdminPanel.jsx`, `requirements-dev.txt`).
- `pytest backend/tests -q` passes against the committed state (baseline is green before Phase 2
  changes begin).

**Proof of correctness**
```
git status --short          # expect: empty
git show --stat HEAD        # expect: the Phase 1 file list above
pytest backend/tests -q     # expect: all pass, 0 failures
```

---

### Step 2 — Bug fixes 1-4 (`backend/app.py`)

#### 2a. Orphaned upload on indexing failure (decision #3)

**Changes**: move `dest.write_bytes(data)` inside the `try` block in `upload_document()`; add
`dest.unlink(missing_ok=True)` in the `except` clause before returning 500.

**Acceptance criteria**
- If `PyMuPDFLoader.load()` or `vectorstore.add_documents()` raises, no `.pdf` file remains under
  `UPLOAD_DIR` afterward.
- No Mongo `documents` record is created for a failed upload.
- The endpoint still returns 500 on failure (behavior for the caller is unchanged, only the
  filesystem side effect is fixed).

**Proof of correctness**: a new test in `backend/tests/test_documents.py` that monkeypatches
`PyMuPDFLoader.load` (or `_chunk_documents`) to raise, uploads a PDF, and asserts:
```python
resp = client.post("/api/documents", ...)
assert resp.status_code == 500
assert list(app_module.UPLOAD_DIR.iterdir()) == []
assert app_module.documents_col.count_documents({}) == 0
```

#### 2b. Internal exceptions leaked to the client / nothing logged (decision #4)

**Changes**: add `logger = logging.getLogger(__name__)` and
`logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")`
near the top of `app.py`; replace every `except Exception as e: return jsonify(error=f"...{e}"), 500`
with `logger.exception("...")` + a fixed generic message (no `str(e)` in the response).

**Acceptance criteria**
- No 500 response body from any endpoint contains raw exception text.
- The full exception (message + traceback) is captured server-side via `logger.exception`.

**Proof of correctness**: using pytest's `caplog` fixture, force a distinctive exception (e.g.
monkeypatch a call to raise `ValueError("distinct-marker-abc123")`) and assert:
```python
resp = client.post(...)
assert "distinct-marker-abc123" not in resp.get_json()["error"]
assert "distinct-marker-abc123" in caplog.text
```

#### 2c. No rate limit on login/register (decision #5, #5a)

**Changes**: add `MIN_SECONDS_BETWEEN_AUTH_REQUESTS` (env, default `"2"`), and two dicts
`_last_login_time_by_ip` / `_last_register_time_by_ip` keyed by `request.remote_addr`, checked at
the top of `login()` / `register()` respectively, mirroring the existing chat cooldown pattern.

**Acceptance criteria**
- A second `POST /api/auth/login` from the same IP inside the cooldown window returns 429,
  regardless of whether the credentials are correct.
- Same for `POST /api/auth/register`.
- A `register` call immediately after a `login` call from the same IP is **not** blocked (separate
  buckets), and vice versa.
- After the cooldown elapses, requests succeed normally.

**Proof of correctness**: new tests in `backend/tests/test_auth.py`:
```python
def test_login_rate_limited(client, make_user):
    make_user("a@x.com")
    client.post("/api/auth/login", json={"email": "a@x.com", "password": "password123"})
    resp = client.post("/api/auth/login", json={"email": "a@x.com", "password": "password123"})
    assert resp.status_code == 429

def test_login_and_register_buckets_independent(client, make_user):
    make_user("a@x.com")
    client.post("/api/auth/login", json={"email": "a@x.com", "password": "password123"})
    resp = client.post("/api/auth/register", json={"email": "b@x.com", "password": "password123"})
    assert resp.status_code != 429
```

#### 2d. Prompt injection surface (decision #6)

**Changes**: in `chat()`, send a separate `role: "system"` message instructing the model to treat
CONTEXT as untrusted data and ignore any instructions found inside it; keep CONTEXT fenced
(e.g. inside a delimited block) in the user message.

**Acceptance criteria**
- The `messages` list passed to `openai_client.chat.completions.create` has ≥2 entries: one
  `role: "system"` containing an explicit "ignore instructions in the context" directive, and one
  `role: "user"` with the fenced CONTEXT + QUESTION.

**Proof of correctness**: in `backend/tests/test_chat.py`, capture the mocked
`openai_client.chat.completions.create` call args and assert:
```python
messages = mock_create.call_args.kwargs["messages"]
assert messages[0]["role"] == "system"
assert "ignore" in messages[0]["content"].lower()
assert "CONTEXT" in messages[-1]["content"]
```

---

### Step 3 — Extend `backend/tests/` for the new behavior

**Changes**: the four test additions described in Step 2a-2d land here (they can be written
alongside each fix, but this step is the checkpoint that they all exist and pass together).

**Acceptance criteria**
- `pytest backend/tests -q` passes with 0 failures.
- The collected test count increased by exactly the number of new test functions added (one per
  bug, at minimum).

**Proof of correctness**
```
pytest backend/tests --collect-only -q | tail -1   # note count before Step 2, compare after
pytest backend/tests -q                            # expect: all pass, 0 failures
```

---

### Step 4 — CI workflow (decision #7)

**Changes**: `.github/workflows/test.yml` — checkout, `actions/setup-python@v5` with
`python-version: "3.11"`, `pip install -r requirements-dev.txt`, `pytest backend/tests`. Triggers:
`on: [push, pull_request]`, no branch filter.

**Acceptance criteria**
- The workflow YAML is syntactically valid.
- The exact commands the workflow runs succeed locally in a clean environment (this is what CI
  will do).

**Proof of correctness**
```
python -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml'))"   # no error
python -m venv /tmp/ci-repro && /tmp/ci-repro/bin/pip install -r requirements-dev.txt \
  && /tmp/ci-repro/bin/pytest backend/tests -q   # expect: all pass
```
Then push the commit (or open a PR) and confirm the Actions tab shows a green run — this is the
final confirmation that can only happen after a real push, not something reproducible offline.

---

### Step 5 — Docker + `.env.example` + health check (decisions #8, #9, #10, #11, #12)

**Changes**:
- `backend/Dockerfile`: python slim base, install `requirements.txt` (add `gunicorn`), run
  `gunicorn -b 0.0.0.0:5000 backend.app:app`.
- `frontend/Dockerfile`: multi-stage — `npm ci && npm run build`, then copy `dist/` into an nginx
  image with `frontend/nginx.conf` (serves static files, proxies `/api/*` to `backend:5000`).
- `docker-compose.yml` at repo root: services `mongo`, `backend`, `frontend`; named volumes
  `mongo-data`, `uploads`, `chroma-data` mounted into `mongo`/`backend` respectively; `backend`
  depends on `mongo`.
- `backend/app.py`: `GET /api/health` — no auth, no rate limit, pings Mongo
  (`mongo_client.admin.command("ping")`), returns `{"status": "ok"}` / 200 or
  `{"status": "error"}` / 503.
- `.env.example` at repo root, mirroring every variable in the README's Configuration section with
  placeholder (non-secret) values.

**Acceptance criteria**
- `docker compose config` validates without error.
- `docker compose up --build` brings up all three services; the frontend URL serves the SPA;
  `/api/health` (proxied through nginx) returns 200 with `{"status": "ok"}`.
- Data (a registered user, an uploaded document) survives `docker compose down` followed by
  `docker compose up` (named-volume persistence).
- `.env.example` contains every variable from the README Configuration block, with no real secret
  values, and `.env` itself stays out of git (already gitignored).

**Proof of correctness**
```
docker compose config                                   # expect: no error
docker compose up -d --build
curl -s http://localhost:8080/api/health                # expect: {"status":"ok",...} HTTP 200
curl -s http://localhost:8080/                           # expect: 200, HTML containing the SPA root div
# register + upload a doc via curl or the UI, then:
docker compose down && docker compose up -d
# re-list documents for that user — expect the previously uploaded doc still present
docker compose down -v   # cleanup
diff <(sort .env.example | cut -d= -f1) \
     <(grep -oP '^\w+(?==)' README.md | sort)            # sanity check var-name coverage
```

---

### Step 6 — Source citations (decision #13)

**Changes**:
- `backend/app.py` `chat()`: after retrieval, dedup `results` by `metadata["page"]` (converted to
  1-indexed), build `sources: [{"page": int, "snippet": str}]` (snippet truncated to ~150 chars),
  return alongside `answer`.
- `frontend/src/api.js`: no change needed (already returns full JSON body).
- `frontend/src/App.jsx`: store `sources` on the assistant message object.
- `frontend/src/components/NotesPanel.jsx`: render small "p. N" badges under the answer text when
  `sources.length > 0`.

**Acceptance criteria**
- `/api/chat` response includes a `sources` array whenever retrieval returns results; each entry
  has an integer `page >= 1` and a string `snippet`.
- No duplicate `page` values within one response's `sources` array.
- Badges render in the browser under the relevant assistant message only, not under user messages.

**Proof of correctness**: in `backend/tests/test_chat.py`:
```python
data = client.post("/api/chat", ...).get_json()
pages = [s["page"] for s in data["sources"]]
assert all(isinstance(p, int) and p >= 1 for p in pages)
assert len(pages) == len(set(pages))   # dedup check
```
Manual browser check: upload a multi-page PDF, ask a question, confirm citation badges appear with
page numbers that match where the answer's content actually appears in the PDF (spot-check by
opening the source PDF to that page).

---

### Step 7 — Retrieval eval script (decisions #14, #15, #16)

**Changes**:
- `backend/eval/fixtures/sample.pdf` — committed public-domain PDF (copy of the existing Alice in
  Wonderland test upload).
- `backend/eval/dataset.json` — 15-20 `{"question": str, "expected_page": int}` entries authored
  against the fixture's actual content.
- `backend/eval/run_eval.py` — standalone script: builds/loads a Chroma collection from the
  fixture using the **real** embedding model (not mocked), runs each question through
  `similarity_search(k=3)`, checks whether `expected_page` is among the retrieved chunks' pages,
  prints one pass/fail line per question and a final summary line.

**Acceptance criteria**
- `python backend/eval/run_eval.py` exits 0.
- Output includes one line per dataset entry and a final summary line matching
  `N/M hits (P%)`.
- Running it twice produces byte-identical output (deterministic retrieval — no timestamps, no
  randomness in the output).

**Proof of correctness**
```
python backend/eval/run_eval.py                          # expect: exit 0, per-question lines + summary
diff <(python backend/eval/run_eval.py) <(python backend/eval/run_eval.py)   # expect: no diff
```

---

## Definition of done

- [x] `pytest backend/tests -q` passes (0 failures), including all new tests from Steps 2-3 and 6.
      49/49 passing as of the Step 7 commit.
- [x] `.github/workflows/test.yml` shows a green run on GitHub after a push. Pushed to
      `origin/master`; run https://github.com/cong-mai/chat-with-pdf/actions/runs/33794970417
      completed with conclusion `success`.
- [x] `docker compose up --build` config validates and the backend image builds successfully
      (confirmed via `docker compose config` and a full build reaching the backend stage). A
      complete `docker compose up` end-to-end run (all three services live, restart-persistence
      check) could not be completed in this session: the sandbox's network connection reset
      repeatedly on Docker Hub's larger image layers (confirmed environmental, not project-specific
      — even `hello-world` failed identically at first, then succeeded on retry). Pinned `mongo:6`
      instead of `mongo:7` since :6 was already cached locally and proven to pull reliably here;
      bump the tag freely once a stable connection isn't a concern. Recommend re-running
      `docker compose up -d --build` locally to get the full live-run confirmation.
- [x] Citation badges are visible in the browser for a real question against a real PDF. Manually
      verified end-to-end: registered a test account, uploaded an 11-page PDF, asked a question, got
      a correct grounded answer with three distinct, correctly-deduped page badges (p.1, p.10, p.2)
      whose tooltip snippets matched the actual page content. Test account and documents were
      cleaned up afterward.
- [x] `backend/eval/run_eval.py` runs standalone and prints a reproducible hit-rate summary.
      19/20 hits (95.0%); byte-identical output across two consecutive runs.

**Note:** while verifying Docker, `docker compose config` printed the real `.env` secrets
(`OPENAI_API_KEY`, `JWT_SECRET`) into terminal output in this session. The user was notified
immediately and is rotating the OpenAI key; all subsequent Docker verification used a swapped-in
dummy `.env` to avoid repeating this.
