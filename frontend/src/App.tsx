import { useEffect, useState, type CSSProperties, type ReactNode } from 'react'
import {
  VERIFIED_VENUES_DF,
  interpretRequest,
  makeInitials,
  rankVenues,
  type InterpretedIntent,
  type MemberProfile,
  type NoiseTolerance,
  type ScheduledMeeting,
  type VerifiedVenue,
} from './data/bubblesData'

type Screen =
  | 'welcome'
  | 'signup'
  | 'preferences'
  | 'home'
  | 'confirm'
  | 'recommendations'
  | 'meeting'
  | 'meetings'
  | 'feedback'
  | 'profile'

type IconName =
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

interface SpeechRecognitionLike {
  lang: string
  interimResults: boolean
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null
  onerror: (() => void) | null
  onend: (() => void) | null
  start: () => void
}

function Icon({ name, size = 22 }: { name: IconName; size?: number }) {
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

function Logo({ light = false }: { light?: boolean }) {
  return (
    <div className={`logo ${light ? 'logo--light' : ''}`} aria-label="Bubbles">
      <span className="logo-bubbles" aria-hidden="true"><i/><i/><i/></span>
      <span>Bubbles</span>
    </div>
  )
}

function Header({
  initials,
  onProfile,
  activeMeeting,
}: {
  initials: string
  onProfile: () => void
  activeMeeting: ScheduledMeeting | null
}) {
  const [showNotifications, setShowNotifications] = useState(false)

  return (
    <header className="topbar">
      <Logo />
      <div className="topbar-actions">
        <button
          type="button"
          className="icon-button notification"
          aria-label="Notificações"
          aria-expanded={showNotifications}
          onClick={() => setShowNotifications((open) => !open)}
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
            <button type="button" onClick={() => setShowNotifications(false)}>Fechar</button>
          </header>
          <ul>
            {activeMeeting && activeMeeting.status === 'confirmado' ? (
              <li>
                <strong>Check-in Final disponível em breve</strong>
                <small>
                  {activeMeeting.venue.name} ({activeMeeting.venue.time}). Confirme 30 a 60 min antes para manter o quórum mínimo de 3 pessoas.
                </small>
              </li>
            ) : (
              <li>
                <strong>Tudo tranquilo por aqui</strong>
                <small>Quando você agendar um encontro, enviaremos avisos 24h, 2h e 30 min antes.</small>
              </li>
            )}
          </ul>
        </aside>
      )}
    </header>
  )
}

function Nav({ current, go }: { current: Screen; go: (screen: Screen) => void }) {
  return (
    <nav className="bottom-nav" aria-label="Navegação principal">
      <button type="button" className={current === 'home' ? 'active' : ''} onClick={() => go('home')}><Icon name="home" /><span>Início</span></button>
      <button type="button" className={current === 'meetings' || current === 'meeting' ? 'active' : ''} onClick={() => go('meetings')}><Icon name="calendar" /><span>Encontros</span></button>
      <button type="button" className={current === 'profile' ? 'active' : ''} onClick={() => go('profile')}><Icon name="profile" /><span>Perfil</span></button>
    </nav>
  )
}

function Stepper({ step }: { step: number }) {
  return (
    <div className="stepper" aria-label={`Etapa ${step} de 3`}>
      {[1, 2, 3].map((item) => <span key={item} className={item <= step ? 'active' : ''} />)}
      <small>Etapa {step} de 3</small>
    </div>
  )
}

