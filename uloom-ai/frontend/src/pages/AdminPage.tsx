import { useEffect, useState } from 'react'
import * as adminApi from '../api/admin'
import { ApiError } from '../api/client'
import type { AdminUser, Document, Settings } from '../api/types'

export function AdminPage() {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [documents, setDocuments] = useState<Document[]>([])
  const [settings, setSettings] = useState<Settings | null>(null)
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
          <dl className="settings-list">
            <dt>Retrieval top-k</dt>
            <dd>{settings.retrieval_top_k}</dd>
            <dt>Chunk token size</dt>
            <dd>{settings.chunk_token_size}</dd>
            <dt>Similarity threshold</dt>
            <dd>{settings.similarity_threshold}</dd>
          </dl>
          <p className="page-status">
            Editing these isn't implemented yet on the backend (PATCH /admin/settings is still 501).
          </p>
        </section>
      )}
    </div>
  )
}
