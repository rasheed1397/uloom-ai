import { useEffect, useState, type FormEvent } from 'react'
import * as adminApi from '../api/admin'
import { ApiError } from '../api/client'
import type { AdminUser, Document, Settings } from '../api/types'

export function AdminPage() {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [documents, setDocuments] = useState<Document[]>([])
  const [settings, setSettings] = useState<Settings | null>(null)
  const [settingsForm, setSettingsForm] = useState({
    retrieval_top_k: '',
    chunk_token_size: '',
    similarity_threshold: '',
  })
  const [savingSettings, setSavingSettings] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function refresh() {
    const [u, d, s] = await Promise.all([
      adminApi.listUsers(),
      adminApi.listAllDocuments(),
      adminApi.getSettings(),
    ])
    setUsers(u)
    setDocuments(d)
    setSettings(s)
    setSettingsForm({
      retrieval_top_k: String(s.retrieval_top_k),
      chunk_token_size: String(s.chunk_token_size),
      similarity_threshold: String(s.similarity_threshold),
    })
  }

  useEffect(() => {
    refresh()
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Failed to load admin data.'))
      .finally(() => setLoading(false))
  }, [])

  async function handleToggleActive(user: AdminUser) {
    setError(null)
    try {
      await adminApi.updateUser(user.id, { is_active: !user.is_active })
      await refresh()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to update user.')
    }
  }

  async function handleDeleteDocument(id: string) {
    setError(null)
    try {
      await adminApi.deleteAnyDocument(id)
      await refresh()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to delete document.')
    }
  }

  async function handleSaveSettings(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSavingSettings(true)
    try {
      await adminApi.updateSettings({
        retrieval_top_k: Number(settingsForm.retrieval_top_k),
        chunk_token_size: Number(settingsForm.chunk_token_size),
        similarity_threshold: Number(settingsForm.similarity_threshold),
      })
      await refresh()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to update settings.')
    } finally {
      setSavingSettings(false)
    }
  }

  if (loading) {
    return <p className="page-status">Loading…</p>
  }

  return (
    <div className="page">
      <h1>Admin</h1>
      {error && <p className="form-error">{error}</p>}

      <section>
        <h2>Users</h2>
        <table className="data-table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Role</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.email}</td>
                <td>{u.role}</td>
                <td>{u.is_active ? 'Active' : 'Disabled'}</td>
                <td>
                  <button type="button" onClick={() => handleToggleActive(u)}>
                    {u.is_active ? 'Disable' : 'Enable'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h2>Documents</h2>
        <table className="data-table">
          <thead>
            <tr>
              <th>Filename</th>
              <th>Status</th>
              <th>Owner</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {documents.map((d) => (
              <tr key={d.id}>
                <td>{d.filename}</td>
                <td>{d.status}</td>
                <td>{d.owner_id.slice(0, 8)}…</td>
                <td>
                  <button type="button" onClick={() => handleDeleteDocument(d.id)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {settings && (
        <section>
          <h2>Settings</h2>
          <form className="settings-form" onSubmit={handleSaveSettings}>
            <label>
              Retrieval top-k
              <input
                type="number"
                min={1}
                step={1}
                value={settingsForm.retrieval_top_k}
                onChange={(e) =>
                  setSettingsForm((f) => ({ ...f, retrieval_top_k: e.target.value }))
                }
                required
              />
            </label>
            <label>
              Chunk token size
              <input
                type="number"
                min={1}
                step={1}
                value={settingsForm.chunk_token_size}
                onChange={(e) =>
                  setSettingsForm((f) => ({ ...f, chunk_token_size: e.target.value }))
                }
                required
              />
            </label>
            <label>
              Similarity threshold
              <input
                type="number"
                min={0}
                max={1}
                step={0.01}
                value={settingsForm.similarity_threshold}
                onChange={(e) =>
                  setSettingsForm((f) => ({ ...f, similarity_threshold: e.target.value }))
                }
                required
              />
            </label>
            <button type="submit" disabled={savingSettings}>
              {savingSettings ? 'Saving…' : 'Save settings'}
            </button>
          </form>
          <p className="page-status">Takes effect immediately — no deployment needed.</p>
        </section>
      )}
    </div>
  )
}