function Welcome({ start, signup }: { start: () => void; signup: () => void }) {
  const [showHowItWorks, setShowHowItWorks] = useState(false)

  return (
    <main className="welcome">
      <section className="welcome-art">
        <Logo light />
        <div className="orb orb-one" /><div className="orb orb-two" /><div className="orb orb-three" />
        <img src="/assets/bubbles-symbol.webp" alt="Pessoas conectadas por atividades como música, cultura, jogos e cafés" />
        <p>Conexões que aproximam</p>
      </section>
      <section className="welcome-copy">
        <div className="welcome-inner">
          <span className="eyebrow">Encontros reais em Brasília, do seu jeito</span>
          <h1>Gente nova.<br/><em>Boas histórias.</em></h1>
          <p className="lead">A gente forma o grupo e cuida dos detalhes. Você só precisa aparecer.</p>
          <div className="welcome-actions">
            <button type="button" className="primary-button" onClick={start}>Quero começar <Icon name="arrow" /></button>
            <button type="button" className="secondary-button" onClick={signup}><Icon name="profile" /> Criar minha conta</button>
          </div>
          <button type="button" className="text-button" onClick={() => setShowHowItWorks((open) => !open)}>
            {showHowItWorks ? 'Ocultar como funciona' : 'Ver como funciona'}
          </button>
          {showHowItWorks && (
            <section className="info-drawer" aria-label="Como funciona o Bubbles">
              <h2>Como funciona em 3 passos simples</h2>
              <ol>
                <li><strong>Conte do seu jeito:</strong> escreva ou fale o tipo de encontro que tem vontade de viver, sem formulários longos.</li>
                <li><strong>Locais públicos verificados:</strong> sugerimos apenas espaços ativos no OpenStreetMap em Brasília, respeitando acessibilidade e nível de ruído.</li>
                <li><strong>Pequenos grupos seguros:</strong> formamos grupos de 3 a 8 pessoas com Check-in Final e pauta quebra-gelo 30 minutos antes.</li>
              </ol>
            </section>
          )}
          <div className="trust-row">
            <span><Icon name="shield" size={18} /> Locais verificados no DF</span>
            <span><Icon name="people" size={18} /> Grupos de 3 a 8 pessoas</span>
          </div>
        </div>
      </section>
    </main>
  )
}

function Signup({
  back,
  done,
  onNotify,
}: {
  back: () => void
  done: (name?: string) => void
  onNotify: (msg: string) => void
}) {
  const [form, setForm] = useState({ name: '', email: '', password: '', birthdate: '', terms: false })
  const canSubmit =
    form.name.trim().length >= 3 &&
    form.email.includes('@') &&
    form.password.length >= 8 &&
    Boolean(form.birthdate) &&
    form.terms

  const update = (field: keyof typeof form, value: string | boolean) => {
    setForm((current) => ({ ...current, [field]: value }))
  }

  return (
    <main className="signup-page">
      <section className="signup-aside">
        <Logo light />
        <div className="signup-promise">
          <span className="eyebrow">Comece por aqui</span>
          <h1>Seu próximo encontro começa com um <em>olá.</em></h1>
          <p>Crie seu perfil para receber sugestões de grupos que combinam com o seu momento.</p>
          <ul>
            <li><span><Icon name="shield" size={19}/></span><div><strong>Você no controle</strong><small>Seus textos livres são descartados após a busca (LGPD).</small></div></li>
            <li><span><Icon name="people" size={19}/></span><div><strong>Grupos acolhedores</strong><small>Encontros de 3 a 8 pessoas, sempre em locais públicos verificados.</small></div></li>
            <li><span><Icon name="sparkle" size={19}/></span><div><strong>Sugestões com a sua cara</strong><small>Preferências e acessibilidade que você ajusta quando quiser.</small></div></li>
          </ul>
        </div>
        <p className="signup-aside-note">Conexões que aproximam</p>
      </section>

      <section className="signup-content">
        <div className="signup-top">
          <button type="button" className="back-button" onClick={back} aria-label="Voltar"><Icon name="arrow"/></button>
          <span>Já tem uma conta? <button type="button" onClick={() => done()}>Entrar</button></span>
        </div>
        <form
          className="signup-form"
          onSubmit={(event) => {
            event.preventDefault()
            if (canSubmit) done(form.name.trim())
          }}
        >
          <span className="eyebrow">Crie sua conta</span>
          <h2>Que bom ter você por aqui</h2>
          <p>Leva só um minuto. Depois, você conta um pouco mais sobre o que gosta.</p>

          <div className="signup-fields">
            <label>
              <span>Nome completo</span>
              <input type="text" autoComplete="name" placeholder="Como você gosta de ser chamado?" value={form.name} onChange={(event) => update('name', event.target.value)} />
            </label>
            <label>
              <span>E-mail</span>
              <input type="email" autoComplete="email" placeholder="voce@exemplo.com" value={form.email} onChange={(event) => update('email', event.target.value)} />
            </label>
            <div className="signup-row">
              <label>
                <span>Data de nascimento</span>
                <input type="date" autoComplete="bday" value={form.birthdate} onChange={(event) => update('birthdate', event.target.value)} />
              </label>
              <label>
                <span>Crie uma senha</span>
                <input type="password" autoComplete="new-password" minLength={8} placeholder="Mínimo de 8 caracteres" value={form.password} onChange={(event) => update('password', event.target.value)} />
              </label>
            </div>
          </div>

          <label className="signup-terms">
            <input type="checkbox" checked={form.terms} onChange={(event) => update('terms', event.target.checked)} />
            <span>
              Li e aceito os{' '}
              <button type="button" onClick={() => onNotify('Termos de uso: encontros presenciais gratuitos e seguros em espaços públicos.')}>Termos de uso</button>{' '}
              e a{' '}
              <button type="button" onClick={() => onNotify('Privacidade LGPD: seus textos livres não ficam armazenados após a extração.')}>Política de privacidade</button>.
            </span>
          </label>
          <button className="primary-button full" type="submit" disabled={!canSubmit}>Criar minha conta <Icon name="arrow"/></button>
          <p className="signup-safety"><Icon name="shield" size={17}/> Seus dados ficam protegidos e nunca são vendidos.</p>
        </form>
      </section>
    </main>
  )
}

