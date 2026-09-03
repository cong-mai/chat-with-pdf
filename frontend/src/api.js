const JSON_HEADERS = { 'Content-Type': 'application/json' }

async function parseOrThrow(res) {
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const err = new Error(data.error || 'Something went wrong.')
    err.status = res.status
    throw err
  }
  return data
}

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function register(email, password) {
  const res = await fetch('/api/auth/register', {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({ email, password }),
  })
  return parseOrThrow(res)
}

export async function login(email, password) {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({ email, password }),
  })
  return parseOrThrow(res)
}

export async function fetchMe(token) {
  const res = await fetch('/api/auth/me', { headers: authHeaders(token) })
  return parseOrThrow(res)
}

export async function uploadDocument(file, token) {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch('/api/documents', {
    method: 'POST',
    headers: authHeaders(token),
    body: formData,
  })
  return parseOrThrow(res)
}

export async function askQuestion(fileId, message, token) {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { ...JSON_HEADERS, ...authHeaders(token) },
    body: JSON.stringify({ file_id: fileId, message }),
  })
  return parseOrThrow(res)
}

export async function listDocuments(token) {
  const res = await fetch('/api/documents', { headers: authHeaders(token) })
  return parseOrThrow(res)
}

export async function deleteDocument(fileId, token) {
  const res = await fetch(`/api/documents/${fileId}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  })
  return parseOrThrow(res)
}

export async function listUsers(token) {
  const res = await fetch('/api/admin/users', { headers: authHeaders(token) })
  return parseOrThrow(res)
}

export async function setUserActive(userId, active, token) {
  const res = await fetch(`/api/admin/users/${userId}`, {
    method: 'PATCH',
    headers: { ...JSON_HEADERS, ...authHeaders(token) },
    body: JSON.stringify({ active }),
  })
  return parseOrThrow(res)
}

// <iframe src> can't send an Authorization header, so the PDF preview is
// fetched with the token and shown via an object URL instead.
export async function fetchDocumentBlobUrl(fileId, token) {
  const res = await fetch(`/api/documents/${fileId}/file`, { headers: authHeaders(token) })
  if (!res.ok) {
    const err = new Error('Could not load the document preview.')
    err.status = res.status
    throw err
  }
  const blob = await res.blob()
  return URL.createObjectURL(blob)
}
