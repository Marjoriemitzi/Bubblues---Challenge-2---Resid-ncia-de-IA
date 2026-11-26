import { useState, type CSSProperties } from 'react'
import type {
  ConversationStyle,
  MeetingFrequency,
  MemberProfile,
  NoiseTolerance,
  Sociability,
} from '../data/bubblesData'
import { Icon, Logo, Stepper, type IconName } from './Icons'

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

export function Preferences({
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
          <span className="eyebrow">Etapa 1 de 2 · Seus interesses</span>
          <h1>O que faz você<br/><em>perder a hora?</em></h1>
        </div>
        <div className="preferences-copy">
          <p>Escolha pelo menos 3 interesses. É só tocar no que combina com você — dá para mudar tudo depois.</p>
          <div className="selection-status">
            <span>{selected.length}</span>
            <div><strong>{selected.length === 1 ? 'escolha feita' : 'escolhas feitas'}</strong><small>{selected.length < 3 ? `Faltam ${3 - selected.length} para continuar` : 'Ótimo! Vamos ajustar seu estilo de convivência.'}</small></div>
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

export function OnboardingStyle({
  profile,
  back,
  done,
}: {
  profile: MemberProfile
  back: () => void
  done: (updates: Partial<MemberProfile>) => void
}) {
  const [sociability, setSociability] = useState<Sociability>(profile.sociability)
  const [conversationStyle, setConversationStyle] = useState<ConversationStyle>(profile.conversationStyle)
  const [frequency, setFrequency] = useState<MeetingFrequency>(profile.frequency)
  const [noiseTolerance, setNoiseTolerance] = useState<NoiseTolerance>(profile.noiseTolerance)
  const [wheelchairRequired, setWheelchairRequired] = useState<boolean>(profile.wheelchairRequired)
  const [region, setRegion] = useState<string>(profile.region)

  return (
    <main className="flow-page">
      <div className="flow-header">
        <button type="button" className="back-button" onClick={back} aria-label="Voltar"><Icon name="arrow"/></button>
        <Logo/>
        <span />
      </div>
      <div className="flow-container">
        <Stepper step={2} total={2} />
        <span className="eyebrow">Perfil Base e conforto</span>
        <h1>Como você prefere<br/><em>os encontros?</em></h1>
        <p className="lead">Essas escolhas evitam locais barulhentos ou sem acessibilidade desde a primeira recomendação.</p>

        <div className="onboarding-questions">
          <section className="question-block">
            <h2>1. Como você se considera?</h2>
            <div className="settings-chips">
              {(
                [
                  ['introvertido', 'Introvertido(a)'],
                  ['ambivertido', 'Ambivertido(a)'],
                  ['extrovertido', 'Extrovertido(a)'],
                ] as const
              ).map(([val, label]) => (
                <button type="button" key={val} className={sociability === val ? 'active' : ''} onClick={() => setSociability(val)}>
                  {label}
                </button>
              ))}
            </div>
          </section>

          <section className="question-block">
            <h2>2. Tolerância sensorial (nível de ruído do local)</h2>
            <div className="settings-chips">
              {(
                [
                  ['baixo', 'Lugares tranquilos (baixo ruído)'],
                  ['moderado', 'Moderado (cafés e parques)'],
                  ['indiferente', 'Tanto faz'],
                ] as const
              ).map(([val, label]) => (
                <button type="button" key={val} className={noiseTolerance === val ? 'active' : ''} onClick={() => setNoiseTolerance(val)}>
                  {label}
                </button>
              ))}
            </div>
          </section>

          <section className="question-block">
            <h2>3. Como prefere conversar?</h2>
            <div className="settings-chips">
              {(
                [
                  ['profundas', 'Conversas profundas'],
                  ['leves', 'Conversas leves e descontraídas'],
                  ['tanto_faz', 'Tanto faz'],
                ] as const
              ).map(([val, label]) => (
                <button type="button" key={val} className={conversationStyle === val ? 'active' : ''} onClick={() => setConversationStyle(val)}>
                  {label}
                </button>
              ))}
            </div>
          </section>

          <section className="question-block">
            <h2>4. Com que frequência gostaria de sair?</h2>
            <div className="settings-chips">
              {(
                [
                  ['semanal', 'Toda semana'],
                  ['mensal', 'Algumas vezes no mês'],
                  ['ocasional', 'Ocasionalmente'],
                ] as const
              ).map(([val, label]) => (
                <button type="button" key={val} className={frequency === val ? 'active' : ''} onClick={() => setFrequency(val)}>
                  {label}
                </button>
              ))}
            </div>
          </section>

          <section className="question-block">
            <h2>5. Região em Brasília e acessibilidade física</h2>
            <div className="settings-chips" style={{ marginBottom: '.85rem' }}>
              {['Asa Sul', 'Asa Norte', 'Plano Piloto'].map((reg) => (
                <button type="button" key={reg} className={region === reg ? 'active' : ''} onClick={() => setRegion(reg)}>
                  {reg}
                </button>
              ))}
            </div>
            <label className="detail-toggle">
              <input
                type="checkbox"
                checked={wheelchairRequired}
                onChange={(e) => setWheelchairRequired(e.target.checked)}
              />
              <span>Exigir sempre locais com acesso plano / cadeira de rodas (Hard Filter)</span>
            </label>
          </section>
        </div>

        <div className="flow-actions">
          <button
            type="button"
            className="primary-button"
            onClick={() =>
              done({
                sociability,
                conversationStyle,
                frequency,
                noiseTolerance,
                wheelchairRequired,
                region,
              })
            }
          >
            Salvar Perfil Base e começar <Icon name="check"/>
          </button>
        </div>
      </div>
    </main>
  )
}
