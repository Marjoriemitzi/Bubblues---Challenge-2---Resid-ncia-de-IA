import { useEffect, useState } from 'react'
import { ForgotPassword, LegalModal, Login, Signup, Welcome } from './components/AuthScreens'
import { Confirm, Home, Recommendations } from './components/DiscoveryScreens'
import { Nav, type Screen } from './components/Icons'
import { Feedback, Meeting, Meetings, PairingSlot } from './components/MeetingScreens'
import { OnboardingStyle, Preferences } from './components/OnboardingScreens'
import { Profile } from './components/ProfileScreen'
import {
  VERIFIED_VENUES_DF,
  interpretRequest,
  makeInitials,
  rankVenues,
  type InterpretedIntent,
  type MemberProfile,
  type ScheduledMeeting,
  type VerifiedVenue,
} from './data/bubblesData'

const INITIAL_PROFILE: MemberProfile = {
  name: 'Carla Mendes',
  initials: 'CM',
  since: 'Membro em Brasília · DF',
  region: 'Asa Sul',
  maxRadiusKm: 5,
  interests: ['Cafés & conversas', 'Tecnologia', 'Livros & leitura'],
  sociability: 'ambivertido',
  conversationStyle: 'leves',
  frequency: 'semanal',
  wheelchairRequired: false,
  noiseTolerance: 'baixo',
  largeText: false,
  commitmentPoints: 82,
  noShowCount: 0,
  accountStatus: 'ativo',
}

