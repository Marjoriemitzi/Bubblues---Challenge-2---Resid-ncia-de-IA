import { useState } from 'react'
import type { MemberProfile, ScheduledMeeting } from '../data/bubblesData'
import { Header, Icon, Logo, Stepper } from './Icons'

export function PairingSlot({
  profile,
  meeting,
  showNotifications,
  onToggleNotifications,
  onProfile,
  onSimulateMemberJoin,
  onSimulateLowQuorum,
  onChooseOtherVenue,
  onCancelEarly,
}: {
  profile: MemberProfile
  meeting: ScheduledMeeting
  showNotifications: boolean
  onToggleNotifications: () => void
  onProfile: () => void
  onSimulateMemberJoin: () => void
  onSimulateLowQuorum: () => void
  onChooseOtherVenue: () => void
  onCancelEarly: () => void
}) {
  const { venue } = meeting
  const isCancelledQuorum = meeting.status === 'cancelado_quorum'

  return (
    <>
      <Header
        initials={profile.initials}
        onProfile={onProfile}
        activeMeeting={meeting}
        showNotifications={showNotifications}
        onToggleNotifications={onToggleNotifications}
      />
      <main className="page meeting-page">
        <Stepper step={3} />
        {isCancelledQuorum ? (
          <>
            <div className="success-heading">
              <span className="success-icon" style={{ background: 'var(--brown)' }}><Icon name="shield" size={32}/></span>
              <span className="eyebrow">Proteção de Quórum Mínimo</span>
              <h1>Encontro reagendado<br/><em>preventivamente</em></h1>
              <p>O Check-in Final fechou com menos de 3 Membros confirmados ({meeting.confirmedCheckinCount}/3).</p>
            </div>
            <section className="abstention-card" role="status">
              <header>
                <span className="round-icon orange"><Icon name="people" /></span>
                <h2>Nunca deixamos virar encontro 1-a-1</h2>
              </header>
              <p>
                Para sua segurança e conforto emocional, o Bubbles exige o piso absoluto de 3 confirmados. Nenhuma penalidade foi aplicada a você.
              </p>
              <button type="button" className="primary-button" onClick={onChooseOtherVenue}>
                Escolher outro Local Verificado <Icon name="arrow" />
              </button>
            </section>
          </>
        ) : (
          <>
            <div className="success-heading">
              <span className="success-icon"><Icon name="people" size={32}/></span>
              <span className="eyebrow">Slot de Pareamento em formação</span>
              <h1>Quase lá!<br/><em>Reunindo seu grupo</em></h1>
              <p>
                Assim que 3 a 8 Membros com afinidades compatíveis aderirem a este Local Verificado e turno, o Encontro é confirmado.
              </p>
            </div>

            <section className="ticket">
              <div className="ticket-date"><strong>{venue.dateDay}</strong><span>{venue.dateMonth}<br/>{venue.dateWeekday}</span></div>
              <div className="ticket-main">
                <span className="eyebrow">{meeting.activity}</span>
                <h2>{venue.name}</h2>
                <p><Icon name="clock" size={18}/> {venue.hoursRange}</p>
                <p><Icon name="location" size={18}/> {venue.address}</p>
              </div>
              <div className="ticket-group">
                <strong>{meeting.slotMembersCount} de 3 mínimos (até 8)</strong>
                <span>Afinidades: {meeting.groupInterests.slice(0, 3).join(' · ')}</span>
                <div className="progress" style={{ marginTop: '.75rem' }}>
                  <i style={{ width: `${Math.min(100, Math.round((meeting.slotMembersCount / 3) * 100))}%` }} />
                </div>
              </div>
            </section>

            <section className="checkin-banner">
              <div>
                <strong>Mediação passiva sem chat prévio</strong>
                <small>
                  Não abrimos chat antes do encontro para evitar fadiga de decisão. A Pauta Quebra-Gelo será liberada 30 min antes, após o Check-in Final.
                </small>
              </div>
              <div style={{ display: 'flex', gap: '.6rem', flexWrap: 'wrap' }}>
                <button type="button" className="primary-button" onClick={onSimulateMemberJoin}>
                  Simular adesão de Membro (+1)
                </button>
                <button type="button" className="secondary-button" onClick={onSimulateLowQuorum}>
                  Simular quórum &lt; 3
                </button>
              </div>
            </section>

            <div className="demo-links">
              <button type="button" onClick={onCancelEarly}>Desistência prévia (sem penalidade)</button>
            </div>
          </>
        )}
      </main>
    </>
  )
}

