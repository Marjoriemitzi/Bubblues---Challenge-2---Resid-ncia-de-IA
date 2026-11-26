import { useState } from 'react'
import { Icon, Logo } from './Icons'

export function LegalModal({
  tab,
  onClose,
}: {
  tab: 'terms' | 'privacy'
  onClose: () => void
}) {
  const [active, setActive] = useState<'terms' | 'privacy'>(tab)

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Termos e Privacidade">
      <section className="modal-card">
        <header className="modal-header">
          <Logo />
          <button type="button" className="secondary-button" onClick={onClose}>Fechar</button>
        </header>
        <div className="tabs">
          <button type="button" className={active === 'terms' ? 'active' : ''} onClick={() => setActive('terms')}>Termos de Uso</button>
          <button type="button" className={active === 'privacy' ? 'active' : ''} onClick={() => setActive('privacy')}>Privacidade (LGPD)</button>
        </div>
        {active === 'terms' ? (
          <div className="modal-body">
            <h2>Regras da comunidade Bubbles</h2>
            <ul>
              <li><strong>Encontros presenciais gratuitos:</strong> conectamos grupos de 3 a 8 pessoas em espaços públicos ou comerciais verificados no DF.</li>
              <li><strong>Compromisso e Quórum Mínimo:</strong> desistências antes do Check-in Final (30 a 60 min antes) são livres de penalidade. Faltas após confirmação final geram alerta de No-Show.</li>
              <li><strong>Sem intermediação financeira ou de transporte:</strong> o Bubbles facilita apenas a organização logística do encontro.</li>
            </ul>
          </div>
        ) : (
          <div className="modal-body">
            <h2>Proteção de Dados e Minimização (RNF02)</h2>
            <ul>
              <li><strong>Textos livres são efêmeros:</strong> pedidos digitados ou falados são convertidos em filtros estruturados na memória e imediatamente descartados.</li>
              <li><strong>Sem perfilamento clínico:</strong> armazenamos apenas interesses gerais, acessibilidade física objetiva e tolerância sensorial.</li>
              <li><strong>Você no controle:</strong> pode alterar ou remover suas preferências a qualquer momento na aba Perfil.</li>
            </ul>
          </div>
        )}
      </section>
    </div>
  )
}

