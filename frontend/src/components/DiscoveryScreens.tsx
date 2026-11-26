import { useEffect, useState } from 'react'
import {
  formatWheelchairLabel,
  type InterpretedIntent,
  type MemberProfile,
  type NoiseTolerance,
  type ScheduledMeeting,
  type VerifiedVenue,
} from '../data/bubblesData'
import { Header, Icon, Logo, Stepper, type IconName, type Screen } from './Icons'

interface SpeechRecognitionLike {
  lang: string
  interimResults: boolean
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null
  onerror: (() => void) | null
  onend: (() => void) | null
  start: () => void
}

export function EvidenceModal({
  venue,
  onClose,
}: {
  venue: VerifiedVenue
  onClose: () => void
}) {
  const { scoreDecomposition: sd } = venue
  const factors = [
    { label: 'Similaridade vetorial (40%)', value: sd.vector },
    { label: 'Proximidade física (25%)', value: sd.distance },
    { label: 'Reputação Google + App (15%)', value: sd.reputation },
    { label: 'Compatibilidade de tags OSM (20%)', value: sd.compatibility },
  ]

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Evidências do ranking">
      <section className="modal-card">
        <header className="modal-header">
          <div>
            <span className="eyebrow" style={{ marginBottom: '.25rem' }}>Auditoria do Ranking (Contrato 4)</span>
            <h2>{venue.name}</h2>
          </div>
          <button type="button" className="secondary-button" onClick={onClose}>Fechar</button>
        </header>
        <div className="modal-body">
          <p className="lead" style={{ fontSize: '.92rem' }}>
            Score composto: <strong>{Math.round(sd.total * 100)}%</strong> · Reputação: Google {venue.googleRating} (peso 0,4) + App {venue.appRating} (peso 0,6).
          </p>
          <div className="evidence-bars">
            {factors.map((f) => (
              <div className="evidence-row" key={f.label}>
                <div className="evidence-labels">
                  <span>{f.label}</span>
                  <strong>{f.value.toFixed(2)}</strong>
                </div>
                <div className="evidence-track">
                  <i style={{ width: `${Math.min(100, Math.round((f.value / 0.4) * 100))}%` }} />
                </div>
              </div>
            ))}
          </div>
          <div className="verified">
            <Icon name="shield" size={18} />
            <span>
              <strong>Grounding OpenStreetMap:</strong> {venue.address} · {formatWheelchairLabel(venue.wheelchair)} · ruído {venue.noiseLevel} ·{' '}
              <a className="osm-link" href={venue.osmUrl} target="_blank" rel="noreferrer">{venue.osmLabel}</a>
            </span>
          </div>
        </div>
      </section>
    </div>
  )
}

