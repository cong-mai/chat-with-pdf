import { useEffect, useState } from 'react'
import { fetchDocumentBlobUrl } from '../api.js'

export default function DocumentPanel({ doc, status, onFile, token }) {
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

  return (
    <section className="doc-pane" aria-label="Document">
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
