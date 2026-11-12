/** OTP authentication and authenticated student-profile API. */
import { apiFetch, setAccessToken } from './client'

export type SessionUser = {
  id: string
  phone: string
  name: string | null
  role: 'user' | 'admin'
  selected_grade: number | null
}

type TokenResponse = {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  user: SessionUser
}

export async function requestOtp(phone: string): Promise<void> {
  await apiFetch<{ status: 'sent' }>('/auth/otp/request', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone }),
  })
}

export async function verifyOtp(phone: string, code: string): Promise<SessionUser> {
  const response = await apiFetch<TokenResponse>('/auth/otp/verify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone, code }),
  })
  setAccessToken(response.access_token)
  return response.user
}

export async function getMyProfile(): Promise<SessionUser> {
  return apiFetch<SessionUser>('/profile/me')
}

export async function updateSelectedGrade(selectedGrade: number): Promise<SessionUser> {
  return apiFetch<SessionUser>('/profile/me/grade', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ selected_grade: selectedGrade }),
  })
}

export async function logout(): Promise<void> {
  try {
    await apiFetch<void>('/auth/logout', { method: 'POST' })
  } finally {
    setAccessToken(null)
  }
}
