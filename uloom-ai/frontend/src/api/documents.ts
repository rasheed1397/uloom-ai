import { apiRequest } from './client'
import type { Document } from './types'

export function listDocuments(): Promise<Document[]> {
  return apiRequest<Document[]>('/documents')
}

export function getDocument(id: string): Promise<Document> {
  return apiRequest<Document>(`/documents/${id}`)
}

export function uploadDocument(file: File): Promise<Document> {
  const formData = new FormData()
  formData.append('file', file)
  return apiRequest<Document>('/documents', { method: 'POST', formData })
}

export function deleteDocument(id: string): Promise<void> {
  return apiRequest<void>(`/documents/${id}`, { method: 'DELETE' })
}
