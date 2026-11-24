export type NoiseLevel = 'baixo' | 'moderado' | 'alto'
export type NoiseTolerance = 'baixo' | 'moderado' | 'indiferente'

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
  wheelchairRequired: boolean
  noiseTolerance: NoiseTolerance
  largeText: boolean
}

export interface ScheduledMeeting {
  id: string
  venue: VerifiedVenue
  activity: string
  status: 'confirmado' | 'concluido' | 'cancelado'
  checkedIn: boolean
  groupInterests: string[]
  satisfaction?: number
  safety?: number
}

export const VERIFIED_VENUES_DF: VerifiedVenue[] = [
  {
    placeId: 'LOC-03',
    name: 'Sephinah Casa de Chá e Cafeteria',
    amenity: 'cafe',
    kind: 'Casa de chá e café · Asa Sul',
    region: 'Asa Sul',
    address: 'CLS 403 Bloco B · Asa Sul, Brasília - DF',
    distanceKm: 1.2,
    distanceLabel: '1,2 km',
    time: 'Sáb, 15:00',
    dateDay: '28',
    dateMonth: 'NOV',
    dateWeekday: 'SÁB',
    hoursRange: '15:00 — 17:00',
    openUntil: '19h',
    rating: '4,8',
    groupSize: 5,
    tone: 'orange',
    tag: 'Mais compatível',
    vibe: 'Tranquilo e intimista',
    noiseLevel: 'baixo',
    wheelchair: 'yes',
    isPublicVerified: true,
    osmUrl: 'https://www.openstreetmap.org/node/736192840',
    osmLabel: 'OpenStreetMap #736192840',
    matchReason:
      'Ambiente silencioso com mesas espaçadas, acesso plano e alta afinidade para conversas calmas.',
    icebreakers: [
      'Qual livro, série ou podcast você recomendaria sem pensar duas vezes?',
      'Qual é o seu cantinho favorito para desacelerar em Brasília?',
      'Se pudesse aprender uma nova habilidade este ano, qual seria?',
    ],
    categories: ['cafe', 'leitura', 'conversa', 'tecnologia'],
  },
  {
    placeId: 'LOC-01',
    name: 'Ernesto Cafés Especiais',
    amenity: 'cafe',
    kind: 'Café especial · Asa Sul',
    region: 'Asa Sul',
    address: 'CLS 115 Bloco C · Asa Sul, Brasília - DF',
    distanceKm: 1.8,
    distanceLabel: '1,8 km',
    time: 'Sáb, 15:30',
    dateDay: '28',
    dateMonth: 'NOV',
    dateWeekday: 'SÁB',
    hoursRange: '15:30 — 17:30',
    openUntil: '20h',
    rating: '4,8',
    groupSize: 4,
    tone: 'yellow',
    tag: 'Mais tranquilo',
    vibe: 'Acolhedor para conversa',
    noiseLevel: 'baixo',
    wheelchair: 'yes',
    isPublicVerified: true,
    osmUrl: 'https://www.openstreetmap.org/node/482910482',
    osmLabel: 'OpenStreetMap #482910482',
    matchReason:
      'Café de referência na Asa Sul com baixo ruído, acessibilidade confirmada e ótima reputação comunitária.',
    icebreakers: [
      'Café coado, espresso ou chá: qual ritual combina mais com seu fim de semana?',
      'Que assunto de tecnologia ou cultura tem despertado sua curiosidade ultimamente?',
      'Qual foi a melhor descoberta recente que você fez pela cidade?',
    ],
    categories: ['cafe', 'leitura', 'conversa', 'tecnologia'],
  },
  {
    placeId: 'LOC-02',
    name: 'Parque da Cidade Dona Sarah Kubitschek',
    amenity: 'park',
    kind: 'Parque urbano · Asa Sul',
    region: 'Asa Sul',
    address: 'Setor de Recreação Pública Sul · Asa Sul, Brasília - DF',
    distanceKm: 2.1,
    distanceLabel: '2,1 km',
    time: 'Dom, 09:30',
    dateDay: '29',
    dateMonth: 'NOV',
    dateWeekday: 'DOM',
    hoursRange: '09:30 — 11:30',
    openUntil: '22h',
    rating: '4,7',
    groupSize: 6,
    tone: 'brown',
    tag: 'Ao ar livre',
    vibe: 'Caminhada leve e sombra',
    noiseLevel: 'moderado',
    wheelchair: 'yes',
    isPublicVerified: true,
    osmUrl: 'https://www.openstreetmap.org/way/918237412',
    osmLabel: 'OpenStreetMap #918237412',
    matchReason:
      'Pistas planas e arborizadas ideais para caminhadas leves, acessibilidade plena e convivência ao ar livre.',
    icebreakers: [
      'Você prefere começar o dia ao ar livre ou aproveitar o fim de tarde?',
      'Qual passeio na natureza mais recarrega suas energias?',
      'O que fez você decidir experimentar um encontro em grupo hoje?',
    ],
    categories: ['parque', 'caminhada', 'natureza', 'ar_livre'],
  },
  {
    placeId: 'LOC-04',
    name: 'Sebinho Livraria Café e Bistrô',
    amenity: 'library',
    kind: 'Livraria e café · Asa Norte',
    region: 'Asa Norte',
    address: 'CLN 406 Bloco C · Asa Norte, Brasília - DF',
    distanceKm: 3.4,
    distanceLabel: '3,4 km',
    time: 'Sáb, 16:00',
    dateDay: '28',
    dateMonth: 'NOV',
    dateWeekday: 'SÁB',
    hoursRange: '16:00 — 18:00',
    openUntil: '21h',
    rating: '4,7',
    groupSize: 5,
    tone: 'orange',
    tag: 'Leitura & café',
    vibe: 'Cultural e silencioso',
    noiseLevel: 'baixo',
    wheelchair: 'yes',
    isPublicVerified: true,
    osmUrl: 'https://www.openstreetmap.org/node/512834910',
    osmLabel: 'OpenStreetMap #512834910',
    matchReason:
      'Une acervo literário, mesas tranquilas e café acolhedor para debates culturais em pequenos grupos.',
    icebreakers: [
      'Qual livro marcou uma fase importante da sua vida?',
      'Você prefere descobrir obras novas por indicação de amigos ou garimpando estantes?',
      'Qual filme adaptado de livro realmente surpreendeu você?',
    ],
    categories: ['leitura', 'cultura', 'cafe', 'conversa'],
  },
  {
    placeId: 'LOC-05',
    name: 'CCBB Brasília',
    amenity: 'cultural_center',
    kind: 'Centro cultural · Asa Sul',
    region: 'Asa Sul',
    address: 'SCES Trecho 2 · Asa Sul, Brasília - DF',
    distanceKm: 4.5,
    distanceLabel: '4,5 km',
    time: 'Dom, 14:30',
    dateDay: '29',
    dateMonth: 'NOV',
    dateWeekday: 'DOM',
    hoursRange: '14:30 — 16:30',
    openUntil: '21h',
    rating: '4,8',
    groupSize: 6,
    tone: 'yellow',
    tag: 'Arte & cultura',
    vibe: 'Exposições e jardim amplo',
    noiseLevel: 'baixo',
    wheelchair: 'yes',
    isPublicVerified: true,
    osmUrl: 'https://www.openstreetmap.org/way/312456789',
    osmLabel: 'OpenStreetMap #312456789',
    matchReason:
      'Espaço público amplo, acessível e seguro com exposições gratuitas e jardins para conversar depois da visita.',
    icebreakers: [
      'Qual exposição, peça ou show inesquecível você já visitou?',
      'O que mais chama sua atenção numa obra: a história, as cores ou a técnica?',
      'Que espaço cultural de Brasília você ainda quer conhecer?',
    ],
    categories: ['cultura', 'arte', 'exposicao', 'cinema'],
  },
  {
    placeId: 'LOC-06',
    name: 'Ludoteca BGC Boardgames',
    amenity: 'cafe',
    kind: 'Café de jogos · Asa Sul',
    region: 'Asa Sul',
    address: 'CLS 310 Bloco D · Asa Sul, Brasília - DF',
    distanceKm: 2.3,
    distanceLabel: '2,3 km',
    time: 'Sáb, 18:00',
    dateDay: '28',
    dateMonth: 'NOV',
    dateWeekday: 'SÁB',
    hoursRange: '18:00 — 20:30',
    openUntil: '23h',
    rating: '4,8',
    groupSize: 5,
    tone: 'brown',
    tag: 'Descontraído',
    vibe: 'Jogos e descontração',
    noiseLevel: 'moderado',
    wheelchair: 'yes',
    isPublicVerified: true,
    osmUrl: 'https://www.openstreetmap.org/node/623910221',
    osmLabel: 'OpenStreetMap #623910221',
    matchReason:
      'Mesas amplas para jogos de tabuleiro modernos em pequenos grupos, com ambiente acolhedor e acessível.',
    icebreakers: [
      'Você prefere jogos cooperativos em equipe ou estratégia competitiva leve?',
      'Qual foi o jogo de mesa ou carta que mais rendeu boas risadas?',
      'Se pudesse inventar uma regra nova para quebrar o gelo, qual seria?',
    ],
    categories: ['jogos', 'cafe', 'conversa'],
  },
]

