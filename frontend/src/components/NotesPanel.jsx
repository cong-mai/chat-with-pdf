import { useEffect, useRef } from 'react'

export default function NotesPanel({ messages, input, onInputChange, onSubmit, asking }) {
  const logRef = useRef(null)

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [messages])

  return (
    <section className="notes-pane" aria-label="Notes">
      <div className="notes-log" ref={logRef} aria-live="polite">
        {messages.length === 0 && <p className="status">Add a PDF, then ask something about it.</p>}
        {messages.map((m, i) => (
          <div key={i} className={`note note-${m.role}`}>
            <span className="note-marker">{m.role === 'user' ? 'Q' : 'A'}</span>
            <div className="note-body">
              <span
                className={
                  m.role === 'assistant' && i === messages.length - 1
                    ? 'note-text note-text--reveal'
                    : 'note-text'
                }
              >
                {m.text}
              </span>
              {m.role === 'assistant' && m.sources?.length > 0 && (
                <div className="note-sources">
                  {m.sources.map((s, si) => (
                    <span key={si} className="source-badge" title={s.snippet}>
                      p. {s.page}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
      <form className="ask-form" onSubmit={onSubmit}>
        <input
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          placeholder="Ask something about the document"
          disabled={asking}
        />
        <button type="submit" className="primary" disabled={asking}>
          Ask
        </button>
      </form>
    </section>
  )
}
