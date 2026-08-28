import { useState, type FormEvent } from 'react'
import * as authApi from '../api/auth'
import { ApiError } from '../api/client'
import { useAuth } from '../context/AuthContext'

export function ProfilePage() {
  const { user, refreshUser } = useAuth()
  const [email, setEmail] = useState(user?.email ?? '')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSuccess(false)
    setSaving(true)
    try {
      const changes: { email?: string; password?: string } = {}
      if (user && email !== user.email) changes.email = email
      if (password) changes.password = password
      if (Object.keys(changes).length > 0) {
        await authApi.updateProfile(changes)
        await refreshUser()
      }
      setPassword('')
      setSuccess(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to update profile.')
    } finally {
      setSaving(false)
    }
  }

  if (!user) {
    return null
  }

  return (
    <div className="auth-page">
      <form className="auth-form" onSubmit={handleSubmit}>
        <h1>Your profile</h1>
        {error && <p className="form-error">{error}</p>}
        {success && <p className="page-status">Profile updated.</p>}
        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
        </label>
        <label>
          New password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            placeholder="Leave blank to keep your current password"
            autoComplete="new-password"
          />
        </label>
        <button type="submit" disabled={saving}>
          {saving ? 'Saving…' : 'Save changes'}
        </button>
      </form>
    </div>
  )
}