export function makeInitials(fullName: string): string {
  const parts = fullName.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return 'CM'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
}

export function interpretRequest(rawText: string, profile: MemberProfile): InterpretedIntent {
  const normalized = rawText.trim().toLowerCase()

  const outOfScopeKeywords = ['frete', 'caminhão', 'caminhao', 'mudança', 'mudanca', 'carreto', 'vender', 'comprar carro']
  if (outOfScopeKeywords.some((kw) => normalized.includes(kw))) {
    return {
      status: 'OUT_OF_SCOPE',
      reason:
        'Sua solicitação parece envolver um serviço comercial ou logístico fora do propósito do Bubbles. Atuamos exclusivamente para conectar pessoas em encontros presenciais sociais (3 a 8 pessoas) em locais públicos seguros de Brasília.',
      activity: 'Fora do escopo social',
      vibe: 'Indiferente',
      noiseTolerance: 'indiferente',
      when: 'Não aplicável',
      region: profile.region,
      maxRadiusKm: profile.maxRadiusKm,
      wheelchairRequired: profile.wheelchairRequired,
      targetCategory: 'cafe',
    }
  }

  const impossibleKeywords = ['patinação no gelo', 'patinacao no gelo', '03:30', '3h30', 'madrugada']
  if (impossibleKeywords.some((kw) => normalized.includes(kw))) {
    return {
      status: 'NO_RESULTS',
      reason:
        'Não encontramos nenhum Local Verificado em Brasília que atenda simultaneamente a essas restrições (ex.: funcionamento na madrugada ou estrutura inexistente na base oficial OpenStreetMap).',
      activity: 'Critérios sem correspondência no DF',
      vibe: 'Indiferente',
      noiseTolerance: profile.noiseTolerance,
      when: 'Madrugada',
      region: 'Asa Sul, Brasília',
      maxRadiusKm: profile.maxRadiusKm,
      wheelchairRequired: profile.wheelchairRequired,
      targetCategory: 'cafe',
    }
  }

  let activity = 'Café e conversa'
  let targetCategory = 'cafe'
  if (normalized.includes('parque') || normalized.includes('caminhada') || normalized.includes('ar livre') || normalized.includes('natureza')) {
    activity = 'Caminhada leve no parque'
    targetCategory = 'parque'
  } else if (normalized.includes('exposição') || normalized.includes('exposicao') || normalized.includes('museu') || normalized.includes('arte') || normalized.includes('cinema')) {
    activity = 'Exposição e conversa cultural'
    targetCategory = 'cultura'
  } else if (normalized.includes('livro') || normalized.includes('leitura') || normalized.includes('livraria')) {
    activity = 'Leitura e conversa em grupo'
    targetCategory = 'leitura'
  } else if (normalized.includes('jogo') || normalized.includes('tabuleiro')) {
    activity = 'Jogos de tabuleiro em grupo'
    targetCategory = 'jogos'
  }

  let noiseTolerance: NoiseTolerance = profile.noiseTolerance
  let vibe = 'Tranquilo e acolhedor'
  if (normalized.includes('silencioso') || normalized.includes('calmo') || normalized.includes('tranquilo') || targetCategory === 'leitura') {
    noiseTolerance = 'baixo'
    vibe = 'Tranquilo e silencioso'
  } else if (normalized.includes('descontraído') || normalized.includes('descontraido') || targetCategory === 'jogos' || targetCategory === 'parque') {
    noiseTolerance = noiseTolerance === 'baixo' ? 'baixo' : 'moderado'
    vibe = targetCategory === 'parque' ? 'Ao ar livre e leve' : 'Descontraído em grupo'
  }

  let when = 'Sábado à tarde'
  if (normalized.includes('manhã') || normalized.includes('manha')) {
    when = 'Manhã (09h — 12h)'
  } else if (normalized.includes('noite')) {
    when = 'Início da noite (18h — 21h)'
  } else if (normalized.includes('domingo')) {
    when = 'Domingo pela manhã'
  }

  let region = `${profile.region} · até ${profile.maxRadiusKm} km`
  if (normalized.includes('asa norte')) {
    region = `Asa Norte · até ${profile.maxRadiusKm} km`
  } else if (normalized.includes('asa sul')) {
    region = `Asa Sul · até ${profile.maxRadiusKm} km`
  }

  const wheelchairRequired =
    profile.wheelchairRequired ||
    normalized.includes('cadeirante') ||
    normalized.includes('acess') ||
    normalized.includes('plano') ||
    normalized.includes('rampa')

  return {
    status: 'VALID',
    activity,
    vibe,
    noiseTolerance,
    when,
    region,
    maxRadiusKm: profile.maxRadiusKm,
    wheelchairRequired,
    targetCategory,
  }
}

