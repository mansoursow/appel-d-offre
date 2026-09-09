import { useCallback, useEffect, useState } from 'react'
import * as api from '../api.js'
import Modal from './Modal.jsx'
import { JOURNAL_STATUS_LABELS, formatDate, formatDateTime } from '../utils.js'

const ROLE_OPTIONS = [
  { value: 'admin', label: 'Administrateur' },
  { value: 'assistante', label: 'Assistante (journaux)' },
  { value: 'selectionneur', label: 'Sélection des avis' },
  { value: 'monteur', label: 'Montage des dossiers' },
]

const ROLE_LABELS = Object.fromEntries(ROLE_OPTIONS.map((r) => [r.value, r.label]))

const ACTION_LABELS = {
  connexion: 'Connexion',
  deconnexion: 'Déconnexion',
  changement_mot_de_passe: 'Mot de passe changé',
  depot_journaux: 'Dépôt de journaux',
  declaration_journaux: 'Déclaration NÉANT / RAS',
  suppression_photo_journal: 'Suppression de photo',
  avis_retenu: 'Avis retenu',
  avis_rejete: 'Avis écarté',
  modification_decision: 'Décision modifiée',
  depot_offre: 'Offre déposée',
  suppression_offre: 'Offre retirée',
  collecte_veille: 'Collecte de la veille',
  creation_compte: 'Compte créé',
  modification_compte: 'Compte modifié',
}

const SUB_TABS = [
  { key: 'alertes', label: 'Alertes' },
  { key: 'journaux', label: 'Suivi des journaux' },
  { key: 'activite', label: "Journal d'activité" },
  { key: 'comptes', label: 'Comptes' },
]

export default function AdminPage({ dashboard, onChanged }) {
  const [sub, setSub] = useState('alertes')

  return (
    <div className="stack">
      <section className="card card-pad">
        <div className="section-title">
          <div>
            <h2>Supervision</h2>
            <p>
              Dépôts de journaux manquants, décisions de soumission et dossiers dont les
              offres ne sont pas jointes.
            </p>
          </div>
        </div>

        <div className="stat-grid">
          <div className={`stat${dashboard?.journal_today_done ? ' stat-ok' : ' stat-alert'}`}>
            <div className="stat-value">{dashboard?.journal_today_done ? 'Oui' : 'Non'}</div>
            <div className="stat-label">journaux déposés aujourd'hui</div>
          </div>
          <div className={`stat${dashboard?.journal_missing_days ? ' stat-alert' : ' stat-ok'}`}>
            <div className="stat-value">{dashboard?.journal_missing_days ?? '—'}</div>
            <div className="stat-label">journées manquantes (30 j)</div>
          </div>
          <div className="stat">
            <div className="stat-value">{dashboard?.selections_retenues ?? '—'}</div>
            <div className="stat-label">avis retenus</div>
          </div>
          <div className={`stat${dashboard?.dossiers_incomplets ? ' stat-alert' : ' stat-ok'}`}>
            <div className="stat-value">{dashboard?.dossiers_incomplets ?? '—'}</div>
            <div className="stat-label">dossiers incomplets</div>
          </div>
          <div className={`stat${dashboard?.dossiers_en_retard ? ' stat-alert' : ' stat-ok'}`}>
            <div className="stat-value">{dashboard?.dossiers_en_retard ?? '—'}</div>
            <div className="stat-label">dossiers en retard</div>
          </div>
        </div>
      </section>

      <div className="main-nav" style={{ marginBottom: 0 }}>
        {SUB_TABS.map((tab) => (
          <button
            key={tab.key}
            className={`nav-tab${sub === tab.key ? ' is-active' : ''}`}
            onClick={() => setSub(tab.key)}
          >
            {tab.label}
            {tab.key === 'alertes' && dashboard?.alerts?.length > 0 && (
              <span className="nav-badge">{dashboard.alerts.length}</span>
            )}
          </button>
        ))}
      </div>

      {sub === 'alertes' && <AlertsPanel alerts={dashboard?.alerts || []} />}
      {sub === 'journaux' && <CompliancePanel />}
      {sub === 'activite' && <LogsPanel />}
      {sub === 'comptes' && <UsersPanel onChanged={onChanged} />}
    </div>
  )
}

