export type NoiseLevel = 'baixo' | 'moderado' | 'alto'
export type NoiseTolerance = 'baixo' | 'moderado' | 'indiferente'
export type Sociability = 'introvertido' | 'extrovertido' | 'ambivertido'
export type ConversationStyle = 'profundas' | 'leves' | 'tanto_faz'
export type MeetingFrequency = 'semanal' | 'mensal' | 'ocasional'

export interface ScoreDecomposition {
  vector: number
  distance: number
  reputation: number
  compatibility: number
  total: number
}

export interface VerifiedVenue {
  placeId: string
  name: string
  amenity: string
  kind: string
  region: string
  address: string
  distanceKm: number
  distanceLabel: string
  time: string
  dateDay: string
  dateMonth: string
  dateWeekday: string
  hoursRange: string
  openUntil: string
  rating: string
  googleRating: number
  appRating: number
  groupSize: number
  tone: 'orange' | 'yellow' | 'brown'
  tag: string
  vibe: string
  noiseLevel: NoiseLevel
  wheelchair: 'yes' | 'limited' | 'no'
  isPublicVerified: true
  osmUrl: string
  osmLabel: string
  matchReason: string
  icebreakers: [string, string, string]
  categories: string[]
  scoreDecomposition: ScoreDecomposition
}

export interface InterpretedIntent {
  status: 'VALID' | 'OUT_OF_SCOPE' | 'NO_RESULTS'
  reason?: string
  activity: string
  vibe: string
  noiseTolerance: NoiseTolerance
  when: string
  region: string
  maxRadiusKm: number
  wheelchairRequired: boolean
  targetCategory: string
}

export interface MemberProfile {
  name: string
  initials: string
  since: string
  region: string
  maxRadiusKm: number
  interests: string[]
  sociability: Sociability
  conversationStyle: ConversationStyle
  frequency: MeetingFrequency
  wheelchairRequired: boolean
  noiseTolerance: NoiseTolerance
  largeText: boolean
  commitmentPoints: number
  noShowCount: number
  accountStatus: 'ativo' | 'alerta' | 'suspenso_temporario'
}

export interface ScheduledMeeting {
  id: string
  venue: VerifiedVenue
  activity: string
  status: 'em_formacao' | 'confirmado' | 'concluido' | 'cancelado' | 'cancelado_quorum'
  slotMembersCount: number
  confirmedCheckinCount: number
  checkedIn: boolean
  groupInterests: string[]
  satisfaction?: number
  safety?: number
  safetyIncident?: string
}

export const EMPTY_MEMBER_PROFILE: MemberProfile = {
  name: '',
  initials: 'MB',
  since: 'Membro Bubbles',
  region: 'Asa Sul',
  maxRadiusKm: 5,
  interests: [],
  sociability: 'ambivertido',
  conversationStyle: 'leves',
  frequency: 'semanal',
  wheelchairRequired: false,
  noiseTolerance: 'baixo',
  largeText: false,
  commitmentPoints: 100,
  noShowCount: 0,
  accountStatus: 'ativo',
}

export function makeInitials(fullName: string): string {
  const parts = fullName.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return 'MB'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
}

export function formatWheelchairLabel(wheelchair: VerifiedVenue['wheelchair']): string {
  if (wheelchair === 'yes') return 'Acesso plano (PCD)'
  if (wheelchair === 'limited') return 'Acesso parcial'
  return 'Sem acesso plano'
}
