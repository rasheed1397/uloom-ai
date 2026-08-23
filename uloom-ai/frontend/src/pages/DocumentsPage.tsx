import { useCallback, useEffect, useRef, useState } from 'react'
import * as documentsApi from '../api/documents'
import { ApiError } from '../api/client'
import type { Document } from '../api/types'

const PENDING_STATUSES = new Set(['uploaded', 'processing'])

export function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const refresh = useCallback(async () => {
    const docs = await documentsApi.listDocuments()
    setDocuments(docs)
    return docs
  }, [])

  useEffect(() => {
    refresh()
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Failed to load documents.'))
      .finally(() => setLoading(false))
  }, [refresh])

  // Poll while anything is still uploading/processing, so status updates
  // (indexed/failed) show up without a manual refresh.
  useEffect(() => {
    if (!documents.some((d) => PENDING_STATUSES.has(d.status))) {
      return
    }
    const timer = setInterval(() => {
      refresh().catch(() => {
        /* keep the last known list on a transient poll failure */
      })
    }, 3000)
    return () => clearInterval(timer)
  }, [documents, refresh])

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setError(null)
    setUploading(true)
    try {
      await documentsApi.uploadDocument(file)
      await refresh()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Upload failed.')
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  async function handleDelete(id: string) {
    setError(null)
    try {
      await documentsApi.deleteDocument(id)
      await refresh()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Delete failed.')
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>Documents</h1>
        <label className="upload-button">
          {uploading ? 'Uploading…' : 'Upload document'}
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.md,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/markdown,text/plain"
            onChange={handleUpload}
            disabled={uploading}
            hidden
          />
        </label>
      </div>
      {error && <p className="form-error">{error}</p>}
      {loading ? (
        <p className="page-status">Loading…</p>
      ) : documents.length === 0 ? (
        <p className="page-status">No documents yet. Upload one to get started.</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Filename</th>
              <th>Status</th>
              <th>Uploaded</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => (
              <tr key={doc.id}>
                <td>{doc.filename}</td>
                <td>
                  <span className={`status-badge status-${doc.status}`}>{doc.status}</span>
                  {doc.status === 'failed' && doc.status_detail && (
                    <span className="status-detail" title={doc.status_detail}>
                      ⚠
                    </span>
                  )}
                </td>
                <td>{new Date(doc.created_at).toLocaleString()}</td>
                <td>
                  <button type="button" onClick={() => handleDelete(doc.id)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
