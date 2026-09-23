import { useCallback, useEffect, useState } from 'react'
import * as api from './api.js'
import Login from './components/Login.jsx'
import ChangePasswordModal from './components/ChangePasswordModal.jsx'
import VeillePage from './components/VeillePage.jsx'
import JournauxPage from './components/JournauxPage.jsx'
import DossiersPage from './components/DossiersPage.jsx'
import PricesPage from './components/PricesPage.jsx'
import AdminPage from './components/AdminPage.jsx'
import { ADMIN_ROLES } from './utils.js'
import logo from './logo.png'
import './index.css'

const ROLE_LABELS = {
  admin: 'Administrateur',
  assistante: 'Assistante — journaux',
  selectionneur: 'Sélection des avis',
  superviseur: 'Superviseur',
  monteur: 'Montage des dossiers',
}

/** Onglets visibles selon le profil. */
const TABS = [
  { key: 'veille', label: 'Veille en ligne', roles: ['admin', 'assistante', 'selectionneur', 'superviseur', 'monteur'] },
  { key: 'journaux', label: 'Journaux papier', roles: ['admin', 'assistante', 'selectionneur', 'superviseur', 'monteur'] },
  { key: 'dossiers', label: 'Dossiers', roles: ['admin', 'selectionneur', 'superviseur', 'monteur'] },
  { key: 'prix', label: 'Historique des prix', roles: ['admin', 'assistante', 'selectionneur', 'superviseur', 'monteur'] },
  { key: 'admin', label: 'Administration', roles: ADMIN_ROLES },
]

const DEFAULT_TAB = {
  admin: 'admin',
  assistante: 'journaux',
  selectionneur: 'veille',
  superviseur: 'veille',
  monteur: 'dossiers',
}

export default function App() {
  const [user, setUser] = useState(null)
  const [booting, setBooting] = useState(true)
  const [tab, setTab] = useState('veille')
  const [dashboard, setDashboard] = useState(null)
  const [showPasswordModal, setShowPasswordModal] = useState(false)

  // Reprise de session : un jeton valide en stockage local évite de se
  // reconnecter à chaque rechargement de la page.
  useEffect(() => {
    if (!api.getToken()) {
      setBooting(false)
      return
    }
    api.fetchMe()
      .then((me) => {
        setUser(me)
        setTab(DEFAULT_TAB[me.role] || 'veille')
      })
      .catch(() => api.setToken(null))
      .finally(() => setBooting(false))
  }, [])

  const loadDashboard = useCallback(() => {
    if (!ADMIN_ROLES.includes(user?.role)) return
    api.fetchAdminDashboard().then(setDashboard).catch(() => setDashboard(null))
  }, [user])

  useEffect(() => { loadDashboard() }, [loadDashboard])

  function handleLoggedIn(me) {
    setUser(me)
    setTab(DEFAULT_TAB[me.role] || 'veille')
    if (me.must_change_password) setShowPasswordModal(true)
  }

  async function handleLogout() {
    await api.logout()
    setUser(null)
    setDashboard(null)
  }

  if (booting) {
    return (
      <>
        <div className="page-background" />
        <div className="login-screen"><p className="spinner-text">Chargement…</p></div>
      </>
    )
  }

  if (!user) {
    return (
      <>
        <div className="page-background" />
        <Login onLoggedIn={handleLoggedIn} />
      </>
    )
  }

  const visibleTabs = TABS.filter((t) => t.roles.includes(user.role))
  const alertCount = dashboard?.alerts?.length || 0

  return (
    <>
      <div className="page-background" />

      <div className="app">
        <header className="app-header">
          <div className="brand">
            <img className="brand-logo" src={logo} alt="ADOC" />
            <div>
              <h1>Veille Appels d'Offres &amp; AMI</h1>
              <p className="app-subtitle">Sénégal et sous-région UEMOA — veille en ligne et presse papier</p>
            </div>
          </div>

          <div className="header-user">
            <div className="user-chip">
              <strong>{user.full_name || user.username}</strong>
              <span>{ROLE_LABELS[user.role] || user.role}</span>
            </div>
            <button className="btn btn-outline btn-sm" onClick={() => setShowPasswordModal(true)}>
              Mot de passe
            </button>
            <button className="btn btn-outline btn-sm" onClick={handleLogout}>
              Déconnexion
            </button>
          </div>
        </header>

        <nav className="main-nav">
          {visibleTabs.map((t) => (
            <button
              key={t.key}
              className={`nav-tab${tab === t.key ? ' is-active' : ''}`}
              onClick={() => setTab(t.key)}
            >
              {t.label}
              {t.key === 'admin' && alertCount > 0 && <span className="nav-badge">{alertCount}</span>}
            </button>
          ))}
        </nav>

        {user.must_change_password && !showPasswordModal && (
          <div className="banner banner-warning">
            Vous utilisez encore le mot de passe initial fourni par l'administrateur.
            {' '}
            <button className="btn btn-sm btn-outline" onClick={() => setShowPasswordModal(true)}>
              Le changer maintenant
            </button>
          </div>
        )}

        {tab === 'veille' && <VeillePage user={user} onSelectionsChanged={loadDashboard} />}
        {tab === 'journaux' && <JournauxPage user={user} onChanged={loadDashboard} />}
        {tab === 'dossiers' && <DossiersPage user={user} onChanged={loadDashboard} />}
        {tab === 'prix' && <PricesPage user={user} />}
        {tab === 'admin' && <AdminPage dashboard={dashboard} onChanged={loadDashboard} />}

        <footer className="app-footer">
          <p>
            Veille automatique sur une vingtaine de sources publiques (Sénégal, UEMOA, bailleurs
            internationaux) complétée par le relevé quotidien de la presse papier.
          </p>
        </footer>
      </div>

      {showPasswordModal && (
        <ChangePasswordModal
          forced={user.must_change_password}
          onClose={() => setShowPasswordModal(false)}
          onDone={(updated) => { setUser(updated); setShowPasswordModal(false) }}
        />
      )}
    </>
  )
}
