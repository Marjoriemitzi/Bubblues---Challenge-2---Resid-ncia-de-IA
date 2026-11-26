import type { ReactNode } from 'react'
import type { ScheduledMeeting } from '../data/bubblesData'

export type Screen =
  | 'welcome'
  | 'login'
  | 'forgot-password'
  | 'signup'
  | 'preferences'
  | 'onboarding-style'
  | 'home'
  | 'confirm'
  | 'recommendations'
  | 'pairing-slot'
  | 'meeting'
  | 'meetings'
  | 'feedback'
  | 'profile'

export type IconName =
  | 'arrow'
  | 'calendar'
  | 'check'
  | 'chevron'
  | 'clock'
  | 'edit'
  | 'heart'
  | 'home'
  | 'location'
  | 'menu'
  | 'mic'
  | 'people'
  | 'profile'
  | 'route'
  | 'shield'
  | 'sparkle'
  | 'star'
  | 'sun'

export function Icon({ name, size = 22 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, ReactNode> = {
    arrow: <><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="3"/><path d="M16 3v4M8 3v4M3 10h18"/></>,
    check: <path d="m5 12 4 4L19 6"/>,
    chevron: <path d="m9 18 6-6-6-6"/>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
    edit: <><path d="M13.5 6.5 17.5 10.5"/><path d="m4 20 4.2-1 10-10a2.8 2.8 0 0 0-4-4l-10 10Z"/></>,
    heart: <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8l1.1 1.1L12 21l7.8-7.5 1.1-1.1a5.5 5.5 0 0 0-.1-7.8Z"/>,
    home: <><path d="m3 11 9-8 9 8"/><path d="M5 10v10h14V10M9 20v-6h6v6"/></>,
    location: <><path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/></>,
    menu: <><path d="M4 7h16M4 12h16M4 17h16"/></>,
    mic: <><rect x="8" y="3" width="8" height="13" rx="4"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></>,
    people: <><circle cx="9" cy="8" r="3"/><path d="M3 20v-2a6 6 0 0 1 12 0v2"/><circle cx="17" cy="9" r="2.5"/><path d="M16 14a5 5 0 0 1 5 5v1"/></>,
    profile: <><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></>,
    route: <><circle cx="6" cy="19" r="2"/><circle cx="18" cy="5" r="2"/><path d="M8 19h3a3 3 0 0 0 3-3V9a4 4 0 0 1 4-4"/></>,
    shield: <><path d="M12 22s8-3.5 8-10V5l-8-3-8 3v7c0 6.5 8 10 8 10Z"/><path d="m9 12 2 2 4-5"/></>,
    sparkle: <><path d="m12 3 1.5 4.2L18 9l-4.5 1.8L12 15l-1.5-4.2L6 9l4.5-1.8Z"/><path d="m19 15 .8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8Z"/></>,
    star: <path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9Z"/>,
    sun: <><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></>,
  }

  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name]}
    </svg>
  )
}

export function Logo({ light = false }: { light?: boolean }) {
  return (
    <div className={`logo ${light ? 'logo--light' : ''}`} aria-label="Bubbles">
      <span className="logo-bubbles" aria-hidden="true"><i/><i/><i/></span>
      <span>Bubbles</span>
    </div>
  )
}

export function Stepper({ step, total = 3 }: { step: number; total?: number }) {
  return (
    <div className="stepper" aria-label={`Etapa ${step} de ${total}`}>
      {Array.from({ length: total }, (_, idx) => idx + 1).map((item) => (
        <span key={item} className={item <= step ? 'active' : ''} />
      ))}
      <small>Etapa {step} de {total}</small>
    </div>
  )
}

export function Header({
  initials,
  onProfile,
  activeMeeting,
  showNotifications,
  onToggleNotifications,
}: {
  initials: string
  onProfile: () => void
  activeMeeting: ScheduledMeeting | null
  showNotifications: boolean
  onToggleNotifications: () => void
}) {
  return (
    <header className="topbar">
      <Logo />
      <div className="topbar-actions">
        <button
          type="button"
          className="icon-button notification"
          aria-label="Notificações"
          aria-expanded={showNotifications}
          onClick={onToggleNotifications}
        >
          <span />
        </button>
        <button type="button" className="avatar" onClick={onProfile} aria-label="Abrir perfil">
          {initials}
        </button>
      </div>
      {showNotifications && (
        <aside className="notification-popover" aria-label="Notificações recentes">
          <header>
            <h2>Notificações</h2>
            <button type="button" onClick={onToggleNotifications}>Fechar</button>
          </header>
          <ul>
            {activeMeeting && activeMeeting.status === 'confirmado' ? (
              <li>
                <strong>Check-in Final disponível em breve</strong>
                <small>
                  {activeMeeting.venue.name} ({activeMeeting.venue.time}). Confirme 30 a 60 min antes para manter o quórum mínimo de 3 pessoas.
                </small>
              </li>
            ) : activeMeeting && activeMeeting.status === 'em_formacao' ? (
              <li>
                <strong>Slot de Pareamento em formação</strong>
                <small>
                  {activeMeeting.venue.name}: {activeMeeting.slotMembersCount} de 3 Membros necessários já aderiram.
                </small>
              </li>
            ) : (
              <li>
                <strong>Tudo tranquilo por aqui</strong>
                <small>Quando você entrar em um Slot de Pareamento, enviaremos avisos 24h, 2h e 30 min antes.</small>
              </li>
            )}
          </ul>
        </aside>
      )}
    </header>
  )
}

export function Nav({ current, go }: { current: Screen; go: (screen: Screen) => void }) {
  const inMeetings = current === 'meetings' || current === 'meeting' || current === 'pairing-slot'
  return (
    <nav className="bottom-nav" aria-label="Navegação principal">
      <button type="button" className={current === 'home' ? 'active' : ''} onClick={() => go('home')}><Icon name="home" /><span>Início</span></button>
      <button type="button" className={inMeetings ? 'active' : ''} onClick={() => go('meetings')}><Icon name="calendar" /><span>Encontros</span></button>
      <button type="button" className={current === 'profile' ? 'active' : ''} onClick={() => go('profile')}><Icon name="profile" /><span>Perfil</span></button>
    </nav>
  )
}
