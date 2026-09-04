"""Environment configuration, constants, and shared regexes.

Read via `from .. import config` and `config.NAME` (not `from .config import
NAME`) wherever a value is monkeypatched in tests (e.g. DATA_DIR, UPLOAD_DIR) —
a direct-name import would cache a stale reference that a later
`monkeypatch.setattr(config, "NAME", ...)` couldn't reach.
"""

import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("backend.app")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

# Defaults to BASE_DIR (today's behavior) when unset. Set to a single mounted
# volume path in production (e.g. Railway, which allows only one volume per
# service) so both persisted directories below live under one mount point.
PERSIST_DIR = Path(os.getenv("PERSIST_DIR", str(BASE_DIR)))
UPLOAD_DIR = PERSIST_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR = PERSIST_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE_MB = float(os.getenv("MAX_FILE_SIZE_MB", "20"))
MIN_SECONDS_BETWEEN_CHATS = float(os.getenv("MIN_SECONDS_BETWEEN_CHATS", "2"))
MIN_SECONDS_BETWEEN_AUTH_REQUESTS = float(os.getenv("MIN_SECONDS_BETWEEN_AUTH_REQUESTS", "2"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError(
        "Please set the OPENAI_API_KEY environment variable. "
        "You can get one at https://platform.openai.com/account/api-keys"
    )

MONGODB_URI = os.getenv("MONGODB_URI")
if not MONGODB_URI:
    raise ValueError("Please set the MONGODB_URI environment variable to your MongoDB connection string.")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "reading_room")

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise ValueError(
        "Please set the JWT_SECRET environment variable (a long random string used to sign login "
        'tokens). Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
    )
JWT_EXPIRES_HOURS = float(os.getenv("JWT_EXPIRES_HOURS", "24"))

FILE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{3,60}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