interface InterestOption {
  name: string
  icon: IconName
  size: 'short' | 'medium' | 'tall'
  position?: string
  bgSize?: string
  tone?: 'orange' | 'yellow' | 'cream' | 'brown'
}

const INTEREST_OPTIONS: InterestOption[] = [
  { name: 'Cafés & conversas', icon: 'heart', size: 'tall', position: '0% 0%', bgSize: '300% 300%' },
  { name: 'Ao ar livre', icon: 'sun', size: 'medium', position: '50% 0%', bgSize: '300% 300%' },
  { name: 'Arte & cultura', icon: 'star', size: 'short', position: '100% 0%', bgSize: '300% 300%' },
  { name: 'Gastronomia', icon: 'sparkle', size: 'short', position: '0% 50%', bgSize: '300% 300%' },
  { name: 'Música ao vivo', icon: 'heart', size: 'tall', position: '50% 50%', bgSize: '300% 300%' },
  { name: 'Livros & leitura', icon: 'profile', size: 'medium', position: '100% 50%', bgSize: '300% 300%' },
  { name: 'Jogos de tabuleiro', icon: 'people', size: 'medium', position: '0% 100%', bgSize: '200% 300%' },
  { name: 'Cinema & séries', icon: 'star', size: 'short', tone: 'brown' },
  { name: 'Viagens', icon: 'route', size: 'tall', position: '100% 100%', bgSize: '200% 300%' },
  { name: 'Tecnologia', icon: 'sparkle', size: 'short', tone: 'orange' },
  { name: 'Bem-estar', icon: 'sun', size: 'medium', tone: 'yellow' },
  { name: 'Pets', icon: 'heart', size: 'short', tone: 'cream' },
]

