from __future__ import annotations

import io


def _upload_pdf(client, token: str) -> str:
    file_content = b"%PDF-1.4\n1 0 obj << /Type /Catalog >>\n"
    files = {"file": ("sample.pdf", io.BytesIO(file_content), "application/pdf")}
    response = client.post(
        "/api/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=files,
    )
    assert response.status_code == 201
    return response.json()["document_id"]


def test_upload_document(client):
    token = "user-test"
    document_id = _upload_pdf(client, token)

    list_resp = client.get(
        "/api/documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_resp.status_code == 200
    documents = list_resp.json()
    assert len(documents) == 1
    assert documents[0]["id"] == document_id


def test_delete_document(client):
    token = "user-delete"
    document_id = _upload_pdf(client, token)

    delete_resp = client.delete(
        f"/api/documents/{document_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_resp.status_code == 204

    list_resp = client.get(
        "/api/documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_resp.status_code == 200
    documents = list_resp.json()
    assert documents == []

    embedder = client.app.state.test_embedder
    assert (document_id, token) in embedder.deleted

