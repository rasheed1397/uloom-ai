import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import * as conversationsApi from '../api/conversations'
import { ApiError } from '../api/client'
import type { Conversation } from '../api/types'

export function ConversationsPage() {
  const navigate = useNavigate()
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    conversationsApi
      .listConversations()
      .then(setConversations)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Failed to load conversations.'))
      .finally(() => setLoading(false))
  }, [])

  async function handleCreate() {
    setError(null)
    setCreating(true)
    try {
      const conversation = await conversationsApi.createConversation()
      navigate(`/conversations/${conversation.id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to create conversation.')
      setCreating(false)
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>Conversations</h1>
        <button type="button" onClick={handleCreate} disabled={creating}>
          {creating ? 'Creating…' : 'New conversation'}
        </button>
      </div>
      {error && <p className="form-error">{error}</p>}
      {loading ? (
        <p className="page-status">Loading…</p>
      ) : conversations.length === 0 ? (
        <p className="page-status">No conversations yet. Start one to ask a question.</p>
      ) : (
        <ul className="conversation-list">
          {conversations.map((c) => (
            <li key={c.id}>
              <button type="button" className="conversation-item" onClick={() => navigate(`/conversations/${c.id}`)}>
                <span>{c.title}</span>
                <span className="conversation-date">{new Date(c.updated_at).toLocaleString()}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