export function Home({
  profile,
  request,
  onChangeRequest,
  zeroTurnVenues,
  activeMeeting,
  showNotifications,
  onToggleNotifications,
  onNavigate,
  onProfile,
  onSubmit,
  onQuickChoose,
  onNotify,
}: {
  profile: MemberProfile
  request: string
  onChangeRequest: (value: string) => void
  zeroTurnVenues: VerifiedVenue[]
  activeMeeting: ScheduledMeeting | null
  showNotifications: boolean
  onToggleNotifications: () => void
  onNavigate: (screen: Screen) => void
  onProfile: () => void
  onSubmit: () => void
  onQuickChoose: (venue: VerifiedVenue) => void
  onNotify: (msg: string) => void
}) {
  const [listening, setListening] = useState(false)
  const firstName = profile.name.trim().split(/\s+/)[0] || 'visitante'

  const examples = [
    {
      label: 'Café tranquilo na Asa Sul',
      text: 'Quero um café tranquilo na Asa Sul no sábado à tarde para conversar sobre livros e tecnologia, com acesso para cadeirantes.',
    },
    {
      label: 'Caminhada leve no parque',
      text: 'Quero uma caminhada leve ao ar livre no Parque da Cidade pela manhã com pistas planas.',
    },
    {
      label: 'Visitar uma exposição',
      text: 'Quero visitar uma exposição cultural em local tranquilo na Asa Sul no domingo à tarde.',
    },
  ]

  const handleVoice = () => {
    const win = window as unknown as {
      SpeechRecognition?: new () => SpeechRecognitionLike
      webkitSpeechRecognition?: new () => SpeechRecognitionLike
    }
    const SpeechCtor = win.SpeechRecognition || win.webkitSpeechRecognition
    if (!SpeechCtor) {
      onNotify('Captura de voz indisponível neste navegador. Digite seu pedido abaixo.')
      return
    }
    const recognition = new SpeechCtor()
    recognition.lang = 'pt-BR'
    recognition.interimResults = false
    setListening(true)
    recognition.onresult = (event) => {
      const transcript = event.results[0]?.[0]?.transcript
      if (transcript) {
        onChangeRequest(transcript)
        onNotify('Pedido capturado por voz com sucesso.')
      }
    }
    recognition.onerror = () => {
      setListening(false)
      onNotify('Não foi possível acessar o microfone. Você pode digitar seu pedido.')
    }
    recognition.onend = () => setListening(false)
    recognition.start()
  }

  return (
    <>
      <Header
        initials={profile.initials}
        onProfile={onProfile}
        activeMeeting={activeMeeting}
        showNotifications={showNotifications}
        onToggleNotifications={onToggleNotifications}
        current="home"
        go={onNavigate}
      />
      <main className="page home-page">
        <section className="home-hero">
          <div>
            <span className="eyebrow">Olá, {firstName}</span>
            <h1>O que você gostaria<br/>de fazer <em>em boa companhia?</em></h1>
          </div>
          <div className="mini-illustration"><span /><span /><span /><Icon name="heart" size={32} /></div>
        </section>

        <section className="request-card">
          <label htmlFor="wish">Conte do seu jeito</label>
          <div className="input-wrap">
            <textarea
              id="wish"
              maxLength={500}
              value={request}
              onChange={(e) => onChangeRequest(e.target.value)}
              placeholder="Ex: Quero um café tranquilo na Asa Sul no sábado à tarde para conversar sobre livros e tecnologia..."
            />
            <button
              type="button"
              className={`mic-button ${listening ? 'listening' : ''}`}
              aria-label="Gravar pedido por voz"
              onClick={handleVoice}
            >
              <Icon name="mic" size={28}/>
              <span>{listening ? 'Ouvindo...' : 'Falar'}</span>
            </button>
          </div>
          <div className="request-bottom"><small>Seu texto não fica armazenado após a interpretação (LGPD).</small><span>{request.length}/500</span></div>
          <button type="button" className="primary-button full" onClick={onSubmit} disabled={!request.trim()}>Encontrar meu grupo <Icon name="sparkle" /></button>
        </section>

        <section className="examples">
          <h2>Ou inspire-se por aqui</h2>
          <div className="chip-row">
            {examples.map((example, index) => (
              <button type="button" key={example.label} onClick={() => onChangeRequest(example.text)}>
                <span className={`chip-icon chip-${index}`}><Icon name={index === 1 ? 'sun' : index === 2 ? 'star' : 'heart'} size={18}/></span>
                {example.label}
              </button>
            ))}
          </div>
        </section>

        <section className="zero-turn-section" aria-label="Sugestões prontas sem precisar digitar">
          <div className="zero-turn-header">
            <div>
              <span className="eyebrow" style={{ marginBottom: '.35rem' }}>Sugestões rápidas (Zero-Turn)</span>
              <h2>Para ir direto ao encontro com seu Perfil Base</h2>
            </div>
            <small>3 categorias distintas · filtradas por acessibilidade e ruído</small>
          </div>
          {zeroTurnVenues.length > 0 ? (
            <div className="zero-turn-grid">
              {zeroTurnVenues.map((venue) => (
                <article className="zero-turn-card" key={venue.placeId}>
                  <span className="venue-badge">{venue.tag}</span>
                  <h3>{venue.name}</h3>
                  <p>{venue.kind} · {venue.time}</p>
                  <small>{formatWheelchairLabel(venue.wheelchair)} · Ruído {venue.noiseLevel}</small>
                  <button type="button" className="secondary-button full" onClick={() => onQuickChoose(venue)}>
                    Entrar no grupo <Icon name="arrow" size={18}/>
                  </button>
                </article>
              ))}
            </div>
          ) : (
            <div className="info-drawer" style={{ marginTop: 0 }}>
              <p style={{ color: 'var(--muted)', fontSize: '.9rem' }}>
                Aguardando conexão com a API de recomendações para carregar locais verificados compatíveis com o seu Perfil Base.
              </p>
            </div>
          )}
        </section>

        <aside className="safety-note"><Icon name="shield" /><div><strong>Você está em um espaço seguro</strong><p>Todos os encontros acontecem em locais públicos verificados no OpenStreetMap em Brasília.</p></div></aside>
      </main>
    </>
  )
}

