"""Third-party clients and DB handles, built once at import time.

Re-instantiating the embedding model or DB clients per-request would hit
Hugging Face Hub / MongoDB on every call — slow, and a single network hiccup
would break every request.
"""

from langchain_huggingface import HuggingFaceEmbeddings
from openai import OpenAI
from pymongo import MongoClient

from . import config

openai_client = OpenAI(api_key=config.OPENAI_API_KEY)

mongo_client = MongoClient(config.MONGODB_URI)
db = mongo_client[config.MONGODB_DB_NAME]
users_col = db["users"]
documents_col = db["documents"]
users_col.create_index("email", unique=True)
documents_col.create_index("owner_id")

embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
