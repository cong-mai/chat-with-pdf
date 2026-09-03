import io
from types import SimpleNamespace
from unittest.mock import patch


def _upload(client, auth_header, user, pdf_bytes, filename="notes.pdf"):
    res = client.post(
        "/api/documents",
        data={"file": (io.BytesIO(pdf_bytes), filename)},
        content_type="multipart/form-data",
        headers=auth_header(user["token"]),
    )
    return res.get_json()["file_id"]


def _fake_completion(answer="The sky is blue."):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=answer))])


def test_chat_requires_auth(client):
    res = client.post("/api/chat", json={"file_id": "x", "message": "hi"})
    assert res.status_code == 401


def test_chat_without_document_rejected(client, make_user, auth_header):
    user = make_user("chatnodoc@example.com")
    res = client.post(
        "/api/chat",
        json={"file_id": "does-not-exist", "message": "hi"},
        headers=auth_header(user["token"]),
    )
    assert res.status_code == 400


def test_chat_empty_message_rejected(client, make_user, auth_header, sample_pdf_bytes):
    user = make_user("chatempty@example.com")
    file_id = _upload(client, auth_header, user, sample_pdf_bytes)
    res = client.post(
        "/api/chat", json={"file_id": file_id, "message": "   "}, headers=auth_header(user["token"])
    )
    assert res.status_code == 400


def test_chat_happy_path(client, make_user, auth_header, sample_pdf_bytes):
    import backend.app as app_module

    user = make_user("chatter@example.com")
    file_id = _upload(client, auth_header, user, sample_pdf_bytes)

    with patch.object(
        app_module.openai_client.chat.completions, "create", return_value=_fake_completion()
    ) as mock_create:
        res = client.post(
            "/api/chat",
            json={"file_id": file_id, "message": "What color is the sky?"},
            headers=auth_header(user["token"]),
        )

    assert res.status_code == 200
    assert res.get_json()["answer"] == "The sky is blue."
    mock_create.assert_called_once()


def test_chat_rate_limited_on_rapid_requests(client, make_user, auth_header, sample_pdf_bytes):
    import backend.app as app_module

    user = make_user("ratelimited@example.com")
    file_id = _upload(client, auth_header, user, sample_pdf_bytes)

    with patch.object(
        app_module.openai_client.chat.completions, "create", return_value=_fake_completion()
    ):
        first = client.post(
            "/api/chat",
            json={"file_id": file_id, "message": "first question"},
            headers=auth_header(user["token"]),
        )
        second = client.post(
            "/api/chat",
            json={"file_id": file_id, "message": "second question"},
            headers=auth_header(user["token"]),
        )

    assert first.status_code == 200
    assert second.status_code == 429


def test_chat_not_rate_limited_across_different_users(client, make_user, auth_header):
    import backend.app as app_module
    import fitz

    def _pdf_with_text(text):
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), text)
        data = doc.tobytes()
        doc.close()
        return data

    user_a = make_user("usera@example.com")
    user_b = make_user("userb@example.com")
    # Distinct content per user so their content-hash-derived file_ids differ
    # (identical content from two users would collide onto the same document).
    file_id_a = _upload(client, auth_header, user_a, _pdf_with_text("Document A content."), "a.pdf")
    file_id_b = _upload(client, auth_header, user_b, _pdf_with_text("Document B content."), "b.pdf")

    with patch.object(
        app_module.openai_client.chat.completions, "create", return_value=_fake_completion()
    ):
        res_a = client.post(
            "/api/chat",
            json={"file_id": file_id_a, "message": "question"},
            headers=auth_header(user_a["token"]),
        )
        res_b = client.post(
            "/api/chat",
            json={"file_id": file_id_b, "message": "question"},
            headers=auth_header(user_b["token"]),
        )

    assert res_a.status_code == 200
    assert res_b.status_code == 200
