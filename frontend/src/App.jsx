import { useEffect, useState } from 'react'
import AdminPanel from './components/AdminPanel.jsx'
import AuthPanel from './components/AuthPanel.jsx'
import DocumentPanel from './components/DocumentPanel.jsx'
import NotesPanel from './components/NotesPanel.jsx'
import { askQuestion, deleteDocument, fetchMe, listDocuments, uploadDocument } from './api.js'

const TOKEN_KEY = 'reading_room_token'

export default function App() {
  const [token, setToken] = useState(null)
  const [user, setUser] = useState(null)
  const [checkingSession, setCheckingSession] = useState(true)
  const [view, setView] = useState('desk')

  const [documents, setDocuments] = useState([])
  const [doc, setDoc] = useState(null)
  const [status, setStatus] = useState('')
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [asking, setAsking] = useState(false)

  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_KEY)
    if (!stored) {
      setCheckingSession(false)
      return
    }
    fetchMe(stored)
      .then((data) => {
        setToken(stored)
        setUser(data.user)
      })
      .catch(() => {
        localStorage.removeItem(TOKEN_KEY)
      })
      .finally(() => setCheckingSession(false))
  }, [])

  useEffect(() => {
    if (!token) return
    refreshDocuments()
  }, [token])

  function handleAuthenticated(newToken, newUser) {
    localStorage.setItem(TOKEN_KEY, newToken)
    setToken(newToken)
    setUser(newUser)
  }

  function handleLogout() {
    localStorage.removeItem(TOKEN_KEY)
    setToken(null)
    setUser(null)
    setView('desk')
    setDocuments([])
    setDoc(null)
    setStatus('')
    setMessages([])
  }

  function handleAuthError(err) {
    if (err.status === 401) {
      handleLogout()
      return true
    }
    return false
  }

  async function refreshDocuments() {
    try {
      const data = await listDocuments(token)
      setDocuments(data.documents)
    } catch (err) {
      handleAuthError(err)
    }
  }

  async function handleFile(file) {
    setStatus('Reading the document…')
    try {
      const data = await uploadDocument(file, token)
      setDoc({ fileId: data.file_id, filename: data.filename, pages: data.pages })
      setMessages([])
      setStatus('Ready. Ask away.')
      refreshDocuments()
    } catch (err) {
      if (handleAuthError(err)) return
      setDoc(null)
      setStatus(err.message)
    }
  }

  function handleSelectDocument(entry) {
    setDoc({ fileId: entry.file_id, filename: entry.filename, pages: entry.pages })
    setMessages([])
    setStatus('Ready. Ask away.')
  }

  async function handleDeleteDocument(fileId) {
    try {
      await deleteDocument(fileId, token)
      if (doc?.fileId === fileId) {
        setDoc(null)
        setMessages([])
        setStatus('')
      }
      refreshDocuments()
    } catch (err) {
      if (handleAuthError(err)) return
      setStatus(err.message)
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    const message = input.trim()
    if (!message || asking) return

    setMessages((prev) => [...prev, { role: 'user', text: message }])
    setInput('')

    if (!doc) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: 'Add and read a PDF before asking questions.' },
      ])
      return
    }

    setAsking(true)
    try {
      const data = await askQuestion(doc.fileId, message, token)
      const text = data.answer ?? data.message ?? 'Nothing in the document answers that.'
      setMessages((prev) => [...prev, { role: 'assistant', text }])
    } catch (err) {
      if (handleAuthError(err)) return
      setMessages((prev) => [...prev, { role: 'assistant', text: err.message }])
    } finally {
      setAsking(false)
    }
  }

  if (checkingSession) {
    return <div className="app" />
  }

  return (
    <div className="app">
      <header id="header">
        <h1 className="headline">Read together.</h1>
        <p className="subline">Ask your document things.</p>
        {user && (
          <p className="session-line">
            Signed in as {user.email} ·{' '}
            <button type="button" className="link-button" onClick={() => setView('desk')}>
              Desk
            </button>
            {user.role === 'admin' && (
              <>
                {' · '}
                <button type="button" className="link-button" onClick={() => setView('admin')}>
                  Admin
                </button>
              </>
            )}
            {' · '}
            <button type="button" className="link-button" onClick={handleLogout}>
              Log out
            </button>
          </p>
        )}
      </header>

      {!user ? (
        <AuthPanel onAuthenticated={handleAuthenticated} />
      ) : view === 'admin' ? (
        <AdminPanel token={token} onAuthError={handleAuthError} />
      ) : (
        <main className="desk">
          <DocumentPanel
            doc={doc}
            documents={documents}
            status={status}
            onFile={handleFile}
            onSelectDocument={handleSelectDocument}
            onDeleteDocument={handleDeleteDocument}
            token={token}
          />
          <NotesPanel
            messages={messages}
            input={input}
            onInputChange={setInput}
            onSubmit={handleSubmit}
            asking={asking}
          />
        </main>
      )}
    </div>
  )
}