function Preferences({
  initialSelected,
  back,
  done,
}: {
  initialSelected: string[]
  back: () => void
  done: (interests: string[]) => void
}) {
  const [selected, setSelected] = useState<string[]>(initialSelected)
  const toggle = (interest: string) => {
    setSelected((current) =>
      current.includes(interest) ? current.filter((item) => item !== interest) : [...current, interest],
    )
  }

  return (
    <main className="preferences-onboarding">
      <header className="preferences-header">
        <button type="button" className="back-button" onClick={back} aria-label="Voltar"><Icon name="arrow"/></button>
        <Logo/>
        <button type="button" className="skip-button" onClick={() => done(selected.length ? selected : initialSelected)}>Pular por agora</button>
      </header>

      <section className="preferences-intro">
        <div>
          <span className="eyebrow">Deixe o Bubbles com a sua cara</span>
          <h1>O que faz você<br/><em>perder a hora?</em></h1>
        </div>
        <div className="preferences-copy">
          <p>Escolha pelo menos 3 interesses. É só tocar no que combina com você — dá para mudar tudo depois.</p>
          <div className="selection-status">
            <span>{selected.length}</span>
            <div><strong>{selected.length === 1 ? 'escolha feita' : 'escolhas feitas'}</strong><small>{selected.length < 3 ? `Faltam ${3 - selected.length} para continuar` : 'Ótimo! Já podemos personalizar suas sugestões.'}</small></div>
          </div>
        </div>
      </section>

      <section className="interest-grid" aria-label="Escolha seus interesses">
        {INTEREST_OPTIONS.map((interest) => {
          const isSelected = selected.includes(interest.name)
          const imageStyle: CSSProperties | undefined = interest.position
            ? {
                backgroundImage: "url('/assets/preferences-moodboard.png')",
                backgroundPosition: interest.position,
                backgroundSize: interest.bgSize ?? '300% 300%',
              }
            : undefined
          return (
            <button
              type="button"
              key={interest.name}
              className={`interest-card ${interest.size} ${interest.tone ?? ''} ${isSelected ? 'selected' : ''}`}
              style={imageStyle}
              aria-pressed={isSelected}
              onClick={() => toggle(interest.name)}
            >
              <span className="interest-check"><Icon name={isSelected ? 'check' : interest.icon} size={20}/></span>
              <span className="interest-label">{interest.name}</span>
            </button>
          )
        })}
      </section>

      <footer className="preferences-footer">
        <div className="selected-preview">
          <div className="mini-bubbles"><i/><i/><i/></div>
          <p><strong>Sua bolha está ganhando forma</strong><span>{selected.length ? selected.slice(0, 3).join(' · ') : 'Escolha o que você curte para começar'}</span></p>
        </div>
        <button type="button" className="primary-button" disabled={selected.length < 3} onClick={() => done(selected)}>
          Continuar com {selected.length} {selected.length === 1 ? 'interesse' : 'interesses'} <Icon name="arrow"/>
        </button>
      </footer>
    </main>
  )
}

function Home({
  profile,
  request,
  onChangeRequest,
  activeMeeting,
  onProfile,
  onSubmit,
  onNotify,
}: {
  profile: MemberProfile
  request: string
  onChangeRequest: (value: string) => void
  activeMeeting: ScheduledMeeting | null
  onProfile: () => void
  onSubmit: () => void
  onNotify: (msg: string) => void
}) {
  const [listening, setListening] = useState(false)
  const firstName = profile.name.trim().split(/\s+/)[0] || 'Carla'

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
      onChangeRequest(
        'Quero um café bem tranquilo e acessível na Asa Sul no sábado à tarde para conversar sobre livros.',
      )
      onNotify('Transcrição de voz simulada preenchida — confirme ou edite seu pedido.')
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
      onNotify('Não foi possível acessar o microfone. Você pode digitar ou tocar num exemplo.')
    }
    recognition.onend = () => setListening(false)
    recognition.start()
  }

  return (
    <>
      <Header initials={profile.initials} onProfile={onProfile} activeMeeting={activeMeeting} />
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
        <aside className="safety-note"><Icon name="shield" /><div><strong>Você está em um espaço seguro</strong><p>Todos os encontros acontecem em locais públicos verificados no OpenStreetMap em Brasília.</p></div></aside>
      </main>
    </>
  )
}

