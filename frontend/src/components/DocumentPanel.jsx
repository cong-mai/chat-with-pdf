import { useEffect, useState } from 'react'
import { fetchDocumentBlobUrl } from '../api.js'

export default function DocumentPanel({
  doc,
  documents,
  status,
  onFile,
  onSelectDocument,
  onDeleteDocument,
  token,
}) {
  const [previewUrl, setPreviewUrl] = useState(null)

  useEffect(() => {
    if (!doc) {
      setPreviewUrl(null)
      return
    }
    let objectUrl = null
    let cancelled = false
    fetchDocumentBlobUrl(doc.fileId, token).then((url) => {
      if (cancelled) {
        URL.revokeObjectURL(url)
        return
      }
      objectUrl = url
      setPreviewUrl(url)
    })
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [doc, token])

  function handleDrop(e) {
    e.preventDefault()
    const file = e.dataTransfer.files?.[0]
    if (file) onFile(file)
  }

  function handleChange(e) {
    const file = e.target.files?.[0]
    if (file) onFile(file)
  }

  function handleDelete(e, fileId) {
    e.stopPropagation()
    onDeleteDocument(fileId)
  }

  return (
    <section className="doc-pane" aria-label="Document">
      {documents.length > 0 && (
        <ul className="doc-list">
          {documents.map((entry) => (
            <li
              key={entry.file_id}
              className={`doc-list-item${doc?.fileId === entry.file_id ? ' doc-list-item--active' : ''}`}
              onClick={() => onSelectDocument(entry)}
            >
              <span className="doc-list-name">{entry.filename}</span>
              <span className="doc-list-meta">{entry.pages}p</span>
              <button
                type="button"
                className="doc-list-delete"
                aria-label={`Delete ${entry.filename}`}
                onClick={(e) => handleDelete(e, entry.file_id)}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
      <label className="dropzone" onDrop={handleDrop} onDragOver={(e) => e.preventDefault()}>
        <input type="file" accept="application/pdf" onChange={handleChange} />
        {doc ? doc.filename : 'Drop a PDF here, or choose a file'}
      </label>
      <p className="status" aria-live="polite">
        {status}
      </p>
      {previewUrl && <iframe className="preview" src={previewUrl} title={doc.filename} />}
    </section>
  )
}
