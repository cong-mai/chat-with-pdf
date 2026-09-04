"""Document ingestion and retrieval helpers: chunking, hashing, and Chroma."""

import hashlib
import re
import uuid

from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

from . import config, extensions


def _sanitize_name(name: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", name).strip("_-")
    return sanitized if sanitized else "doc"


def _content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


def _vectorstore_for(file_id: str) -> Chroma:
    return Chroma(
        persist_directory=str(config.DATA_DIR),
        collection_name=file_id,
        embedding_function=extensions.embeddings,
    )


def _chunk_documents(documents, source_id: str):
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=80)
    chunks = splitter.split_documents(documents)
    for index, chunk in enumerate(chunks):
        # source_id + index keeps repeated boilerplate text (headers,
        # footers) from colliding onto the same chunk id.
        chunk.id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{source_id}:{index}:{chunk.page_content}"))
    return chunks