export function Confirm({
  intent,
  onUpdateIntent,
  back,
  next,
}: {
  intent: InterpretedIntent | null
  onUpdateIntent: (nextIntent: InterpretedIntent) => void
  back: () => void
  next: () => void
}) {
  const [editingField, setEditingField] = useState<'activity' | 'vibe' | 'when' | 'region' | null>(null)

  if (!intent) {
    return (
      <main className="flow-page">
        <div className="flow-header"><button type="button" className="back-button" onClick={back} aria-label="Voltar"><Icon name="arrow" /></button><Logo/><span /></div>
        <div className="flow-container">
          <Stepper step={1}/>
          <div className="empty-state">
            <span><Icon name="sparkle" size={34}/></span>
            <h2>Nenhuma intenção interpretada</h2>
            <p>Envie um pedido na tela inicial conectado à API de NLU para revisar os filtros extraídos.</p>
            <button type="button" className="primary-button" onClick={back}>Voltar para o início</button>
          </div>
        </div>
      </main>
    )
  }

  if (intent.status !== 'VALID') {
    const isOutOfScope = intent.status === 'OUT_OF_SCOPE'
    return (
      <main className="flow-page">
        <div className="flow-header"><button type="button" className="back-button" onClick={back} aria-label="Voltar"><Icon name="arrow" /></button><Logo/><span /></div>
        <div className="flow-container">
          <Stepper step={1}/>
          <span className="eyebrow">{isOutOfScope ? 'Fora do escopo social' : 'Sem local compatível no DF'}</span>
          <h1>Não conseguimos<br/><em>seguir com este pedido</em></h1>
          <section className="abstention-card" role="status">
            <header>
              <span className="round-icon orange"><Icon name="shield" /></span>
              <h2>Abstenção segura ativada</h2>
            </header>
            <p>{intent.reason}</p>
            <small>
              Por segurança (RNF01), o Bubbles nunca inventa locais nem recomenda espaços sem verificação ativa na base oficial OpenStreetMap.
            </small>
          </section>
          <div className="flow-actions">
            <button type="button" className="primary-button" onClick={back}>Ajustar meu pedido <Icon name="arrow"/></button>
          </div>
        </div>
      </main>
    )
  }

  const details: Array<{ key: 'activity' | 'vibe' | 'when' | 'region'; icon: IconName; label: string; value: string }> = [
    { key: 'activity', icon: 'heart', label: 'Atividade', value: intent.activity },
    {
      key: 'vibe',
      icon: 'sun',
      label: 'Clima & ruído',
      value: `${intent.vibe} (ruído ${intent.noiseTolerance})`,
    },
    { key: 'when', icon: 'calendar', label: 'Quando', value: intent.when },
    {
      key: 'region',
      icon: 'location',
      label: 'Região & acesso',
      value: `${intent.region}${intent.wheelchairRequired ? ' · Acessível (PCD)' : ''}`,
    },
  ]

  return (
    <main className="flow-page">
      <div className="flow-header"><button type="button" className="back-button" onClick={back} aria-label="Voltar"><Icon name="arrow" /></button><Logo/><span /></div>
      <div className="flow-container">
        <Stepper step={1}/>
        <span className="eyebrow">Entendemos assim</span>
        <h1>É isso que você<br/><em>está procurando?</em></h1>
        <p className="lead">Confira os detalhes extraídos do seu pedido. Toque em qualquer cartão para ajustar.</p>
        <div className="detail-grid">
          {details.map((detail) => (
            <button
              type="button"
              className="detail-card"
              key={detail.key}
              onClick={() => setEditingField((current) => (current === detail.key ? null : detail.key))}
            >
              <span className="detail-icon"><Icon name={detail.icon}/></span>
              <span><small>{detail.label}</small><strong>{detail.value}</strong></span>
              <Icon name="edit" size={18}/>
            </button>
          ))}
        </div>

        {editingField && (
          <section className="detail-editor" aria-label="Ajustar preferência do pedido">
            {editingField === 'activity' && (
              <label>
                Atividade desejada
                <input
                  type="text"
                  value={intent.activity}
                  onChange={(e) => onUpdateIntent({ ...intent, activity: e.target.value })}
                />
              </label>
            )}
            {editingField === 'vibe' && (
              <label>
                Tolerância sensorial (nível de ruído)
                <select
                  value={intent.noiseTolerance}
                  onChange={(e) =>
                    onUpdateIntent({ ...intent, noiseTolerance: e.target.value as NoiseTolerance })
                  }
                >
                  <option value="baixo">Baixo (lugares silenciosos e calmos)</option>
                  <option value="moderado">Moderado (cafés e parques comuns)</option>
                  <option value="indiferente">Indiferente</option>
                </select>
              </label>
            )}
            {editingField === 'when' && (
              <label>
                Turno preferido
                <select
                  value={intent.when}
                  onChange={(e) => onUpdateIntent({ ...intent, when: e.target.value })}
                >
                  <option value="Manhã (09h — 12h)">Manhã (09h — 12h)</option>
                  <option value="Sábado à tarde">Sábado à tarde</option>
                  <option value="Domingo pela manhã">Domingo pela manhã</option>
                  <option value="Início da noite (18h — 21h)">Início da noite (18h — 21h)</option>
                </select>
              </label>
            )}
            {editingField === 'region' && (
              <>
                <label>
                  Região em Brasília (DF)
                  <select
                    value={intent.region}
                    onChange={(e) => onUpdateIntent({ ...intent, region: e.target.value })}
                  >
                    <option value="Asa Sul · até 5 km">Asa Sul · até 5 km</option>
                    <option value="Asa Norte · até 5 km">Asa Norte · até 5 km</option>
                    <option value="Plano Piloto · até 5 km">Plano Piloto · até 5 km</option>
                  </select>
                </label>
                <label className="detail-toggle">
                  <input
                    type="checkbox"
                    checked={intent.wheelchairRequired}
                    onChange={(e) =>
                      onUpdateIntent({ ...intent, wheelchairRequired: e.target.checked })
                    }
                  />
                  <span>Exigir acessibilidade física (acesso plano / cadeira de rodas)</span>
                </label>
              </>
            )}
            <button type="button" className="secondary-button" onClick={() => setEditingField(null)}>
              Concluir ajuste
            </button>
          </section>
        )}

        <div className="privacy-inline"><Icon name="sparkle"/><p><strong>A tecnologia só ajuda a entender seu pedido.</strong> Seu texto original já foi descartado e você sempre confirma antes de seguirmos.</p></div>
        <div className="flow-actions">
          <button type="button" className="primary-button" onClick={next}>Está certinho <Icon name="check"/></button>
          <button type="button" className="secondary-button" onClick={back}>Reescrever pedido</button>
        </div>
      </div>
    </main>
  )
}

