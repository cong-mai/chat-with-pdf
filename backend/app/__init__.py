"""Flask app package: gunicorn and WSGI runners target `backend.app:app`.

Submodules (config, extensions, rag, rate_limit, security) are imported here
before `flask_app`/`routes` so that, by the time route modules do
`from .. import config` etc., those attributes already exist on this
partially-initialized package — see flask_app.py for the blueprint wiring.

A few names are re-exported below purely so the test suite can reach them as
`backend.app.<name>` (mocks/monkeypatches shared, mutable objects like
`users_col` or the rate-limit dicts); anything a test *rebinds* instead of
mutating in place (e.g. `config.DATA_DIR`, `rag._chunk_documents`) must be
patched through its owning submodule instead, since a copied name here
wouldn't be affected by that rebind.
"""

import time  # noqa: F401  re-exported: tests patch time.monotonic to simulate rate-limit cooldowns

from . import config, extensions, rag, rate_limit, security  # noqa: F401
from .config import MIN_SECONDS_BETWEEN_AUTH_REQUESTS  # noqa: F401
from .extensions import documents_col, mongo_client, openai_client, users_col  # noqa: F401
from .flask_app import create_app
from .rate_limit import (  # noqa: F401
    _last_chat_time_by_user,
    _last_login_time_by_ip,
    _last_register_time_by_ip,
)
from .security import _issue_token  # noqa: F401

app = create_app()