export function Welcome({
  start,
  signup,
  login,
}: {
  start: () => void
  signup: () => void
  login: () => void
}) {
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
          <div className="welcome-secondary-links">
            <button type="button" className="text-button" onClick={login}>Já tenho conta (Entrar)</button>
            <button type="button" className="text-button" onClick={() => setShowHowItWorks((open) => !open)}>
              {showHowItWorks ? 'Ocultar como funciona' : 'Ver como funciona'}
            </button>
          </div>
          {showHowItWorks && (
            <section className="info-drawer" aria-label="Como funciona o Bubbles">
              <h2>Como funciona em 3 passos simples</h2>
              <ol>
                <li><strong>Conte do seu jeito:</strong> escreva, fale ou toque numa sugestão pronta, sem formulários cansativos.</li>
                <li><strong>Locais públicos verificados:</strong> sugerimos apenas espaços ativos no OpenStreetMap em Brasília, respeitando acessibilidade e nível de ruído.</li>
                <li><strong>Pequenos grupos seguros:</strong> formamos grupos de 3 a 8 pessoas com Check-in Final e Pauta Quebra-Gelo 30 minutos antes.</li>
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

export function Login({
  back,
  goSignup,
  goForgot,
  done,
}: {
  back: () => void
  goSignup: () => void
  goForgot: () => void
  done: (email: string) => void
}) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const canSubmit = email.includes('@') && password.length >= 6

  return (
    <main className="signup-page">
      <section className="signup-aside">
        <Logo light />
        <div className="signup-promise">
          <span className="eyebrow">Que bom te ver de volta</span>
          <h1>Seu grupo está a um <em>clique.</em></h1>
          <p>Entre para acompanhar seus Slots de Pareamento, confirmar presença no Check-in Final e descobrir novos locais seguros.</p>
        </div>
        <p className="signup-aside-note">Conexões que aproximam</p>
      </section>
      <section className="signup-content">
        <div className="signup-top">
          <button type="button" className="back-button" onClick={back} aria-label="Voltar"><Icon name="arrow"/></button>
          <span>Ainda não tem conta? <button type="button" onClick={goSignup}>Criar conta</button></span>
        </div>
        <form
          className="signup-form"
          onSubmit={(e) => {
            e.preventDefault()
            if (canSubmit) done(email.trim())
          }}
        >
          <span className="eyebrow">Acesso de Membro</span>
          <h2>Entrar no Bubbles</h2>
          <p>Use seu e-mail cadastrado para continuar.</p>
          <div className="signup-fields">
            <label>
              <span>E-mail</span>
              <input type="email" autoComplete="email" placeholder="voce@exemplo.com" value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
            <label>
              <span>Senha</span>
              <input type="password" autoComplete="current-password" placeholder="Sua senha" value={password} onChange={(e) => setPassword(e.target.value)} />
            </label>
          </div>
          <div className="auth-inline-row">
            <button type="button" className="text-button" onClick={goForgot}>Esqueci minha senha</button>
          </div>
          <button className="primary-button full" type="submit" disabled={!canSubmit}>Entrar <Icon name="arrow"/></button>
        </form>
      </section>
    </main>
  )
}

export function ForgotPassword({
  back,
  onNotify,
}: {
  back: () => void
  onNotify: (msg: string) => void
}) {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)

  return (
    <main className="flow-page">
      <div className="flow-header"><button type="button" className="back-button" onClick={back} aria-label="Voltar"><Icon name="arrow"/></button><Logo/><span /></div>
      <div className="flow-container">
        <span className="eyebrow">Recuperar acesso</span>
        <h1>Esqueceu a<br/><em>sua senha?</em></h1>
        <p className="lead">Informe seu e-mail cadastrado. Enviaremos um link seguro para você definir uma nova senha.</p>
        {!sent ? (
          <form
            className="signup-form"
            style={{ marginTop: '2rem' }}
            onSubmit={(e) => {
              e.preventDefault()
              if (email.includes('@')) {
                setSent(true)
                onNotify('Instruções de recuperação enviadas para o seu e-mail.')
              }
            }}
          >
            <div className="signup-fields">
              <label>
                <span>E-mail cadastrado</span>
                <input type="email" placeholder="voce@exemplo.com" value={email} onChange={(e) => setEmail(e.target.value)} />
              </label>
            </div>
            <button type="submit" className="primary-button full" disabled={!email.includes('@')}>
              Enviar link de recuperação <Icon name="arrow"/>
            </button>
          </form>
        ) : (
          <section className="abstention-card" role="status">
            <header>
              <span className="round-icon orange"><Icon name="check"/></span>
              <h2>Verifique sua caixa de entrada</h2>
            </header>
            <p>Se <strong>{email}</strong> estiver cadastrado, você receberá as instruções em instantes.</p>
            <button type="button" className="primary-button" onClick={back}>Voltar para o login</button>
          </section>
        )}
      </div>
    </main>
  )
}

export function Signup({
  back,
  goLogin,
  done,
  onOpenLegal,
}: {
  back: () => void
  goLogin: () => void
  done: (name: string) => void
  onOpenLegal: (tab: 'terms' | 'privacy') => void
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
          <span>Já tem uma conta? <button type="button" onClick={goLogin}>Entrar</button></span>
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
              <button type="button" onClick={() => onOpenLegal('terms')}>Termos de uso</button>{' '}
              e a{' '}
              <button type="button" onClick={() => onOpenLegal('privacy')}>Política de privacidade</button>.
            </span>
          </label>
          <button className="primary-button full" type="submit" disabled={!canSubmit}>Criar minha conta <Icon name="arrow"/></button>
          <p className="signup-safety"><Icon name="shield" size={17}/> Seus dados ficam protegidos e nunca são vendidos.</p>
        </form>
      </section>
    </main>
  )
}