function Confirm({
  intent,
  onUpdateIntent,
  back,
  next,
}: {
  intent: InterpretedIntent
  onUpdateIntent: (nextIntent: InterpretedIntent) => void
  back: () => void
  next: () => void
}) {
  const [editingField, setEditingField] = useState<'activity' | 'vibe' | 'when' | 'region' | null>(null)

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
              <>
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
              </>
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

function Recommendations({
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

  useEffect(() => {
    if (venues.length > 0 && !venues.some((v) => v.placeId === selectedId)) {
      setSelectedId(venues[0].placeId)
    }
  }, [venues, selectedId])

  return (
    <main className="flow-page recommendations-page">
      <div className="flow-header"><button type="button" className="back-button" onClick={back} aria-label="Voltar"><Icon name="arrow"/></button><Logo/><span /></div>
      <div className="flow-container wide">
        <Stepper step={2}/>
        <div className="results-heading">
          <div><span className="eyebrow">Locais verificados em Brasília</span><h1>Escolha seu<br/><em>próximo encontro</em></h1></div>
          <p>3 opções verificadas no OpenStreetMap, perto de você e filtradas pelas suas necessidades de conforto e acessibilidade.</p>
        </div>
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
                    <span className="venue-badge">Acesso plano (wheelchair={venue.wheelchair})</span>
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
                  <button
                    type="button"
                    className={isSelected ? 'primary-button full' : 'secondary-button full'}
                    onClick={(event) => {
                      event.stopPropagation()
                      setSelectedId(venue.placeId)
                      choose(venue)
                    }}
                  >
                    Escolher esta opção <Icon name="arrow"/>
                  </button>
                </div>
              </article>
            )
          })}
        </div>
        <button type="button" className="text-button centered" onClick={onMoreOptions}>
          Ver outras opções verificadas no DF
        </button>
      </div>
    </main>
  )
}