export function rankVenues(intent: InterpretedIntent, pageOffset = 0): VerifiedVenue[] {
  if (intent.status !== 'VALID') return []

  const eligible = VERIFIED_VENUES_DF.filter((venue) => {
    if (!venue.isPublicVerified) return false
    if (intent.wheelchairRequired && venue.wheelchair === 'no') return false
    if ((intent.noiseTolerance === 'baixo' || intent.noiseTolerance === 'moderado') && venue.noiseLevel === 'alto') {
      return false
    }
    return true
  })

  const scored = [...eligible].sort((a, b) => {
    const scoreOf = (venue: VerifiedVenue) => {
      let score = 0
      if (venue.categories.includes(intent.targetCategory)) score += 3
      if (intent.region.toLowerCase().includes(venue.region.toLowerCase())) score += 1.2
      if (intent.noiseTolerance === 'baixo' && venue.noiseLevel === 'baixo') score += 1.1
      score += 1 / (1 + venue.distanceKm / 5)
      return score
    }
    return scoreOf(b) - scoreOf(a)
  })

  if (scored.length <= 3) return scored
  const start = (pageOffset * 3) % scored.length
  const picked: VerifiedVenue[] = []
  for (let i = 0; i < 3; i += 1) {
    picked.push(scored[(start + i) % scored.length])
  }
  return picked
}
