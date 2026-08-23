import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useParams } from 'react-router-dom'
import * as conversationsApi from '../api/conversations'
import { ApiError } from '../api/client'
import type { Message } from '../api/types'

export function ConversationDetailPage() {
  const { conversationId } = useParams<{ conversationId: string }>()
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(true)
  const [question, setQuestion] = useState('')
  const [asking, setAsking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!conversationId) return
    conversationsApi
      .listMessages(conversationId)
      .then(setMessages)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Failed to load messages.'))
      .finally(() => setLoading(false))
  }, [conversationId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!conversationId || !question.trim()) return
    const asked = question
    setQuestion('')
    setError(null)
    setAsking(true)
    // Optimistic: the backend persists the question too, but showing it
    // immediately (rather than waiting for the full round trip) keeps the
    // chat feeling responsive.
    setMessages((prev) => [
      ...prev,
      { id: `pending-${Date.now()}`, role: 'user', content: asked, citations: [] },
    ])
    try {
      const answer = await conversationsApi.ask(conversationId, asked)
      setMessages((prev) => [...prev, answer])
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to get an answer.')
    } finally {
      setAsking(false)
    }
  }

  if (loading) {
    return <p className="page-status">Loading…</p>
  }

  return (
    <div className="page chat-page">
      <h1>Conversation</h1>
      <div className="chat-messages">
        {messages.length === 0 && <p className="page-status">Ask a question about your documents.</p>}
        {messages.map((m) => (
          <div key={m.id} className={`chat-message chat-message-${m.role}`}>
            <p>{m.content}</p>
            {m.citations.length > 0 && (
              <ul className="citations">
                {m.citations.map((c, i) => (
                  <li key={i}>Source: document {c.document_id.slice(0, 8)}…</li>
                ))}
              </ul>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
      {error && <p className="form-error">{error}</p>}
      <form className="chat-input" onSubmit={handleSubmit}>
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question about your documents…"
          disabled={asking}
        />
        <button type="submit" disabled={asking || !question.trim()}>
          {asking ? 'Asking…' : 'Ask'}
        </button>
      </form>
    </div>
  )
}
