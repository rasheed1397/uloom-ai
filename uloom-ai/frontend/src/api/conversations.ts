import { apiRequest } from './client'
import type { Conversation, Message } from './types'

export function listConversations(): Promise<Conversation[]> {
  return apiRequest<Conversation[]>('/conversations')
}

export function createConversation(title?: string): Promise<Conversation> {
  return apiRequest<Conversation>('/conversations', { method: 'POST', body: { title: title ?? null } })
}

export function listMessages(conversationId: string): Promise<Message[]> {
  return apiRequest<Message[]>(`/conversations/${conversationId}/messages`)
}

export function ask(conversationId: string, question: string): Promise<Message> {
  return apiRequest<Message>(`/conversations/${conversationId}/messages`, {
    method: 'POST',
    body: { question },
  })
}
