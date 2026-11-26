import type {
  InterpretedIntent,
  MemberProfile,
  ScheduledMeeting,
  VerifiedVenue,
} from '../data/bubblesData'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api'

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  })
  if (!response.ok) {
    throw new Error(`Erro na API (${response.status}): ${response.statusText}`)
  }
  return (await response.json()) as T
}

export function interpretIntent(rawText: string, profile: MemberProfile): Promise<InterpretedIntent> {
  return requestJson<InterpretedIntent>('/intent', {
    method: 'POST',
    body: JSON.stringify({ rawText, profile }),
  })
}

export function fetchRecommendations(
  intent: InterpretedIntent,
  pageOffset = 0,
): Promise<VerifiedVenue[]> {
  return requestJson<VerifiedVenue[]>('/recommendations', {
    method: 'POST',
    body: JSON.stringify({ intent, pageOffset }),
  })
}

export function fetchZeroTurnRecommendations(profile: MemberProfile): Promise<VerifiedVenue[]> {
  return requestJson<VerifiedVenue[]>('/recommendations/zero-turn', {
    method: 'POST',
    body: JSON.stringify({ profile }),
  })
}

export function joinPairingSlot(placeId: string, activity: string): Promise<ScheduledMeeting> {
  return requestJson<ScheduledMeeting>('/meetings/slots', {
    method: 'POST',
    body: JSON.stringify({ placeId, activity }),
  })
}

export function confirmCheckin(meetingId: string): Promise<ScheduledMeeting> {
  return requestJson<ScheduledMeeting>(`/meetings/${meetingId}/checkin`, {
    method: 'POST',
  })
}

export function cancelEarly(meetingId: string): Promise<void> {
  return requestJson<void>(`/meetings/${meetingId}/cancel-early`, {
    method: 'POST',
  })
}

export function submitFeedback(
  meetingId: string,
  payload: { satisfaction: number; safety: number; attendedCount: number; incident?: string },
): Promise<void> {
  return requestJson<void>(`/meetings/${meetingId}/feedback`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
