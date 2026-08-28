import { apiRequest } from './client'
import type { AdminUser, Document, Settings, UserRole } from './types'

export function listUsers(): Promise<AdminUser[]> {
  return apiRequest<AdminUser[]>('/admin/users')
}

export function updateUser(
  userId: string,
  changes: { role?: UserRole; is_active?: boolean },
): Promise<AdminUser> {
  return apiRequest<AdminUser>(`/admin/users/${userId}`, { method: 'PATCH', body: changes })
}

export function listAllDocuments(): Promise<Document[]> {
  return apiRequest<Document[]>('/admin/documents')
}

export function deleteAnyDocument(documentId: string): Promise<void> {
  return apiRequest<void>(`/admin/documents/${documentId}`, { method: 'DELETE' })
}

export function getSettings(): Promise<Settings> {
  return apiRequest<Settings>('/admin/settings')
}

export function updateSettings(changes: Partial<Settings>): Promise<Settings> {
  return apiRequest<Settings>('/admin/settings', { method: 'PATCH', body: changes })
}
