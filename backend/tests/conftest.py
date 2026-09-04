import hashlib
import os
import sys
from pathlib import Path
from unittest.mock import patch

# Dummy secrets so backend/app.py's module-level env checks don't raise —
# no real OpenAI/Mongo credentials are ever touched by the test suite.
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("MONGODB_URI", "mongodb://localhost/test")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("MIN_SECONDS_BETWEEN_CHATS", "2")

from datetime import UTC

import mongomock
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


class _FakeEmbeddings:
    """Deterministic, offline stand-in for HuggingFaceEmbeddings.

    Avoids downloading/running the real all-MiniLM-L6-v2 model in tests.
    Similarity search still works meaningfully because the fake vectors are
    derived from the text itself (identical text -> identical vector).
    """

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)

    @staticmethod
    def _vec(text):
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [b / 255 for b in digest[:16]]


# backend/app.py does its Mongo connection and embedding-model load at
# *module import time*, so both must be patched before that import runs.
with patch("pymongo.MongoClient", mongomock.MongoClient), patch(
    "langchain_huggingface.HuggingFaceEmbeddings", lambda **kwargs: _FakeEmbeddings()
):
    from backend import app as app_module


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    """Reset all shared/module-level state before every test."""
    app_module.users_col.delete_many({})
    app_module.documents_col.delete_many({})
    app_module._last_chat_time_by_user.clear()
    app_module._last_login_time_by_ip.clear()
    app_module._last_register_time_by_ip.clear()

    data_dir = tmp_path / "data"
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr(app_module.config, "DATA_DIR", data_dir)
    monkeypatch.setattr(app_module.config, "UPLOAD_DIR", upload_dir)

    yield


@pytest.fixture
def client():
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


@pytest.fixture
def make_user():
    """Insert a user directly into the (mocked) users collection."""
    import uuid
    from datetime import datetime

    from werkzeug.security import generate_password_hash

    def _make(email, password="password123", role="user", active=True):
        user_doc = {
            "_id": str(uuid.uuid4()),
            "email": email,
            "password_hash": generate_password_hash(password),
            "role": role,
            "active": active,
            "created_at": datetime.now(UTC),
        }
        app_module.users_col.insert_one(user_doc)
        token = app_module._issue_token(
            {"id": user_doc["_id"], "email": email, "role": role}
        )
        return {"id": user_doc["_id"], "email": email, "role": role, "token": token}

    return _make


@pytest.fixture
def auth_header():
    def _header(token):
        return {"Authorization": f"Bearer {token}"}

    return _header


@pytest.fixture
def sample_pdf_bytes():
    """A tiny, real, one-page PDF with actual extractable text."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "The sky is blue and the grass is green.")
    data = doc.tobytes()
    doc.close()
    return data
