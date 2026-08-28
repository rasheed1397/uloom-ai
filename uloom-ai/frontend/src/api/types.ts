// Mirrors app/schemas/*.py and the inline response models in app/api/routers/*.py.
// Kept hand-written rather than generated for now — see frontend/README.md.

export type UserRole = 'standard' | 'admin'

export interface User {
  id: string
  email: string
  role: UserRole
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

export type DocumentStatus = 'uploaded' | 'processing' | 'indexed' | 'failed'

export interface Document {
  id: string
  owner_id: string
  filename: string
  mime_type: string
  status: DocumentStatus
  status_detail: string | null
  created_at: string
}

export interface Conversation {
  id: string
  user_id: string
  title: string
  created_at: string
  updated_at: string
}

export interface Citation {
  chunk_id: string
  document_id: string
  source_location: Record<string, unknown>
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations: Citation[]
}

export interface AdminUser {
  id: string
  email: string
  role: UserRole
  is_active: boolean
  created_at: string
}

export interface Settings {
  retrieval_top_k: number
  chunk_token_size: number
  similarity_threshold: number
  retention_days: number
}