export function Meeting({
  profile,
  meeting,
  showNotifications,
  onToggleNotifications,
  onProfile,
  onToggleCheckin,
  onCancelEarly,
  goMeetings,
  feedback,
  onNotify,
}: {
  profile: MemberProfile
  meeting: ScheduledMeeting
  showNotifications: boolean
  onToggleNotifications: () => void
  onProfile: () => void
  onToggleCheckin: () => void
  onCancelEarly: () => void
  goMeetings: () => void
  feedback: () => void
  onNotify: (msg: string) => void
}) {
  const [showSafetyGuide, setShowSafetyGuide] = useState(false)
  const { venue } = meeting

  const handleDownloadCalendar = () => {
    const ics = [
      'BEGIN:VCALENDAR',
      'VERSION:2.0',
      'BEGIN:VEVENT',
      `SUMMARY:Bubbles — ${meeting.activity} (${venue.name})`,
      `LOCATION:${venue.address}`,
      `DESCRIPTION:Encontro em grupo verificado via Bubbles. Referência OSM: ${venue.osmUrl}`,
      'END:VEVENT',
      'END:VCALENDAR',
    ].join('\r\n')
    const blob = new Blob([ics], { type: 'text/calendar;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `bubbles-${venue.placeId.toLowerCase()}.ics`
    link.click()
    URL.revokeObjectURL(url)
    onNotify('Convite de calendário (.ics) baixado.')
  }

  const handleShare = async () => {
    const summary = `Vou a um encontro do Bubbles em ${venue.name} (${venue.address}), ${venue.time}. Local público verificado: ${venue.osmUrl}`
    try {
      await navigator.clipboard.writeText(summary)
      onNotify('Itinerário copiado para compartilhar com alguém de confiança.')
    } catch {
      onNotify(summary)
    }
  }

  return (
    <>
      <Header
        initials={profile.initials}
        onProfile={onProfile}
        activeMeeting={meeting}
        showNotifications={showNotifications}
        onToggleNotifications={onToggleNotifications}
      />
      <main className="page meeting-page">
        <div className="success-heading">
          <span className="success-icon"><Icon name="check" size={34}/></span>
          <span className="eyebrow">Tudo combinado</span>
          <h1>Seu encontro<br/><em>está confirmado!</em></h1>
          <p>Agora é só chegar. A gente cuida dos lembretes e da Pauta Quebra-Gelo.</p>
        </div>

        <section className="ticket">
          <div className="ticket-date"><strong>{venue.dateDay}</strong><span>{venue.dateMonth}<br/>{venue.dateWeekday}</span></div>
          <div className="ticket-main">
            <span className="eyebrow">{meeting.activity}</span>
            <h2>{venue.name}</h2>
            <p><Icon name="clock" size={18}/> {venue.hoursRange}</p>
            <p><Icon name="location" size={18}/> {venue.address}</p>
          </div>
          <div className="ticket-group">
            <div className="avatar-stack"><i>MA</i><i>LS</i><i>JR</i><i>+{Math.max(0, meeting.slotMembersCount - 3)}</i></div>
            <strong>Seu grupo tem {meeting.slotMembersCount} pessoas</strong>
            <span>{meeting.groupInterests.slice(0, 3).join(' · ')}</span>
          </div>
        </section>

        <section className="checkin-banner" aria-label="Check-in Final e quórum mínimo">
          <div>
            <strong>{meeting.checkedIn ? 'Check-in Final confirmado!' : 'Check-in Final (30 a 60 min antes)'}</strong>
            <small>
              O encontro ocorre com quórum mínimo de 3 confirmados (nunca vira encontro 1-a-1). Desistência prévia antes da janela não gera penalidade.
            </small>
          </div>
          <button type="button" className={meeting.checkedIn ? 'secondary-button' : 'primary-button'} onClick={onToggleCheckin}>
            {meeting.checkedIn ? 'Presença confirmada' : 'Confirmar Check-in Final'}
          </button>
        </section>

        <section className="icebreaker-card" aria-label="Pauta Quebra-Gelo do grupo">
          <header>
            <span className="round-icon yellow"><Icon name="sparkle"/></span>
            <div>
              <h3>Pauta Quebra-Gelo (liberada 30 min antes)</h3>
              <p>3 tópicos leves baseados nas afinidades em comum, sem expor dados individuais:</p>
            </div>
          </header>
          <ul>
            {venue.icebreakers.map((topic) => (
              <li key={topic}>{topic}</li>
            ))}
          </ul>
        </section>

        <div className="meeting-actions">
          <button type="button" className="primary-button" onClick={handleDownloadCalendar}><Icon name="calendar"/> Adicionar ao calendário</button>
          <a className="secondary-button" href={venue.osmUrl} target="_blank" rel="noreferrer"><Icon name="route"/> Como chegar (OSM)</a>
        </div>

        <section className="prepare-grid">
          <article>
            <span className="round-icon orange"><Icon name="shield"/></span>
            <div>
              <h3>Encontro seguro</h3>
              <p>Local público verificado ({venue.osmLabel}), acesso plano ({venue.wheelchair}) e ruído {venue.noiseLevel}.</p>
              <button type="button" onClick={() => setShowSafetyGuide((open) => !open)}>
                {showSafetyGuide ? 'Ocultar orientações' : 'Ver orientações'} <Icon name="chevron" size={17}/>
              </button>
            </div>
          </article>
          <article>
            <span className="round-icon yellow"><Icon name="people"/></span>
            <div>
              <h3>Compartilhe o plano</h3>
              <p>Envie os detalhes do encontro para alguém da sua confiança.</p>
              <button type="button" onClick={handleShare}>Compartilhar itinerário <Icon name="chevron" size={17}/></button>
            </div>
          </article>
        </section>

        {showSafetyGuide && (
          <section className="info-drawer" aria-label="Orientações de segurança">
            <h2>Orientações para um encontro tranquilo</h2>
            <ol>
              <li>Encontre o grupo sempre dentro do espaço público verificado ({venue.name}).</li>
              <li>Se precisar cancelar antes do Check-in Final, use a Desistência Prévia sem nenhuma penalidade.</li>
              <li>Ao final, avalie sua satisfação e sensação de segurança para melhorar as próximas recomendações.</li>
            </ol>
          </section>
        )}

        <div className="demo-links">
          <button type="button" onClick={goMeetings}>Ver meus encontros</button>
          <button type="button" onClick={feedback}>Simular avaliação pós-encontro</button>
          {meeting.status === 'confirmado' && (
            <button type="button" onClick={onCancelEarly}>Desistência prévia (sem penalidade)</button>
          )}
        </div>
      </main>
    </>
  )
}

export function Meetings({
  profile,
  meetings,
  showNotifications,
  onToggleNotifications,
  onProfile,
  openMeeting,
  goHome,
}: {
  profile: MemberProfile
  meetings: ScheduledMeeting[]
  showNotifications: boolean
  onToggleNotifications: () => void
  onProfile: () => void
  openMeeting: (id: string, status: ScheduledMeeting['status']) => void
  goHome: () => void
}) {
  const [tab, setTab] = useState<'Próximos' | 'Anteriores' | 'Cancelados'>('Próximos')
  const filtered = meetings.filter((m) => {
    if (tab === 'Próximos') return m.status === 'confirmado' || m.status === 'em_formacao'
    if (tab === 'Anteriores') return m.status === 'concluido'
    return m.status === 'cancelado' || m.status === 'cancelado_quorum'
  })
  const nextActive = meetings.find((m) => m.status === 'confirmado' || m.status === 'em_formacao') ?? null

  return (
    <>
      <Header
        initials={profile.initials}
        onProfile={onProfile}
        activeMeeting={nextActive}
        showNotifications={showNotifications}
        onToggleNotifications={onToggleNotifications}
      />
      <main className="page list-page">
        <span className="eyebrow">Sua agenda</span><h1>Meus <em>encontros</em></h1>
        <div className="tabs">
          {(['Próximos', 'Anteriores', 'Cancelados'] as const).map((item) => (
            <button type="button" key={item} className={tab === item ? 'active' : ''} onClick={() => setTab(item)}>
              {item}
            </button>
          ))}
        </div>
        {filtered.length > 0 ? (
          <div className="upcoming">
            <div style={{ display: 'grid', gap: '1rem' }}>
              {filtered.map((item) => (
                <article
                  key={item.id}
                  className="upcoming-card"
                  tabIndex={0}
                  onClick={() => openMeeting(item.id, item.status)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      openMeeting(item.id, item.status)
                    }
                  }}
                >
                  <div className="card-date"><strong>{item.venue.dateDay}</strong><span>{item.venue.dateMonth}</span></div>
                  <div>
                    <span className="status-pill">
                      {item.status === 'em_formacao'
                        ? `Slot em formação (${item.slotMembersCount}/3)`
                        : item.status === 'confirmado'
                          ? item.checkedIn
                            ? 'Check-in confirmado'
                            : 'Confirmado'
                          : item.status === 'concluido'
                            ? `Avaliado (${item.satisfaction ?? 5}/5)`
                            : item.status === 'cancelado_quorum'
                              ? 'Reagendado (quórum < 3)'
                              : 'Desistência prévia'}
                    </span>
                    <h2>{item.activity}</h2>
                    <p>{item.venue.name} · {item.venue.time}</p>
                    <div className="avatar-stack small"><i>MA</i><i>LS</i><i>JR</i><i>+{Math.max(0, item.slotMembersCount - 3)}</i></div>
                  </div>
                  <Icon name="chevron"/>
                </article>
              ))}
            </div>
            <aside className="reminder">
              <Icon name="clock"/>
              <div>
                <strong>Lembraremos você</strong>
                <p>Avisos 24h e 2h antes, além do Check-in Final 30 a 60 min antes com quórum mínimo de 3 confirmados e Pauta Quebra-Gelo.</p>
              </div>
            </aside>
          </div>
        ) : (
          <div className="empty-state">
            <span><Icon name="calendar" size={34}/></span>
            <h2>Nada por aqui ainda</h2>
            <p>Quando houver encontros nesta categoria, eles vão aparecer aqui.</p>
            <button type="button" className="primary-button" onClick={goHome}>Criar novo pedido</button>
          </div>
        )}
      </main>
    </>
  )
}

