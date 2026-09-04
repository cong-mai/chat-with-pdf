from datetime import UTC, datetime
from pathlib import Path

from flask import Blueprint, abort, g, jsonify, request, send_file
from langchain_community.document_loaders import PyMuPDFLoader

from .. import config, extensions, rag, security

documents_bp = Blueprint("documents", __name__)


@documents_bp.post("/api/documents")
@security.require_auth
def upload_document():
    file = request.files.get("file")
    if file is None or file.filename == "":
        return jsonify(error="Add a PDF before reading."), 400
    if not file.filename.lower().endswith(".pdf"):
        return jsonify(error="Only PDF files are supported."), 400

    data = file.read()
    size_mb = len(data) / (1024 * 1024)
    if size_mb > config.MAX_FILE_SIZE_MB:
        return jsonify(
            error=f"That file is too large ({size_mb:.1f} MB). The limit is {config.MAX_FILE_SIZE_MB:.0f} MB."
        ), 400

    base_name = rag._sanitize_name(Path(file.filename).stem)[:40]
    # Namespacing by content hash (not just filename) keeps two different
    # files that share a name from colliding in the same collection.
    file_id = f"{base_name}_{rag._content_hash(data)}"

    dest = config.UPLOAD_DIR / f"{file_id}.pdf"

    try:
        dest.write_bytes(data)
        documents = PyMuPDFLoader(str(dest)).load()
        if not documents:
            dest.unlink(missing_ok=True)
            return jsonify(error="Couldn't read that file."), 400

        chunks = rag._chunk_documents(documents, source_id=file_id)
        vectorstore = rag._vectorstore_for(file_id)
        vectorstore.add_documents(chunks)
    except Exception:
        config.logger.exception("Failed to index uploaded file %s", file_id)
        dest.unlink(missing_ok=True)
        return jsonify(error="Couldn't read that file."), 500

    extensions.documents_col.update_one(
        {"_id": file_id},
        {
            "$set": {
                "owner_id": g.user["id"],
                "filename": file.filename,
                "pages": len(documents),
                "chunks": len(chunks),
                "created_at": datetime.now(UTC),
            }
        },
        upsert=True,
    )

    return jsonify(
        file_id=file_id,
        filename=file.filename,
        pages=len(documents),
        chunks=len(chunks),
    )


@documents_bp.get("/api/documents")
@security.require_auth
def list_documents():
    docs = extensions.documents_col.find({"owner_id": g.user["id"]}).sort("created_at", -1)
    return jsonify(documents=[
        {
            "file_id": doc["_id"],
            "filename": doc["filename"],
            "pages": doc["pages"],
            "chunks": doc["chunks"],
            "created_at": doc["created_at"].isoformat(),
        }
        for doc in docs
    ])


@documents_bp.get("/api/documents/<file_id>/file")
@security.require_auth
def get_document_file(file_id):
    if not config.FILE_ID_RE.match(file_id):
        abort(404)
    if not extensions.documents_col.find_one({"_id": file_id, "owner_id": g.user["id"]}):
        abort(404)
    path = config.UPLOAD_DIR / f"{file_id}.pdf"
    if not path.is_file():
        abort(404)
    return send_file(path, mimetype="application/pdf")


@documents_bp.delete("/api/documents/<file_id>")
@security.require_auth
def delete_document(file_id):
    if not config.FILE_ID_RE.match(file_id):
        abort(404)
    if not extensions.documents_col.find_one({"_id": file_id, "owner_id": g.user["id"]}):
        abort(404)

    rag._vectorstore_for(file_id).delete_collection()
    path = config.UPLOAD_DIR / f"{file_id}.pdf"
    path.unlink(missing_ok=True)
    extensions.documents_col.delete_one({"_id": file_id})

    return jsonify(deleted=file_id)
