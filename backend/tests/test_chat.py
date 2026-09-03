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


def test_chat_sends_system_instruction_and_fences_context(
    client, make_user, auth_header, sample_pdf_bytes
):
    """Bug fix: retrieved CONTEXT must not be spliced directly into a bare
    user message — a system message must instruct the model to treat it as
    untrusted data, and CONTEXT must be clearly delimited from the QUESTION."""
    import backend.app as app_module

    user = make_user("injectioncheck@example.com")
    file_id = _upload(client, auth_header, user, sample_pdf_bytes)

    with patch.object(
        app_module.openai_client.chat.completions, "create", return_value=_fake_completion()
    ) as mock_create:
        client.post(
            "/api/chat",
            json={"file_id": file_id, "message": "What color is the sky?"},
            headers=auth_header(user["token"]),
        )

    messages = mock_create.call_args.kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert "ignore" in messages[0]["content"].lower()
    assert "instructions" in messages[0]["content"].lower()
    assert messages[-1]["role"] == "user"
    assert "CONTEXT" in messages[-1]["content"]
    assert "QUESTION" in messages[-1]["content"]


def test_chat_failure_returns_generic_error_and_logs_exception(
    client, make_user, auth_header, sample_pdf_bytes, caplog
):
    """Bug fix: an OpenAI-call failure must not leak str(e) to the client and
    must be logged server-side instead."""
    import backend.app as app_module

    user = make_user("chatnoleak@example.com")
    file_id = _upload(client, auth_header, user, sample_pdf_bytes)

    with patch.object(
        app_module.openai_client.chat.completions,
        "create",
        side_effect=RuntimeError("distinct-marker-chat456"),
    ):
        with caplog.at_level("ERROR"):
            res = client.post(
                "/api/chat",
                json={"file_id": file_id, "message": "What color is the sky?"},
                headers=auth_header(user["token"]),
            )

    assert res.status_code == 500
    assert "distinct-marker-chat456" not in res.get_json()["error"]
    assert "distinct-marker-chat456" in caplog.text


def test_chat_returns_deduped_source_citations(client, make_user, auth_header, sample_pdf_bytes):
    import backend.app as app_module

    user = make_user("citationcheck@example.com")
    file_id = _upload(client, auth_header, user, sample_pdf_bytes)

    with patch.object(
        app_module.openai_client.chat.completions, "create", return_value=_fake_completion()
    ):
        res = client.post(
            "/api/chat",
            json={"file_id": file_id, "message": "What color is the sky?"},
            headers=auth_header(user["token"]),
        )

    data = res.get_json()
    assert "sources" in data
    pages = [s["page"] for s in data["sources"]]
    assert all(isinstance(p, int) and p >= 1 for p in pages)
    assert len(pages) == len(set(pages))  # deduped
    for s in data["sources"]:
        assert isinstance(s["snippet"], str) and s["snippet"]


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