// --------------------------------------------------------------------------
function AlertsPanel({ alerts }) {
  return (
    <section className="card card-pad">
      <div className="section-title">
        <div>
          <h2>Ce qui n'a pas été fait</h2>
          <p>
            Journées ouvrées sans dépôt de journaux, et dossiers retenus dont l'offre
            technique ou financière manque à l'approche de l'échéance.
          </p>
        </div>
      </div>

      {alerts.length === 0 ? (
        <div className="banner banner-success" style={{ marginBottom: 0 }}>
          Aucune alerte : les journaux sont à jour et tous les dossiers en cours sont complets.
        </div>
      ) : (
        <div className="alert-list">
          {alerts.map((alert, index) => (
            <div key={`${alert.kind}-${alert.date}-${index}`} className={`alert-item alert-${alert.severity}`}>
              <div>
                <strong>{alert.title}</strong>
                <p>{alert.detail}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

// --------------------------------------------------------------------------
function CompliancePanel() {
  const [users, setUsers] = useState([])
  const [userId, setUserId] = useState('')
  const [days, setDays] = useState(30)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.fetchUsers()
      .then((list) => setUsers(list.filter((u) => u.role === 'assistante')))
      .catch(() => setUsers([]))
  }, [])

  useEffect(() => {
    api.fetchAdminCompliance({ days, userId: userId || undefined })
      .then(setData)
      .catch((e) => setError(e.message))
  }, [days, userId])

  return (
    <section className="card card-pad">
      <div className="section-title">
        <div>
          <h2>Suivi des dépôts de journaux</h2>
          <p>Jour par jour : ce qui a été déposé, et les journées restées vides.</p>
        </div>
        <div className="row">
          <select className="select" value={userId} onChange={(e) => setUserId(e.target.value)}>
            <option value="">Tous les comptes</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>{u.full_name || u.username}</option>
            ))}
          </select>
          <select className="select" value={days} onChange={(e) => setDays(Number(e.target.value))}>
            <option value={15}>15 jours</option>
            <option value={30}>30 jours</option>
            <option value={90}>90 jours</option>
            <option value={180}>6 mois</option>
          </select>
        </div>
      </div>

      {error && <div className="banner banner-error">{error}</div>}

      {data && (
        <>
          <div className="stat-grid" style={{ marginBottom: 16 }}>
            <div className="stat stat-ok">
              <div className="stat-value">{data.days_done}</div>
              <div className="stat-label">journées déposées</div>
            </div>
            <div className={`stat${data.days_missing ? ' stat-alert' : ' stat-ok'}`}>
              <div className="stat-value">{data.days_missing}</div>
              <div className="stat-label">journées manquantes</div>
            </div>
            <div className="stat">
              <div className="stat-value">{data.completion_rate}%</div>
              <div className="stat-label">taux de suivi</div>
            </div>
          </div>

          <div className="day-list">
            {data.days.map((day) => (
              <div
                key={day.date}
                className={
                  'day-row'
                  + (day.done ? ' day-row-done' : '')
                  + (day.is_missing ? ' day-row-missing' : '')
                  + (!day.is_working_day && !day.done ? ' day-row-off' : '')
                }
              >
                <span className="day-dot" />
                <span className="day-label">
                  <strong>{day.weekday} {formatDate(day.date)}</strong>{' '}
                  <span>
                    {day.done
                      ? JOURNAL_STATUS_LABELS[day.status] + (day.photo_count ? ` (${day.photo_count} fichier(s))` : '')
                      : day.is_missing
                        ? 'NON FAIT — journée ouvrée sans dépôt'
                        : day.is_working_day ? 'En attente' : 'Jour non ouvré'}
                  </span>
                </span>
                <span className="day-meta">
                  {day.user_name || ''}
                  {day.submitted_at ? ` · ${formatDateTime(day.submitted_at)}` : ''}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  )
}

// --------------------------------------------------------------------------
function LogsPanel() {
  const [logs, setLogs] = useState([])
  const [role, setRole] = useState('')
  const [action, setAction] = useState('')
  const [error, setError] = useState(null)

  useEffect(() => {
    api.fetchActivityLogs({ role: role || undefined, action: action || undefined, limit: 300 })
      .then(setLogs)
      .catch((e) => setError(e.message))
  }, [role, action])

  return (
    <section className="card card-pad">
      <div className="section-title">
        <div>
          <h2>Journal d'activité</h2>
          <p>Qui a fait quoi, et quand. Chaque décision et chaque dépôt y figure.</p>
        </div>
        <div className="row">
          <select className="select" value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="">Tous les profils</option>
            {ROLE_OPTIONS.map((r) => (
              <option key={r.value} value={r.value}>{r.label}</option>
            ))}
          </select>
          <select className="select" value={action} onChange={(e) => setAction(e.target.value)}>
            <option value="">Toutes les actions</option>
            {Object.entries(ACTION_LABELS).map(([key, label]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>
        </div>
      </div>

      {error && <div className="banner banner-error">{error}</div>}

      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>Date</th>
              <th>Utilisateur</th>
              <th>Profil</th>
              <th>Action</th>
              <th>Détail</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log) => (
              <tr key={log.id}>
                <td style={{ whiteSpace: 'nowrap' }}>{formatDateTime(log.created_at)}</td>
                <td>{log.username || '—'}</td>
                <td>{ROLE_LABELS[log.role] || log.role || '—'}</td>
                <td>{ACTION_LABELS[log.action] || log.action}</td>
                <td>{log.detail || '—'}</td>
              </tr>
            ))}
            {logs.length === 0 && (
              <tr><td colSpan={5} className="muted">Aucune activité enregistrée.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}

// --------------------------------------------------------------------------
function UsersPanel({ onChanged }) {
  const [users, setUsers] = useState([])
  const [error, setError] = useState(null)
  const [message, setMessage] = useState(null)
  const [creating, setCreating] = useState(false)

  const load = useCallback(() => {
    api.fetchUsers().then(setUsers).catch((e) => setError(e.message))
  }, [])

  useEffect(() => { load() }, [load])

  async function toggleActive(user) {
    setError(null)
    try {
      await api.updateUser(user.id, { is_active: !user.is_active })
      load()
      onChanged?.()
    } catch (e) {
      setError(e.message)
    }
  }

  async function resetPassword(user) {
    const value = window.prompt(
      `Nouveau mot de passe provisoire pour ${user.username} (6 caractères minimum) :`,
    )
    if (!value) return
    setError(null)
    try {
      await api.updateUser(user.id, { new_password: value })
      setMessage(`Mot de passe de ${user.username} réinitialisé. Il devra le changer à sa prochaine connexion.`)
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <section className="card card-pad">
      <div className="section-title">
        <div>
          <h2>Comptes</h2>
          <p>Un compte par rôle : assistante, sélection, montage, administration.</p>
        </div>
        <button className="btn" onClick={() => setCreating(true)}>Créer un compte</button>
      </div>

      {error && <div className="banner banner-error">{error}</div>}
      {message && <div className="banner banner-success">{message}</div>}

      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>Identifiant</th>
              <th>Nom</th>
              <th>Profil</th>
              <th>État</th>
              <th>Dernière connexion</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id}>
                <td><strong>{user.username}</strong></td>
                <td>{user.full_name || '—'}</td>
                <td>{ROLE_LABELS[user.role] || user.role}</td>
                <td>
                  {user.is_active
                    ? <span className="badge badge-retenu">Actif</span>
                    : <span className="badge badge-rejete">Désactivé</span>}
                  {user.must_change_password && (
                    <span className="badge badge-outline" style={{ marginLeft: 6 }}>
                      mot de passe à changer
                    </span>
                  )}
                </td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  {user.last_login_at ? formatDateTime(user.last_login_at) : 'jamais'}
                </td>
                <td>
                  <div className="row">
                    <button className="btn btn-sm btn-outline" onClick={() => resetPassword(user)}>
                      Réinitialiser
                    </button>
                    <button className="btn btn-sm btn-outline" onClick={() => toggleActive(user)}>
                      {user.is_active ? 'Désactiver' : 'Réactiver'}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {creating && (
        <CreateUserModal
          onClose={() => setCreating(false)}
          onCreated={() => { setCreating(false); load(); onChanged?.() }}
        />
      )}
    </section>
  )
}

function CreateUserModal({ onClose, onCreated }) {
  const [form, setForm] = useState({ username: '', full_name: '', role: 'assistante', password: '' })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.createUser(form)
      onCreated()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const set = (key) => (e) => setForm((prev) => ({ ...prev, [key]: e.target.value }))

  return (
    <Modal
      title="Créer un compte"
      subtitle="L'utilisateur devra changer ce mot de passe à sa première connexion."
      onClose={onClose}
    >
      {error && <div className="banner banner-error">{error}</div>}
      <form className="stack" onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="nu-username">Identifiant</label>
          <input id="nu-username" className="input" minLength={3} required
                 value={form.username} onChange={set('username')} />
        </div>
        <div className="field">
          <label htmlFor="nu-name">Nom complet</label>
          <input id="nu-name" className="input" value={form.full_name} onChange={set('full_name')} />
        </div>
        <div className="field">
          <label htmlFor="nu-role">Profil</label>
          <select id="nu-role" className="select" value={form.role} onChange={set('role')}>
            {ROLE_OPTIONS.map((r) => (
              <option key={r.value} value={r.value}>{r.label}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="nu-password">Mot de passe provisoire</label>
          <input id="nu-password" type="text" className="input" minLength={6} required
                 value={form.password} onChange={set('password')} />
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-outline" onClick={onClose}>Annuler</button>
          <button type="submit" className="btn" disabled={busy}>
            {busy ? 'Création…' : 'Créer le compte'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
