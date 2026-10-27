/** Browser talks to the gateway only (proxied as /api). */

const BASE = '/api'

export interface CreateSessionBody {
  target_column: string
  task_type?: string
  metric?: string
  target_score?: number
  experiment_budget?: number
  scenario?: string
  mock?: boolean
}

export interface CreateSessionResponse {
  session_id: string
  status: string
  mock: boolean
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || res.statusText)
  }
  return res.json() as Promise<T>
}

export async function createSession(body: CreateSessionBody): Promise<CreateSessionResponse> {
  return json(
    await fetch(`${BASE}/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mock: true, ...body }),
    }),
  )
}

export async function pauseSession(sessionId: string) {
  return json(await fetch(`${BASE}/sessions/${sessionId}/pause`, { method: 'POST' }))
}

export async function resumeSession(sessionId: string) {
  return json(await fetch(`${BASE}/sessions/${sessionId}/resume`, { method: 'POST' }))
}

export async function resetSession(sessionId: string) {
  return json(await fetch(`${BASE}/sessions/${sessionId}/reset`, { method: 'POST' }))
}

export function eventsUrl(sessionId: string): string {
  return `${BASE}/sessions/${sessionId}/events`
}
