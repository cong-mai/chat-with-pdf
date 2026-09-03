# Read together — Chat with PDF

A Retrieval-Augmented Generation (RAG) app that lets you upload a PDF and ask it questions, grounded in its actual content. A React frontend talks to a small Flask API that does the indexing and answering.

---

## Features

- Accounts with email/password login and admin/user roles
- Drop in a PDF and ask questions about it — each user only sees their own documents
- Answers are grounded in the document — no hallucination
- Powered by `gpt-4o-mini` for responses and `all-MiniLM-L6-v2` for embeddings
- Vector store persists between sessions (ChromaDB)
- PDF preview rendered inline

---

## Tech Stack

| Layer | Tool |
|---|---|
| Frontend | React (Vite) |
| API | Flask |
| Auth | JWT (`PyJWT`) + hashed passwords (`werkzeug.security`) |
| Accounts DB | MongoDB (`pymongo`) |
| LLM | OpenAI `gpt-4o-mini` |
| Embeddings | HuggingFace `all-MiniLM-L6-v2` |
| Vector DB | ChromaDB (local) |
| PDF Loader | PyMuPDF via LangChain |
| Orchestration | LangChain |

---

## Project Structure

```
.
├── backend/
│   ├── app.py            # Flask API — auth, upload/index a PDF, answer questions
│   └── create_admin.py   # CLI: create or promote an account to admin
├── frontend/             # React (Vite) UI
│   ├── index.html
│   └── src/
├── requirements.txt      # Python (backend) dependencies
├── .env                  # Your API keys/secrets (not committed)
├── uploads/               # Uploaded PDFs (not committed)
└── data/                  # ChromaDB vector store (not committed)
```

---

## Prerequisites

- Python 3.10+
- Node.js 18+
- An [OpenAI API key](https://platform.openai.com/account/api-keys)
- A MongoDB connection string (e.g. a free [MongoDB Atlas](https://www.mongodb.com/cloud/atlas/register) cluster)

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name

# 2. Backend: create a virtual environment and install Python deps
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows
pip install -r requirements.txt

# 3. Frontend: install Node deps
cd frontend
npm install
cd ..
```

---

## Configuration

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=sk-...your-key-here...
MONGODB_URI=mongodb+srv://...your-connection-string...

# Required — generate with: python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET=...a-long-random-string...

# Optional (defaults shown)
MONGODB_DB_NAME=reading_room
JWT_EXPIRES_HOURS=24
MAX_FILE_SIZE_MB=20
MIN_SECONDS_BETWEEN_CHATS=2
MIN_SECONDS_BETWEEN_AUTH_REQUESTS=2
FLASK_DEBUG=false
```

Copy the variable names above into a new `.env` file and fill in your own secrets.

> **Never commit your `.env` file.** It is already listed in `.gitignore`.

Then create your admin account:

```bash
python backend/create_admin.py you@example.com yourpassword
```

Anyone else can sign up for a regular account from the app itself — `/api/auth/register` always creates the `user` role. Run `create_admin.py` again with a different email any time to add another admin, or with an existing email to promote/reset it.

---

## Usage

Run the backend and frontend in two terminals:

```bash
# Terminal 1 — API (http://localhost:5000)
python backend/app.py

# Terminal 2 — frontend dev server (http://localhost:5173)
cd frontend
npm run dev
```

Open `http://localhost:5173`. The dev server proxies `/api/*` requests to the Flask backend, so both run on the same origin from the browser's perspective — no CORS setup needed in development.

1. Log in with the admin account you created, or register a new account
2. Drop a PDF into the document pane, or choose a file
3. Once it says "Ready. Ask away.", type a question in the notes pane
4. For a production build, run `npm run build` in `frontend/` and serve the resulting `frontend/dist/` alongside the API (they'll need to share an origin, or the API will need CORS enabled)

---

## License

MIT