function Meeting({
  profile,
  meeting,
  onProfile,
  onToggleCheckin,
  onCancelEarly,
  goMeetings,
  feedback,
  onNotify,
}: {
  profile: MemberProfile
  meeting: ScheduledMeeting
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
      <Header initials={profile.initials} onProfile={onProfile} activeMeeting={meeting} />
      <main className="page meeting-page">
        <div className="success-heading">
          <span className="success-icon"><Icon name="check" size={34}/></span>
          <span className="eyebrow">Tudo combinado</span>
          <h1>Seu encontro<br/><em>está confirmado!</em></h1>
          <p>Agora é só chegar. A gente cuida dos lembretes e da pauta quebra-gelo.</p>
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
            <div className="avatar-stack"><i>MA</i><i>LS</i><i>JR</i><i>+{venue.groupSize - 3}</i></div>
            <strong>Seu grupo tem {venue.groupSize} pessoas</strong>
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

function Meetings({
  profile,
  meetings,
  onProfile,
  openMeeting,
  goHome,
}: {
  profile: MemberProfile
  meetings: ScheduledMeeting[]
  onProfile: () => void
  openMeeting: (id: string) => void
  goHome: () => void
}) {
  const [tab, setTab] = useState<'Próximos' | 'Anteriores' | 'Cancelados'>('Próximos')
  const statusByTab: Record<typeof tab, ScheduledMeeting['status']> = {
    Próximos: 'confirmado',
    Anteriores: 'concluido',
    Cancelados: 'cancelado',
  }
  const filtered = meetings.filter((m) => m.status === statusByTab[tab])
  const nextActive = meetings.find((m) => m.status === 'confirmado') ?? null

  return (
    <>
      <Header initials={profile.initials} onProfile={onProfile} activeMeeting={nextActive} />
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
                  onClick={() => openMeeting(item.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      openMeeting(item.id)
                    }
                  }}
                >
                  <div className="card-date"><strong>{item.venue.dateDay}</strong><span>{item.venue.dateMonth}</span></div>
                  <div>
                    <span className="status-pill">
                      {item.status === 'confirmado'
                        ? item.checkedIn
                          ? 'Check-in confirmado'
                          : 'Confirmado'
                        : item.status === 'concluido'
                          ? `Avaliado (${item.satisfaction ?? 5}/5)`
                          : 'Desistência prévia'}
                    </span>
                    <h2>{item.activity}</h2>
                    <p>{item.venue.name} · {item.venue.time}</p>
                    <div className="avatar-stack small"><i>MA</i><i>LS</i><i>JR</i><i>+{item.venue.groupSize - 3}</i></div>
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

function Feedback({
  venueName,
  done,
}: {
  venueName: string
  done: (satisfaction: number, safety: number) => void
}) {
  const [satisfaction, setSatisfaction] = useState(0)
  const [safety, setSafety] = useState(0)
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
        <label className="comment-field"><span>Quer contar mais? <small>Opcional</small></span><textarea placeholder="Escreva do seu jeito..."/></label>
        <label className="meet-again"><input type="checkbox"/><span><strong>Quero encontrar esse grupo de novo</strong><small>Vamos considerar isso nos próximos encontros.</small></span></label>
        <button type="button" className="primary-button full" disabled={!satisfaction || !safety} onClick={() => done(satisfaction, safety)}>
          Enviar avaliação <Icon name="arrow"/>
        </button>
      </div>
    </main>
  )
}

function Profile({
  profile,
  activeMeeting,
  onUpdateProfile,
  onEditInterests,
}: {
  profile: MemberProfile
  activeMeeting: ScheduledMeeting | null
  onUpdateProfile: (next: MemberProfile) => void
  onEditInterests: () => void
}) {
  const [openSection, setOpenSection] = useState<'region' | 'privacy' | 'accessibility' | 'name' | null>(null)

  const items: Array<{ id: 'interests' | 'region' | 'privacy' | 'accessibility'; icon: IconName; title: string; subtitle: string }> = [
    {
      id: 'interests',
      icon: 'heart',
      title: 'Meus interesses',
      subtitle: profile.interests.join(', ') || 'Escolher interesses',
    },
    {
      id: 'region',
      icon: 'location',
      title: 'Região e deslocamento',
      subtitle: `${profile.region}, Brasília · até ${profile.maxRadiusKm} km`,
    },
    {
      id: 'privacy',
      icon: 'shield',
      title: 'Privacidade e segurança',
      subtitle: 'Minimização de dados (LGPD) e locais verificados',
    },
    {
      id: 'accessibility',
      icon: 'sun',
      title: 'Acessibilidade e conforto sensorial',
      subtitle: `${profile.wheelchairRequired ? 'Acesso plano obrigatório' : 'Acesso padrão'} · Ruído ${profile.noiseTolerance}${profile.largeText ? ' · Texto ampliado' : ''}`,
    },
  ]

  return (
    <>
      <Header initials={profile.initials} onProfile={() => {}} activeMeeting={activeMeeting} />
      <main className="page profile-page">
        <span className="eyebrow">Seu espaço</span><h1>Perfil e <em>preferências</em></h1>
        <section className="profile-summary">
          <div className="profile-avatar">{profile.initials}</div>
          <div><h2>{profile.name}</h2><p>{profile.since}</p></div>
          <button type="button" onClick={() => setOpenSection((s) => (s === 'name' ? null : 'name'))}>
            <Icon name="edit" size={18}/> Editar
          </button>
        </section>

        {openSection === 'name' && (
          <section className="settings-panel">
            <h3>Editar nome do perfil</h3>
            <label className="detail-editor" style={{ marginTop: 0, padding: 0, border: 0 }}>
              <span>Nome de exibição</span>
              <input
                type="text"
                value={profile.name}
                onChange={(e) =>
                  onUpdateProfile({
                    ...profile,
                    name: e.target.value,
                    initials: makeInitials(e.target.value),
                  })
                }
              />
            </label>
          </section>
        )}

        <section className="commitment">
          <div><span className="round-icon yellow"><Icon name="star"/></span><div><small>Seu nível de comprometimento</small><h2>Companhia de confiança</h2></div></div>
          <p>Você compareceu aos seus últimos encontros. Isso ajuda todo mundo a se conectar melhor e evita faltas de última hora.</p>
          <div className="progress"><i/></div>
        </section>

        <div className="settings-list">
          {items.map((item) => (
            <button
              type="button"
              key={item.id}
              onClick={() => {
                if (item.id === 'interests') {
                  onEditInterests()
                } else {
                  const section = item.id
                  setOpenSection((current) => (current === section ? null : section))
                }
              }}
            >
              <span className="settings-icon"><Icon name={item.icon}/></span>
              <span><strong>{item.title}</strong><small>{item.subtitle}</small></span>
              <Icon name="chevron"/>
            </button>
          ))}
        </div>

        {openSection === 'region' && (
          <section className="settings-panel">
            <h3>Região padrão em Brasília (DF)</h3>
            <div className="settings-chips">
              {['Asa Sul', 'Asa Norte', 'Plano Piloto'].map((reg) => (
                <button
                  type="button"
                  key={reg}
                  className={profile.region === reg ? 'active' : ''}
                  onClick={() => onUpdateProfile({ ...profile, region: reg })}
                >
                  {reg}
                </button>
              ))}
            </div>
          </section>
        )}

        {openSection === 'privacy' && (
          <section className="settings-panel">
            <h3>Privacidade por design (LGPD)</h3>
            <p>
              Apenas condições objetivas de acessibilidade física e tolerância sensorial ficam salvas no seu Perfil Base. Textos livres e relatos enviados no pedido são processados em memória e descartados imediatamente após a busca.
            </p>
          </section>
        )}

        {openSection === 'accessibility' && (
          <section className="settings-panel">
            <h3>Acessibilidade Física e Tolerância Sensorial</h3>
            <label className="detail-toggle">
              <input
                type="checkbox"
                checked={profile.wheelchairRequired}
                onChange={(e) => onUpdateProfile({ ...profile, wheelchairRequired: e.target.checked })}
              />
              <span>Filtrar sempre por locais acessíveis (bloqueia locais com wheelchair=no)</span>
            </label>
            <label className="detail-toggle">
              <input
                type="checkbox"
                checked={profile.largeText}
                onChange={(e) => onUpdateProfile({ ...profile, largeText: e.target.checked })}
              />
              <span>Ativar tamanho de texto ampliado</span>
            </label>
            <div className="settings-chips">
              {(['baixo', 'moderado', 'indiferente'] as const).map((level) => (
                <button
                  type="button"
                  key={level}
                  className={profile.noiseTolerance === level ? 'active' : ''}
                  onClick={() => onUpdateProfile({ ...profile, noiseTolerance: level })}
                >
                  Ruído: {level}
                </button>
              ))}
            </div>
          </section>
        )}
      </main>
    </>
  )
}

export default function App() {
  const [screen, setScreen] = useState<Screen>('welcome')
  const [profile, setProfile] = useState<MemberProfile>({
    name: 'Carla Mendes',
    initials: 'CM',
    since: 'Membro em Brasília · DF',
    region: 'Asa Sul',
    maxRadiusKm: 5,
    interests: ['Cafés & conversas', 'Tecnologia', 'Livros & leitura'],
    wheelchairRequired: false,
    noiseTolerance: 'baixo',
    largeText: false,
  })
  const [requestText, setRequestText] = useState('')
  const [intent, setIntent] = useState<InterpretedIntent>(() =>
    interpretRequest('Quero um café tranquilo na Asa Sul no sábado à tarde para conversar sobre tecnologia.', {
      name: 'Carla Mendes',
      initials: 'CM',
      since: 'Membro em Brasília · DF',
      region: 'Asa Sul',
      maxRadiusKm: 5,
      interests: ['Cafés & conversas', 'Tecnologia', 'Livros & leitura'],
      wheelchairRequired: false,
      noiseTolerance: 'baixo',
      largeText: false,
    }),
  )
  const [venuePageOffset, setVenuePageOffset] = useState(0)
  const [meetings, setMeetings] = useState<ScheduledMeeting[]>([
    {
      id: 'enc-inicial',
      venue: VERIFIED_VENUES_DF[0],
      activity: 'Café e conversa',
      status: 'confirmado',
      checkedIn: false,
      groupInterests: ['Tecnologia', 'Livros & leitura', 'Cafés'],
    },
  ])
  const [activeMeetingId, setActiveMeetingId] = useState<string>('enc-inicial')
  const [toast, setToast] = useState<string | null>(null)

  const notify = (msg: string) => {
    setToast(msg)
  }

  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(() => setToast(null), 3200)
    return () => window.clearTimeout(timer)
  }, [toast])

  const showNav = ['home', 'meeting', 'meetings', 'profile'].includes(screen)
  const navigate = (next: Screen) => {
    setScreen(next)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const activeMeeting =
    meetings.find((m) => m.id === activeMeetingId) ?? meetings[0]

  const recommendedVenues = rankVenues(intent, venuePageOffset)

  const handleSubmitRequest = () => {
    const parsed = interpretRequest(requestText, profile)
    setIntent(parsed)
    setVenuePageOffset(0)
    navigate('confirm')
  }

  const handleChooseVenue = (venue: VerifiedVenue) => {
    const newId = `enc-${Date.now()}`
    const created: ScheduledMeeting = {
      id: newId,
      venue,
      activity: intent.activity,
      status: 'confirmado',
      checkedIn: false,
      groupInterests: profile.interests.length ? profile.interests : ['Cafés', 'Conversa', 'Cultura'],
    }
    setMeetings((prev) => [created, ...prev])
    setActiveMeetingId(newId)
    navigate('meeting')
  }

  const handleCompleteFeedback = (satisfaction: number, safety: number) => {
    setMeetings((prev) =>
      prev.map((m) =>
        m.id === activeMeeting.id
          ? { ...m, status: 'concluido', satisfaction, safety }
          : m,
      ),
    )
    notify('Avaliação enviada! Obrigado por contribuir com a reputação da comunidade.')
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
      {screen === 'welcome' && <Welcome start={() => navigate('home')} signup={() => navigate('signup')}/>}
      {screen === 'signup' && (
        <Signup
          back={() => navigate('welcome')}
          done={(name) => {
            if (name) {
              setProfile((curr) => ({ ...curr, name, initials: makeInitials(name) }))
            }
            navigate('preferences')
          }}
          onNotify={notify}
        />
      )}
      {screen === 'preferences' && (
        <Preferences
          initialSelected={profile.interests}
          back={() => navigate('signup')}
          done={(interests) => {
            setProfile((curr) => ({ ...curr, interests }))
            navigate('home')
          }}
        />
      )}
      {screen === 'home' && (
        <Home
          profile={profile}
          request={requestText}
          onChangeRequest={setRequestText}
          activeMeeting={meetings.find((m) => m.status === 'confirmado') ?? null}
          onProfile={() => navigate('profile')}
          onSubmit={handleSubmitRequest}
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
          choose={handleChooseVenue}
          onMoreOptions={() => setVenuePageOffset((offset) => offset + 1)}
        />
      )}
      {screen === 'meeting' && activeMeeting && (
        <Meeting
          profile={profile}
          meeting={activeMeeting}
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
          onProfile={() => navigate('profile')}
          openMeeting={(id) => {
            setActiveMeetingId(id)
            navigate('meeting')
          }}
          goHome={() => navigate('home')}
        />
      )}
      {screen === 'feedback' && activeMeeting && (
        <Feedback venueName={activeMeeting.venue.name} done={handleCompleteFeedback} />
      )}
      {screen === 'profile' && (
        <Profile
          profile={profile}
          activeMeeting={meetings.find((m) => m.status === 'confirmado') ?? null}
          onUpdateProfile={setProfile}
          onEditInterests={() => navigate('preferences')}
        />
      )}
      {showNav && <Nav current={screen} go={navigate}/>}
    </div>
  )
}
