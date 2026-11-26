import { useEffect, useState } from 'react'
import { ForgotPassword, LegalModal, Login, Signup, Welcome } from './components/AuthScreens'
import { Confirm, Home, Recommendations } from './components/DiscoveryScreens'
import { Nav, type Screen } from './components/Icons'
import { Feedback, Meeting, Meetings, PairingSlot } from './components/MeetingScreens'
import { OnboardingStyle, Preferences } from './components/OnboardingScreens'
import { Profile } from './components/ProfileScreen'
import {
  EMPTY_MEMBER_PROFILE,
  makeInitials,
  type InterpretedIntent,
  type MemberProfile,
  type ScheduledMeeting,
  type VerifiedVenue,
} from './data/bubblesData'
import {
  cancelEarly,
  confirmCheckin,
  fetchRecommendations,
  fetchZeroTurnRecommendations,
  interpretIntent,
  joinPairingSlot,
  submitFeedback,
} from './services/api'

export default function App() {
  const [screen, setScreen] = useState<Screen>('welcome')
  const [profile, setProfile] = useState<MemberProfile>(EMPTY_MEMBER_PROFILE)
  const [requestText, setRequestText] = useState('')
  const [intent, setIntent] = useState<InterpretedIntent | null>(null)
  const [recommendedVenues, setRecommendedVenues] = useState<VerifiedVenue[]>([])
  const [zeroTurnVenues, setZeroTurnVenues] = useState<VerifiedVenue[]>([])
  const [venuePageOffset, setVenuePageOffset] = useState(0)
  const [meetings, setMeetings] = useState<ScheduledMeeting[]>([])
  const [activeMeetingId, setActiveMeetingId] = useState<string | null>(null)
  const [legalTab, setLegalTab] = useState<'terms' | 'privacy' | null>(null)
  const [showNotifications, setShowNotifications] = useState(false)
  const [toast, setToast] = useState<string | null>(null)

  const notify = (msg: string) => setToast(msg)

  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(() => setToast(null), 3200)
    return () => window.clearTimeout(timer)
  }, [toast])

  useEffect(() => {
    if (screen !== 'home') return
    let active = true
    fetchZeroTurnRecommendations(profile)
      .then((venues) => {
        if (active) setZeroTurnVenues(venues)
      })
      .catch(() => {
        if (active) setZeroTurnVenues([])
      })
    return () => {
      active = false
    }
  }, [screen, profile])

  const showNav = ['home', 'pairing-slot', 'meeting', 'meetings', 'profile'].includes(screen)
  const navigate = (next: Screen) => {
    setShowNotifications(false)
    setScreen(next)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const activeMeeting = meetings.find((m) => m.id === activeMeetingId) ?? meetings[0] ?? null
  const nextUpcomingMeeting =
    meetings.find((m) => m.status === 'confirmado' || m.status === 'em_formacao') ?? null

  const handleSubmitRequest = async () => {
    try {
      const parsed = await interpretIntent(requestText, profile)
      setIntent(parsed)
      setVenuePageOffset(0)
      navigate('confirm')
    } catch {
      notify('Não foi possível interpretar o pedido: conecte o backend em /api.')
    }
  }

  const handleLoadRecommendations = async (offset = 0) => {
    if (!intent) return
    try {
      const venues = await fetchRecommendations(intent, offset)
      setRecommendedVenues(venues)
      setVenuePageOffset(offset)
      navigate('recommendations')
    } catch {
      setRecommendedVenues([])
      navigate('recommendations')
      notify('Não foi possível buscar recomendações: conecte o backend em /api.')
    }
  }

  const handleEnterPairingSlot = async (venue: VerifiedVenue, activityLabel?: string) => {
    if (profile.accountStatus === 'suspenso_temporario') {
      notify('Sua conta está pausada por No-Show. Verifique seu status na aba Perfil.')
      navigate('profile')
      return
    }
    try {
      const created = await joinPairingSlot(
        venue.placeId,
        activityLabel || intent?.activity || venue.vibe,
      )
      setMeetings((prev) => [created, ...prev])
      setActiveMeetingId(created.id)
      navigate(created.status === 'confirmado' ? 'meeting' : 'pairing-slot')
    } catch {
      notify('Não foi possível entrar no Slot de Pareamento: conecte o backend em /api.')
    }
  }

  const handleToggleCheckin = async () => {
    if (!activeMeeting) return
    try {
      const updated = await confirmCheckin(activeMeeting.id)
      setMeetings((prev) => prev.map((m) => (m.id === updated.id ? updated : m)))
      notify('Check-in Final atualizado!')
    } catch {
      notify('Não foi possível confirmar o Check-in Final: conecte o backend em /api.')
    }
  }

  const handleCompleteFeedback = async (
    satisfaction: number,
    safety: number,
    attendedCount: number,
    incident?: string,
  ) => {
    if (!activeMeeting) return
    try {
      await submitFeedback(activeMeeting.id, { satisfaction, safety, attendedCount, incident })
      setMeetings((prev) =>
        prev.map((m) =>
          m.id === activeMeeting.id
            ? { ...m, status: 'concluido', satisfaction, safety, safetyIncident: incident }
            : m,
        ),
      )
      notify('Avaliação enviada! Obrigado por contribuir com a comunidade.')
      navigate('meetings')
    } catch {
      notify('Não foi possível enviar a avaliação: conecte o backend em /api.')
    }
  }

  const handleCancelEarly = async () => {
    if (!activeMeeting) return
    try {
      await cancelEarly(activeMeeting.id)
      setMeetings((prev) =>
        prev.map((m) => (m.id === activeMeeting.id ? { ...m, status: 'cancelado' } : m)),
      )
      notify('Desistência prévia registrada sem penalidade de compromisso.')
      navigate('meetings')
    } catch {
      notify('Não foi possível registrar a desistência prévia: conecte o backend em /api.')
    }
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
            const localName = email.split('@')[0] || ''
            setProfile((curr) => ({ ...curr, name: localName, initials: makeInitials(localName) }))
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
          zeroTurnVenues={zeroTurnVenues}
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
          next={() => handleLoadRecommendations(0)}
        />
      )}

      {screen === 'recommendations' && (
        <Recommendations
          venues={recommendedVenues}
          back={() => navigate('confirm')}
          choose={(venue) => handleEnterPairingSlot(venue)}
          onMoreOptions={() => handleLoadRecommendations(venuePageOffset + 1)}
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
          onToggleCheckin={handleToggleCheckin}
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
