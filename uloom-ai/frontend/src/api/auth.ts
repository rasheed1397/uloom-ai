import { apiRequest } from './client'
import type { TokenResponse, User } from './types'

export function register(email: string, password: string): Promise<TokenResponse> {
  return apiRequest<TokenResponse>('/auth/register', { method: 'POST', body: { email, password } })
}

export function login(email: string, password: string): Promise<TokenResponse> {
  return apiRequest<TokenResponse>('/auth/login', { method: 'POST', body: { email, password } })
}

export function getCurrentUser(): Promise<User> {
  return apiRequest<User>('/users/me')
}