export function Recommendations({
  venues,
  back,
  choose,
  onMoreOptions,
}: {
  venues: VerifiedVenue[]
  back: () => void
  choose: (venue: VerifiedVenue) => void
  onMoreOptions: () => void
}) {
  const [selectedId, setSelectedId] = useState<string>(venues[0]?.placeId ?? '')
  const [evidenceVenue, setEvidenceVenue] = useState<VerifiedVenue | null>(null)

  useEffect(() => {
    if (venues.length > 0 && !venues.some((v) => v.placeId === selectedId)) {
      setSelectedId(venues[0].placeId)
    }
  }, [venues, selectedId])

  return (
    <main className="flow-page recommendations-page">
      {evidenceVenue && <EvidenceModal venue={evidenceVenue} onClose={() => setEvidenceVenue(null)} />}
      <div className="flow-header"><button type="button" className="back-button" onClick={back} aria-label="Voltar"><Icon name="arrow"/></button><Logo/><span /></div>
      <div className="flow-container wide">
        <Stepper step={2}/>
        <div className="results-heading">
          <div><span className="eyebrow">Locais verificados em Brasília</span><h1>Escolha seu<br/><em>próximo encontro</em></h1></div>
          <p>3 opções verificadas no OpenStreetMap, perto de você e filtradas pelas suas necessidades de conforto e acessibilidade.</p>
        </div>

        {venues.length > 0 ? (
          <>
            <div className="venue-grid">
              {venues.map((venue) => {
                const isSelected = selectedId === venue.placeId
                return (
                  <article
                    className={`venue-card ${isSelected ? 'selected' : ''}`}
                    key={venue.placeId}
                    tabIndex={0}
                    onClick={() => setSelectedId(venue.placeId)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        setSelectedId(venue.placeId)
                      }
                    }}
                  >
                    <div className={`venue-visual ${venue.tone}`}>
                      <span className="venue-tag">{venue.tag}</span>
                      <div className="map-lines"><i/><i/><i/></div>
                      <span className="map-pin"><Icon name="location" size={24}/></span>
                    </div>
                    <div className="venue-content">
                      <div className="venue-title"><div><h2>{venue.name}</h2><p>{venue.kind}</p></div><span><Icon name="star" size={15}/>{venue.rating}</span></div>
                      <div className="venue-facts">
                        <span><Icon name="calendar" size={17}/>{venue.time}</span>
                        <span><Icon name="route" size={17}/>{venue.distanceLabel}</span>
                        <span><Icon name="people" size={17}/>{venue.groupSize} pessoas (3 a 8)</span>
                      </div>
                      <div className="venue-badges">
                        <span className="venue-badge">{formatWheelchairLabel(venue.wheelchair)}</span>
                        <span className="venue-badge">Ruído {venue.noiseLevel}</span>
                      </div>
                      <div className="verified">
                        <Icon name="shield" size={18}/>
                        <span>
                          <strong>Local público verificado</strong> · aberto até {venue.openUntil} ·{' '}
                          <a
                            className="osm-link"
                            href={venue.osmUrl}
                            target="_blank"
                            rel="noreferrer"
                            onClick={(e) => e.stopPropagation()}
                          >
                            {venue.osmLabel}
                          </a>
                        </span>
                      </div>
                      <p className="match-reason"><Icon name="sparkle" size={18}/> {venue.matchReason}</p>
                      <div style={{ display: 'grid', gap: '.55rem' }}>
                        <button
                          type="button"
                          className={isSelected ? 'primary-button full' : 'secondary-button full'}
                          onClick={(event) => {
                            event.stopPropagation()
                            setSelectedId(venue.placeId)
                            choose(venue)
                          }}
                        >
                          Entrar no Slot de Pareamento <Icon name="arrow"/>
                        </button>
                        <button
                          type="button"
                          className="text-button"
                          style={{ fontSize: '.76rem' }}
                          onClick={(event) => {
                            event.stopPropagation()
                            setEvidenceVenue(venue)
                          }}
                        >
                          Ver transparência do score ({Math.round(venue.scoreDecomposition.total * 100)}%)
                        </button>
                      </div>
                    </div>
                  </article>
                )
              })}
            </div>
            <button type="button" className="text-button centered" onClick={onMoreOptions}>
              Ver outras opções verificadas no DF
            </button>
          </>
        ) : (
          <div className="empty-state">
            <span><Icon name="location" size={34}/></span>
            <h2>Nenhum local retornado pela API</h2>
            <p>Conecte o motor de busca híbrida (PostGIS + pgvector) ou ajuste os filtros do pedido.</p>
            <button type="button" className="primary-button" onClick={back}>Voltar e ajustar</button>
          </div>
        )}
      </div>
    </main>
  )
}
