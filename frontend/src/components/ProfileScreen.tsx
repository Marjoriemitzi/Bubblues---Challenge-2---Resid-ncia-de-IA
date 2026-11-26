import { useState } from 'react'
import { makeInitials, type MemberProfile, type ScheduledMeeting } from '../data/bubblesData'
import { Header, Icon, type Screen } from './Icons'

export function Profile({
  profile,
  activeMeeting,
  showNotifications,
  onToggleNotifications,
  onNavigate,
  onUpdateProfile,
  onEditInterests,
  onEditStyle,
  onOpenLegal,
}: {
  profile: MemberProfile
  activeMeeting: ScheduledMeeting | null
  showNotifications: boolean
  onToggleNotifications: () => void
  onNavigate: (screen: Screen) => void
  onUpdateProfile: (next: MemberProfile) => void
  onEditInterests: () => void
  onEditStyle: () => void
  onOpenLegal: (tab: 'terms' | 'privacy') => void
}) {
  const [openSection, setOpenSection] = useState<'region' | 'privacy' | 'accessibility' | 'name' | null>(null)

  const items: Array<{ id: 'interests' | 'style' | 'region' | 'privacy' | 'accessibility'; icon: 'heart' | 'people' | 'location' | 'shield' | 'sun'; title: string; subtitle: string }> = [
    {
      id: 'interests',
      icon: 'heart',
      title: 'Meus interesses',
      subtitle: profile.interests.join(', ') || 'Escolher interesses',
    },
    {
      id: 'style',
      icon: 'people',
      title: 'Estilo de convivência',
      subtitle: `${profile.sociability} · conversas ${profile.conversationStyle.replace('_', ' ')}`,
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
      <Header
        initials={profile.initials}
        onProfile={() => {}}
        activeMeeting={activeMeeting}
        showNotifications={showNotifications}
        onToggleNotifications={onToggleNotifications}
        current="profile"
        go={onNavigate}
      />
      <main className="page profile-page">
        <span className="eyebrow">Seu espaço</span><h1>Perfil e <em>preferências</em></h1>

        {profile.accountStatus === 'suspenso_temporario' && (
          <section className="abstention-card" role="alert" style={{ marginTop: 0 }}>
            <header>
              <span className="round-icon orange"><Icon name="shield" /></span>
              <h2>Suspensão temporária por No-Show</h2>
            </header>
            <p>
              Você acumulou {profile.noShowCount} faltas após confirmar presença no Check-in Final. Para proteger os grupos, novos pareamentos ficam pausados por 7 dias. Lembre-se: cancelar antes do Check-in Final (Desistência Prévia) nunca gera penalidade.
            </p>
          </section>
        )}

        <section className="profile-summary">
          <div className="profile-avatar">{profile.initials}</div>
          <div>
            <h2>{profile.name || 'Membro Bubbles'}</h2>
            <p>{profile.since}</p>
          </div>
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
                placeholder="Digite seu nome"
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
          <div>
            <span className="round-icon yellow"><Icon name="star"/></span>
            <div>
              <small>Seu nível de comprometimento ({profile.commitmentPoints} pts)</small>
              <h2>
                {profile.accountStatus === 'suspenso_temporario'
                  ? 'Conta pausada temporariamente'
                  : 'Companhia de confiança'}
              </h2>
            </div>
          </div>
          <p>
            Desistência prévia antes do Check-in Final é isenta de punição. Apenas faltas após confirmação final descontam pontos.
          </p>
          <div className="progress"><i style={{ width: `${profile.commitmentPoints}%` }}/></div>
        </section>

        <div className="settings-list">
          {items.map((item) => (
            <button
              type="button"
              key={item.id}
              onClick={() => {
                if (item.id === 'interests') {
                  onEditInterests()
                } else if (item.id === 'style') {
                  onEditStyle()
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
            <div className="settings-chips">
              <button type="button" onClick={() => onOpenLegal('privacy')}>Ler Política de Privacidade</button>
              <button type="button" onClick={() => onOpenLegal('terms')}>Ler Termos de Uso</button>
            </div>
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
