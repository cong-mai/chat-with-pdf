# Chat with PDF — RAG Application

A Retrieval-Augmented Generation (RAG) app that lets you upload a PDF and chat with its contents. Built with Gradio, LangChain, ChromaDB, and OpenAI.

---

## Features

- Upload any PDF and ask questions about it
- Answers are grounded in the document — no hallucination
- Powered by `gpt-4o-mini` for responses and `all-MiniLM-L6-v2` for embeddings
- Vector store persists between sessions (ChromaDB)
- PDF preview rendered inline

---

## Tech Stack

| Layer | Tool |
|---|---|
| UI | Gradio |
| LLM | OpenAI `gpt-4o-mini` |
| Embeddings | HuggingFace `all-MiniLM-L6-v2` |
| Vector DB | ChromaDB (local) |
| PDF Loader | PyMuPDF via LangChain |
| Orchestration | LangChain |

---

## Prerequisites

- Python 3.10+
- An [OpenAI API key](https://platform.openai.com/account/api-keys)

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Configuration

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=sk-...your-key-here...

# Optional — basic abuse/cost guards (defaults shown)
MAX_FILE_SIZE_MB=20
MIN_SECONDS_BETWEEN_CHATS=2
```

> **Never commit your `.env` file.** It is already listed in `.gitignore`.

---

## Usage

```bash
python rag.py
```

Then open `http://localhost:7860` in your browser.

1. Upload a PDF using the left panel
2. Click **Process PDF** and wait for indexing to complete
3. Type a question in the chat box and press Enter or click **Chat**

---

## Share with Others (temporary link)

To give a friend access without deploying to a server, use [ngrok](https://ngrok.com):

```bash
# Terminal 1 — run the app
python rag.py

# Terminal 2 — expose it publicly
ngrok http 7860
```

Ngrok prints a public URL (e.g. `https://abc123.ngrok-free.app`) that anyone can open.

---

## Deploying to AWS (permanent)

Rough outline for EC2 + Nginx + SSL setup with your own domain. This app is a local demo (single-process Gradio server, no auth, no persistent job queue) — for real public deployment, put it behind auth and keep the size/rate-limit env vars above set conservatively.

1. Launch an EC2 `t3.medium` (Ubuntu 22.04)
2. Assign an Elastic IP
3. Point your domain's DNS A record to that IP
4. Run the app as a systemd service
5. Use Nginx as a reverse proxy on port 80/443
6. Get a free SSL cert with `certbot`

---

## Project Structure

```
.
├── rag.py              # Main application
├── requirements.txt    # Python dependencies
├── .env                # Your API key (not committed)
├── .gitignore
└── data/               # ChromaDB vector store (not committed)
```

---

## License

MIT
