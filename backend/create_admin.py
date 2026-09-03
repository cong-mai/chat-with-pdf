"""Create or promote an account to the admin role.

Usage:
    python backend/create_admin.py you@example.com yourpassword
"""

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient
from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def main():
    if len(sys.argv) != 3:
        print("Usage: python backend/create_admin.py <email> <password>")
        raise SystemExit(1)

    email = sys.argv[1].strip().lower()
    password = sys.argv[2]
    if len(password) < 8:
        print("Passwords need at least 8 characters.")
        raise SystemExit(1)

    mongodb_uri = os.getenv("MONGODB_URI")
    if not mongodb_uri:
        print("Please set the MONGODB_URI environment variable to your MongoDB connection string.")
        raise SystemExit(1)
    db_name = os.getenv("MONGODB_DB_NAME", "reading_room")

    client = MongoClient(mongodb_uri)
    users_col = client[db_name]["users"]
    users_col.create_index("email", unique=True)

    result = users_col.update_one(
        {"email": email},
        {
            "$set": {
                "email": email,
                "password_hash": generate_password_hash(password),
                "role": "admin",
            },
            "$setOnInsert": {
                "_id": str(uuid.uuid4()),
                "active": True,
                "created_at": datetime.now(timezone.utc),
            },
        },
        upsert=True,
    )

    if result.upserted_id:
        print(f"Created admin account for {email}.")
    else:
        print(f"Promoted {email} to admin and updated their password.")


if __name__ == "__main__":
    main()