export default function App() {
  const [screen, setScreen] = useState<Screen>('welcome')
  const [profile, setProfile] = useState<MemberProfile>(INITIAL_PROFILE)
  const [requestText, setRequestText] = useState('')
  const [intent, setIntent] = useState<InterpretedIntent>(() =>
    interpretRequest(
      'Quero um café tranquilo na Asa Sul no sábado à tarde para conversar sobre tecnologia.',
      INITIAL_PROFILE,
    ),
  )
  const [venuePageOffset, setVenuePageOffset] = useState(0)
  const [meetings, setMeetings] = useState<ScheduledMeeting[]>([
    {
      id: 'enc-inicial',
      venue: VERIFIED_VENUES_DF[0],
      activity: 'Café e conversa',
      status: 'confirmado',
      slotMembersCount: 5,
      confirmedCheckinCount: 4,
      checkedIn: false,
      groupInterests: ['Tecnologia', 'Livros & leitura', 'Cafés'],
    },
  ])
  const [activeMeetingId, setActiveMeetingId] = useState<string>('enc-inicial')
  const [legalTab, setLegalTab] = useState<'terms' | 'privacy' | null>(null)
  const [showNotifications, setShowNotifications] = useState(false)
  const [toast, setToast] = useState<string | null>(null)

  const notify = (msg: string) => setToast(msg)

  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(() => setToast(null), 3200)
    return () => window.clearTimeout(timer)
  }, [toast])

  const showNav = ['home', 'pairing-slot', 'meeting', 'meetings', 'profile'].includes(screen)
  const navigate = (next: Screen) => {
    setShowNotifications(false)
    setScreen(next)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const activeMeeting = meetings.find((m) => m.id === activeMeetingId) ?? meetings[0]
  const nextUpcomingMeeting =
    meetings.find((m) => m.status === 'confirmado' || m.status === 'em_formacao') ?? null

  const recommendedVenues = rankVenues(intent, venuePageOffset)

  const handleSubmitRequest = () => {
    const parsed = interpretRequest(requestText, profile)
    setIntent(parsed)
    setVenuePageOffset(0)
    navigate('confirm')
  }

  const handleEnterPairingSlot = (venue: VerifiedVenue, activityLabel?: string) => {
    if (profile.accountStatus === 'suspenso_temporario') {
      notify('Sua conta está pausada por No-Show. Reative ou verifique o status na aba Perfil.')
      navigate('profile')
      return
    }
    const newId = `enc-${Date.now()}`
    const created: ScheduledMeeting = {
      id: newId,
      venue,
      activity: activityLabel || intent.activity,
      status: 'em_formacao',
      slotMembersCount: 2,
      confirmedCheckinCount: 2,
      checkedIn: false,
      groupInterests: profile.interests.length ? profile.interests : ['Cafés', 'Conversa', 'Cultura'],
    }
    setMeetings((prev) => [created, ...prev])
    setActiveMeetingId(newId)
    navigate('pairing-slot')
  }

  const handleSimulateMemberJoin = () => {
    if (!activeMeeting) return
    const nextCount = Math.min(8, activeMeeting.slotMembersCount + 1)
    const reachedQuorum = nextCount >= 3
    setMeetings((prev) =>
      prev.map((m) =>
        m.id === activeMeeting.id
          ? {
              ...m,
              slotMembersCount: nextCount,
              confirmedCheckinCount: nextCount,
              status: reachedQuorum ? 'confirmado' : 'em_formacao',
            }
          : m,
      ),
    )
    if (reachedQuorum) {
      notify('Quórum mínimo atingido! Encontro confirmado e Pauta Quebra-Gelo pronta.')
      navigate('meeting')
    }
  }

  const handleSimulateLowQuorum = () => {
    if (!activeMeeting) return
    setMeetings((prev) =>
      prev.map((m) =>
        m.id === activeMeeting.id
          ? { ...m, status: 'cancelado_quorum', confirmedCheckinCount: 2 }
          : m,
      ),
    )
    notify('Encontro cancelado preventivamente para evitar encontro 1-a-1 (sem penalidade).')
  }

  const handleCompleteFeedback = (satisfaction: number, safety: number, incident?: string) => {
    setMeetings((prev) =>
      prev.map((m) =>
        m.id === activeMeeting.id
          ? { ...m, status: 'concluido', satisfaction, safety, safetyIncident: incident }
          : m,
      ),
    )
    notify(
      incident
        ? 'Avaliação e reporte de incidente enviados para moderação.'
        : 'Avaliação enviada! Obrigado por contribuir com a reputação da comunidade.',
    )
    navigate('meetings')
  }

  const handleCancelEarly = () => {
    setMeetings((prev) =>
      prev.map((m) => (m.id === activeMeeting.id ? { ...m, status: 'cancelado' } : m)),
    )
    notify('Desistência prévia registrada sem penalidade de compromisso.')
    navigate('meetings')
  }

  return (
    <div className={`app-shell ${profile.largeText ? 'large-text' : ''}`}>
      {toast && <div className="toast-banner" role="status">{toast}</div>}
      {legalTab && <LegalModal tab={legalTab} onClose={() => setLegalTab(null)} />}

      {screen === 'welcome' && (
        <Welcome
          start={() => navigate('home')}
          signup={() => navigate('signup')}
          login={() => navigate('login')}
        />
      )}

      {screen === 'login' && (
        <Login
          back={() => navigate('welcome')}
          goSignup={() => navigate('signup')}
          goForgot={() => navigate('forgot-password')}
          done={(email) => {
            const localName = email.split('@')[0] || 'Carla'
            setProfile((curr) => ({ ...curr, initials: makeInitials(localName) }))
            notify('Bem-vindo(a) de volta ao Bubbles!')
            navigate('home')
          }}
        />
      )}

      {screen === 'forgot-password' && (
        <ForgotPassword back={() => navigate('login')} onNotify={notify} />
      )}

      {screen === 'signup' && (
        <Signup
          back={() => navigate('welcome')}
          goLogin={() => navigate('login')}
          done={(name) => {
            setProfile((curr) => ({ ...curr, name, initials: makeInitials(name) }))
            navigate('preferences')
          }}
          onOpenLegal={(tab) => setLegalTab(tab)}
        />
      )}

      {screen === 'preferences' && (
        <Preferences
          initialSelected={profile.interests}
          back={() => navigate('signup')}
          done={(interests) => {
            setProfile((curr) => ({ ...curr, interests }))
            navigate('onboarding-style')
          }}
        />
      )}

      {screen === 'onboarding-style' && (
        <OnboardingStyle
          profile={profile}
          back={() => navigate('preferences')}
          done={(updates) => {
            setProfile((curr) => ({ ...curr, ...updates }))
            notify('Perfil Base salvo com seus filtros de conforto e acessibilidade.')
            navigate('home')
          }}
        />
      )}

      {screen === 'home' && (
        <Home
          profile={profile}
          request={requestText}
          onChangeRequest={setRequestText}
          activeMeeting={nextUpcomingMeeting}
          showNotifications={showNotifications}
          onToggleNotifications={() => setShowNotifications((o) => !o)}
          onNavigate={navigate}
          onProfile={() => navigate('profile')}
          onSubmit={handleSubmitRequest}
          onQuickChoose={(venue) => handleEnterPairingSlot(venue, venue.vibe)}
          onNotify={notify}
        />
      )}

      {screen === 'confirm' && (
        <Confirm
          intent={intent}
          onUpdateIntent={setIntent}
          back={() => navigate('home')}
          next={() => navigate('recommendations')}
        />
      )}

      {screen === 'recommendations' && (
        <Recommendations
          venues={recommendedVenues}
          back={() => navigate('confirm')}
          choose={(venue) => handleEnterPairingSlot(venue)}
          onMoreOptions={() => setVenuePageOffset((offset) => offset + 1)}
        />
      )}

      {screen === 'pairing-slot' && activeMeeting && (
        <PairingSlot
          profile={profile}
          meeting={activeMeeting}
          showNotifications={showNotifications}
          onToggleNotifications={() => setShowNotifications((o) => !o)}
          onNavigate={navigate}
          onProfile={() => navigate('profile')}
          onSimulateMemberJoin={handleSimulateMemberJoin}
          onSimulateLowQuorum={handleSimulateLowQuorum}
          onChooseOtherVenue={() => navigate('recommendations')}
          onCancelEarly={handleCancelEarly}
        />
      )}

      {screen === 'meeting' && activeMeeting && (
        <Meeting
          profile={profile}
          meeting={activeMeeting}
          showNotifications={showNotifications}
          onToggleNotifications={() => setShowNotifications((o) => !o)}
          onNavigate={navigate}
          onProfile={() => navigate('profile')}
          onToggleCheckin={() => {
            setMeetings((prev) =>
              prev.map((m) => (m.id === activeMeeting.id ? { ...m, checkedIn: !m.checkedIn } : m)),
            )
            notify(
              activeMeeting.checkedIn
                ? 'Check-in Final desmarcado.'
                : 'Check-in Final confirmado! Sua presença conta para o quórum mínimo.',
            )
          }}
          onCancelEarly={handleCancelEarly}
          goMeetings={() => navigate('meetings')}
          feedback={() => navigate('feedback')}
          onNotify={notify}
        />
      )}

      {screen === 'meetings' && (
        <Meetings
          profile={profile}
          meetings={meetings}
          showNotifications={showNotifications}
          onToggleNotifications={() => setShowNotifications((o) => !o)}
          onNavigate={navigate}
          onProfile={() => navigate('profile')}
          openMeeting={(id, status) => {
            setActiveMeetingId(id)
            navigate(status === 'em_formacao' || status === 'cancelado_quorum' ? 'pairing-slot' : 'meeting')
          }}
          goHome={() => navigate('home')}
        />
      )}

      {screen === 'feedback' && activeMeeting && (
        <Feedback
          venueName={activeMeeting.venue.name}
          groupSize={activeMeeting.slotMembersCount}
          done={handleCompleteFeedback}
        />
      )}

      {screen === 'profile' && (
        <Profile
          profile={profile}
          activeMeeting={nextUpcomingMeeting}
          showNotifications={showNotifications}
          onToggleNotifications={() => setShowNotifications((o) => !o)}
          onNavigate={navigate}
          onUpdateProfile={setProfile}
          onEditInterests={() => navigate('preferences')}
          onEditStyle={() => navigate('onboarding-style')}
          onOpenLegal={(tab) => setLegalTab(tab)}
        />
      )}

      {showNav && <Nav current={screen} go={navigate}/>}
    </div>
  )
}
