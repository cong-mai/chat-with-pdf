import io


def _upload(client, auth_header, user, pdf_bytes, filename="notes.pdf"):
    return client.post(
        "/api/documents",
        data={"file": (io.BytesIO(pdf_bytes), filename)},
        content_type="multipart/form-data",
        headers=auth_header(user["token"]),
    )


def test_upload_requires_auth(client, sample_pdf_bytes):
    res = client.post(
        "/api/documents",
        data={"file": (io.BytesIO(sample_pdf_bytes), "notes.pdf")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 401


def test_upload_rejects_non_pdf(client, make_user, auth_header):
    user = make_user("upload1@example.com")
    res = client.post(
        "/api/documents",
        data={"file": (io.BytesIO(b"not a pdf"), "notes.txt")},
        content_type="multipart/form-data",
        headers=auth_header(user["token"]),
    )
    assert res.status_code == 400


def test_upload_success(client, make_user, auth_header, sample_pdf_bytes):
    user = make_user("upload2@example.com")
    res = _upload(client, auth_header, user, sample_pdf_bytes)
    assert res.status_code == 200
    data = res.get_json()
    assert data["file_id"]
    assert data["pages"] == 1
    assert data["chunks"] >= 1


def test_list_documents_only_shows_owner_documents(client, make_user, auth_header, sample_pdf_bytes):
    owner = make_user("owner@example.com")
    other = make_user("other@example.com")
    _upload(client, auth_header, owner, sample_pdf_bytes)

    owner_res = client.get("/api/documents", headers=auth_header(owner["token"]))
    other_res = client.get("/api/documents", headers=auth_header(other["token"]))

    assert len(owner_res.get_json()["documents"]) == 1
    assert len(other_res.get_json()["documents"]) == 0


def test_get_document_file_not_owned_returns_404(client, make_user, auth_header, sample_pdf_bytes):
    owner = make_user("fileowner@example.com")
    intruder = make_user("intruder@example.com")
    upload_res = _upload(client, auth_header, owner, sample_pdf_bytes)
    file_id = upload_res.get_json()["file_id"]

    ok = client.get(f"/api/documents/{file_id}/file", headers=auth_header(owner["token"]))
    blocked = client.get(f"/api/documents/{file_id}/file", headers=auth_header(intruder["token"]))

    assert ok.status_code == 200
    assert blocked.status_code == 404


def test_get_document_file_nonexistent_returns_404(client, make_user, auth_header):
    user = make_user("nofile@example.com")
    res = client.get("/api/documents/does-not-exist/file", headers=auth_header(user["token"]))
    assert res.status_code == 404


def test_delete_document_removes_it(client, make_user, auth_header, sample_pdf_bytes):
    import backend.app as app_module

    user = make_user("deleter@example.com")
    upload_res = _upload(client, auth_header, user, sample_pdf_bytes)
    file_id = upload_res.get_json()["file_id"]

    pdf_path = app_module.UPLOAD_DIR / f"{file_id}.pdf"
    assert pdf_path.is_file()

    del_res = client.delete(f"/api/documents/{file_id}", headers=auth_header(user["token"]))
    assert del_res.status_code == 200
    assert del_res.get_json()["deleted"] == file_id

    assert not pdf_path.is_file()
    assert app_module.documents_col.find_one({"_id": file_id}) is None

    list_res = client.get("/api/documents", headers=auth_header(user["token"]))
    assert list_res.get_json()["documents"] == []

    file_res = client.get(f"/api/documents/{file_id}/file", headers=auth_header(user["token"]))
    assert file_res.status_code == 404


def test_delete_document_not_owned_returns_404(client, make_user, auth_header, sample_pdf_bytes):
    owner = make_user("realowner@example.com")
    intruder = make_user("intruder2@example.com")
    upload_res = _upload(client, auth_header, owner, sample_pdf_bytes)
    file_id = upload_res.get_json()["file_id"]

    res = client.delete(f"/api/documents/{file_id}", headers=auth_header(intruder["token"]))
    assert res.status_code == 404

    # Confirm it wasn't actually deleted by the failed attempt.
    still_there = client.get(f"/api/documents/{file_id}/file", headers=auth_header(owner["token"]))
    assert still_there.status_code == 200


def test_delete_nonexistent_document_returns_404(client, make_user, auth_header):
    user = make_user("deleter2@example.com")
    res = client.delete("/api/documents/does-not-exist", headers=auth_header(user["token"]))
    assert res.status_code == 404


def test_upload_failure_leaves_no_orphaned_file_or_record(
    client, make_user, auth_header, sample_pdf_bytes, monkeypatch
):
    """Bug fix: an indexing failure must not leave a PDF on disk with no
    matching Mongo record (backend/app.py upload_document)."""
    import backend.app as app_module

    def _boom(*args, **kwargs):
        raise RuntimeError("indexing exploded")

    monkeypatch.setattr(app_module, "_chunk_documents", _boom)

    user = make_user("orphancheck@example.com")
    res = _upload(client, auth_header, user, sample_pdf_bytes)

    assert res.status_code == 500
    assert list(app_module.UPLOAD_DIR.iterdir()) == []
    assert app_module.documents_col.count_documents({}) == 0


def test_upload_failure_returns_generic_error_and_logs_exception(
    client, make_user, auth_header, sample_pdf_bytes, monkeypatch, caplog
):
    """Bug fix: raw exception text must not reach the client; the full
    exception must be logged server-side instead."""
    import backend.app as app_module

    def _boom(*args, **kwargs):
        raise RuntimeError("distinct-marker-xyz789")

    monkeypatch.setattr(app_module, "_chunk_documents", _boom)

    user = make_user("noleak@example.com")
    with caplog.at_level("ERROR"):
        res = _upload(client, auth_header, user, sample_pdf_bytes)

    assert res.status_code == 500
    assert "distinct-marker-xyz789" not in res.get_json()["error"]
    assert "distinct-marker-xyz789" in caplog.text