export function Feedback({
  venueName,
  groupSize,
  done,
}: {
  venueName: string
  groupSize: number
  done: (satisfaction: number, safety: number, incident?: string) => void
}) {
  const [satisfaction, setSatisfaction] = useState(0)
  const [safety, setSafety] = useState(0)
  const [attendedCount, setAttendedCount] = useState(groupSize)
  const [incident, setIncident] = useState('nenhum')

  return (
    <main className="feedback-page">
      <div className="feedback-container">
        <Logo/>
        <span className="eyebrow">Queremos te ouvir</span>
        <h1>Como foi o<br/><em>seu encontro?</em></h1>
        <p className="lead">Avalie sua experiência em {venueName}. Sua nota atualiza a reputação comunitária do local.</p>

        <section className="rating-card">
          <div className="rating-heading"><span className="round-icon orange"><Icon name="heart"/></span><div><small>Sobre a experiência</small><h2>Quanto você gostou?</h2></div></div>
          <div className="stars" aria-label="Nota de satisfação">{[1,2,3,4,5].map((star) => <button type="button" key={star} className={satisfaction >= star ? 'active' : ''} onClick={() => setSatisfaction(star)}><Icon name="star" size={34}/><span>{star}</span></button>)}</div>
        </section>

        <section className="rating-card">
          <div className="rating-heading"><span className="round-icon yellow"><Icon name="shield"/></span><div><small>Sobre o cuidado</small><h2>Você se sentiu em segurança?</h2></div></div>
          <div className="stars" aria-label="Nota de segurança">{[1,2,3,4,5].map((star) => <button type="button" key={star} className={safety >= star ? 'active' : ''} onClick={() => setSafety(star)}><Icon name="star" size={34}/><span>{star}</span></button>)}</div>
        </section>

        <section className="rating-card">
          <div className="rating-heading"><span className="round-icon orange"><Icon name="people"/></span><div><small>Presença efetiva (combate ao No-Show)</small><h2>Quantas pessoas compareceram?</h2></div></div>
          <div className="settings-chips" style={{ marginTop: '1rem' }}>
            {Array.from({ length: Math.max(3, groupSize) }, (_, i) => i + 1).map((n) => (
              <button type="button" key={n} className={attendedCount === n ? 'active' : ''} onClick={() => setAttendedCount(n)}>
                {n} {n === 1 ? 'pessoa' : 'pessoas'}
              </button>
            ))}
          </div>
          <label className="detail-editor" style={{ marginTop: '1rem', padding: 0, border: 0 }}>
            <span>Houve algum problema no local ou com o grupo?</span>
            <select value={incident} onChange={(e) => setIncident(e.target.value)}>
              <option value="nenhum">Tudo certo, local seguro e aberto</option>
              <option value="fechado">Local estava fechado ou sem acessibilidade</option>
              <option value="barulho">Ambiente muito mais barulhento que o esperado</option>
              <option value="conduta">Reportar conduta inadequada para moderação</option>
            </select>
          </label>
        </section>

        <label className="comment-field"><span>Quer contar mais? <small>Opcional</small></span><textarea placeholder="Escreva do seu jeito..."/></label>
        <label className="meet-again"><input type="checkbox"/><span><strong>Quero encontrar esse grupo de novo</strong><small>Vamos considerar isso nos próximos encontros.</small></span></label>
        <button
          type="button"
          className="primary-button full"
          disabled={!satisfaction || !safety}
          onClick={() => done(satisfaction, safety, incident === 'nenhum' ? undefined : incident)}
        >
          Enviar avaliação <Icon name="arrow"/>
        </button>
      </div>
    </main>
  )
}
