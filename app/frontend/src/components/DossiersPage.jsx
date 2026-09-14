import { useCallback, useEffect, useMemo, useState } from 'react'
import * as api from '../api.js'
import {
  CATEGORY_LABELS, DOSSIER_STATUS_LABELS, SELECTION_ROLES,
  deadlineHint, formatDate, formatDateTime, formatSize, userLabel,
} from '../utils.js'

const DOC_TYPES = [
  { key: 'technique', label: 'Offre technique' },
  { key: 'financiere', label: 'Offre financière' },
]

/**
 * Dossiers de soumission : pour chaque avis retenu, l'offre technique et
 * l'offre financière doivent être jointes avant la date limite. Tant qu'une
 * pièce manque, le dossier reste signalé (et remonte chez l'administrateur).
 */
export default function DossiersPage({ user, onChanged }) {
  const [selections, setSelections] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [message, setMessage] = useState(null)
  const [busyId, setBusyId] = useState(null)
  const [filter, setFilter] = useState('a_traiter')
  const [onlyMine, setOnlyMine] = useState(user.role === 'monteur')

  const canUpload = user.role === 'monteur' || user.role === 'admin'
  // Admin / sélection / superviseur peuvent confier (ou reconfier) un dossier.
  const canAssign = SELECTION_ROLES.includes(user.role)
  const [monteurs, setMonteurs] = useState([])

  useEffect(() => {
    if (!canAssign) return
    api.fetchAssignableUsers().then(setMonteurs).catch(() => setMonteurs([]))
  }, [canAssign])

  async function handleAssign(selection, userId) {
    if (!userId || Number(userId) === selection.assigned_to_id) return
    setBusyId(selection.id)
    setError(null)
    setMessage(null)
    try {
      const updated = await api.updateSelection(selection.id, { assigned_to_id: Number(userId) })
      setSelections((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))
      setMessage(
        `Dossier confié à ${updated.assigned_to_name}. Il est prévenu par e-mail si son adresse est renseignée `
        + '(résultat visible dans le journal d\'activité).',
      )
      onChanged?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusyId(null)
    }
  }

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setSelections(await api.fetchSelections())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const visible = useMemo(() => {
    let list = selections
    if (onlyMine) list = list.filter((s) => s.assigned_to_id === user.id)
    if (filter === 'a_traiter') {
      list = list.filter((s) => ['en_cours', 'urgent', 'en_retard'].includes(s.dossier_status))
    } else if (filter !== 'tous') {
      list = list.filter((s) => s.dossier_status === filter)
    }
    // Les échéances les plus proches d'abord ; les dossiers sans date ensuite.
    return [...list].sort((a, b) => {
      if (a.days_left === null) return 1
      if (b.days_left === null) return -1
      return a.days_left - b.days_left
    })
  }, [selections, filter, onlyMine, user.id])

  const counts = useMemo(() => {
    const retenus = selections.filter((s) => s.decision === 'retenu')
    return {
      retenus: retenus.length,
      complets: retenus.filter((s) => s.dossier_status === 'complet').length,
      enRetard: retenus.filter((s) => s.dossier_status === 'en_retard').length,
      urgents: retenus.filter((s) => s.dossier_status === 'urgent').length,
    }
  }, [selections])

  async function handleUpload(selection, docType, file) {
    if (!file) return
    setBusyId(selection.id)
    setError(null)
    setMessage(null)
    try {
      const updated = await api.uploadSubmissionDocument(selection.id, docType, file)
      setSelections((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))
      setMessage(
        updated.is_complete
          ? `Dossier complet : « ${updated.title.slice(0, 70)} » est prêt à être déposé.`
          : 'Pièce enregistrée. Il reste ' + updated.missing_documents.join(' et ') + '.',
      )
      onChanged?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusyId(null)
    }
  }

  async function handleDeleteDoc(selection, doc) {
    if (!window.confirm(`Retirer « ${doc.original_name} » du dossier ?`)) return
    setBusyId(selection.id)
    setError(null)
    try {
      const updated = await api.deleteSubmissionDocument(doc.id)
      setSelections((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))
      onChanged?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusyId(null)
    }
  }

  async function handleDeleteSelection(selection) {
    const pieces = selection.documents.length
    const ok = window.confirm(
      `Retirer le dossier « ${selection.title.slice(0, 90)} » ?\n\n`
      + (pieces ? `Les ${pieces} pièce(s) jointe(s) seront définitivement supprimées.\n` : '')
      + "L'avis redeviendra « sans décision » et pourra être retenu à nouveau.",
    )
    if (!ok) return
    setBusyId(selection.id)
    setError(null)
    setMessage(null)
    try {
      await api.deleteSelection(selection.id)
      setSelections((prev) => prev.filter((s) => s.id !== selection.id))
      setMessage(`Dossier « ${selection.title.slice(0, 70)} » retiré.`)
      onChanged?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="stack">
      {error && <div className="banner banner-error">{error}</div>}
      {message && <div className="banner banner-success">{message}</div>}

      <section className="card card-pad">
        <div className="section-title">
          <div>
            <h2>Dossiers de soumission</h2>
            <p>
              Chaque avis retenu attend son offre technique et son offre financière
              avant la date limite.
            </p>
          </div>
        </div>

        <div className="stat-grid" style={{ marginBottom: 16 }}>
          <div className="stat">
            <div className="stat-value">{counts.retenus}</div>
            <div className="stat-label">avis retenus</div>
          </div>
          <div className="stat stat-ok">
            <div className="stat-value">{counts.complets}</div>
            <div className="stat-label">dossiers complets</div>
          </div>
          <div className={`stat${counts.urgents ? ' stat-alert' : ''}`}>
            <div className="stat-value">{counts.urgents}</div>
            <div className="stat-label">échéances proches</div>
          </div>
          <div className={`stat${counts.enRetard ? ' stat-alert' : ''}`}>
            <div className="stat-value">{counts.enRetard}</div>
            <div className="stat-label">dossiers en retard</div>
          </div>
        </div>

        <div className="row">
          <select className="select" value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="a_traiter">À compléter</option>
            <option value="en_retard">En retard</option>
            <option value="urgent">Échéance proche</option>
            <option value="complet">Dossiers complets</option>
            <option value="rejete">Avis écartés</option>
            <option value="tous">Tous</option>
          </select>
          <label className="checkbox-label">
            <input type="checkbox" checked={onlyMine} onChange={(e) => setOnlyMine(e.target.checked)} />
            Seulement les dossiers qui me sont confiés
          </label>
        </div>
      </section>

      {loading && <p className="empty-state">Chargement…</p>}
      {!loading && visible.length === 0 && (
        <p className="empty-state">Aucun dossier ne correspond à ce filtre.</p>
      )}

      <div className="stack">
        {visible.map((selection) => {
          const docsByType = new Map(selection.documents.map((d) => [d.doc_type, d]))
          const mine = selection.assigned_to_id === user.id
          const editable = canUpload && selection.decision === 'retenu' && (mine || user.role === 'admin')

          return (
            <article key={selection.id} className={`dossier-card dossier-${selection.dossier_status}`}>
              <div className="dossier-head">
                <div style={{ flex: 1, minWidth: 240 }}>
                  <h3>
                    {selection.url ? (
                      <a href={selection.url} target="_blank" rel="noopener noreferrer"
                         style={{ color: 'inherit' }}>
                        {selection.title}
                      </a>
                    ) : selection.title}
                  </h3>
                  <div className="tender-card-header">
                    {selection.category && (
                      <span className={`badge badge-${selection.category}`}>
                        {CATEGORY_LABELS[selection.category] || selection.category}
                      </span>
                    )}
                    {selection.journal_photo_id && (
                      <span className="badge badge-outline">Presse papier</span>
                    )}
                    {selection.entity && <span className="badge badge-source">{selection.entity}</span>}
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <span className={`status-pill status-${selection.dossier_status}`}>
                    {DOSSIER_STATUS_LABELS[selection.dossier_status]}
                  </span>
                  <p className="muted" style={{ margin: '6px 0 0' }}>
                    {selection.deadline_iso
                      ? `${formatDate(selection.deadline_iso)} · ${deadlineHint(selection.days_left)}`
                      : 'Échéance non renseignée'}
                  </p>
                  {user.role === 'admin' && (
                    <button
                      className="btn btn-ghost"
                      style={{ marginTop: 6 }}
                      disabled={busyId === selection.id}
                      onClick={() => handleDeleteSelection(selection)}
                    >
                      Retirer le dossier
                    </button>
                  )}
                </div>
              </div>

              <div className="row muted" style={{ marginTop: 8 }}>
                <span>Retenu par {selection.selected_by_name} le {formatDateTime(selection.created_at)}</span>
                <span>·</span>
                {canAssign && selection.decision === 'retenu' ? (
                  <label className="row" style={{ gap: 6 }}>
                    Montage :
                    <select
                      className="select"
                      style={{ width: 'auto', padding: '4px 8px' }}
                      value={selection.assigned_to_id || ''}
                      disabled={busyId === selection.id}
                      onChange={(e) => handleAssign(selection, e.target.value)}
                    >
                      {!selection.assigned_to_id && <option value="">— non assigné —</option>}
                      {selection.assigned_to_id && !monteurs.some((u) => u.id === selection.assigned_to_id) && (
                        <option value={selection.assigned_to_id}>{selection.assigned_to_name}</option>
                      )}
                      {monteurs.map((u) => (
                        <option key={u.id} value={u.id}>{userLabel(u)}</option>
                      ))}
                    </select>
                  </label>
                ) : (
                  <span>Montage : {selection.assigned_to_name || <em>non assigné</em>}</span>
                )}
              </div>
              {selection.comment && (
                <p className="tender-description">« {selection.comment} »</p>
              )}

              {selection.decision === 'retenu' && (
                <div className="doc-slots">
                  {DOC_TYPES.map(({ key, label }) => {
                    const doc = docsByType.get(key)
                    return (
                      <div
                        key={key}
                        className={`doc-slot ${doc ? 'doc-slot-filled' : 'doc-slot-missing'}`}
                      >
                        <h5>{label}</h5>
                        {doc ? (
                          <>
                            <a href={api.fileUrl(doc.file_url)} target="_blank" rel="noopener noreferrer">
                              {doc.original_name}
                            </a>
                            <p className="muted" style={{ margin: '4px 0 0' }}>
                              {formatSize(doc.size_bytes)} · déposée par {doc.uploaded_by_name}
                              {' '}le {formatDateTime(doc.uploaded_at)}
                            </p>
                            {editable && (
                              <div className="row" style={{ marginTop: 8 }}>
                                <label className="btn btn-sm btn-outline" style={{ cursor: 'pointer' }}>
                                  Remplacer
                                  <input
                                    type="file" style={{ display: 'none' }}
                                    disabled={busyId === selection.id}
                                    onChange={(e) => handleUpload(selection, key, e.target.files?.[0])}
                                  />
                                </label>
                                <button
                                  className="btn btn-ghost"
                                  disabled={busyId === selection.id}
                                  onClick={() => handleDeleteDoc(selection, doc)}
                                >
                                  Retirer
                                </button>
                              </div>
                            )}
                          </>
                        ) : (
                          <>
                            <p className="muted" style={{ margin: 0 }}>Pièce non jointe.</p>
                            {editable ? (
                              <label className="btn btn-sm" style={{ cursor: 'pointer', marginTop: 8 }}>
                                Joindre le fichier
                                <input
                                  type="file" style={{ display: 'none' }}
                                  disabled={busyId === selection.id}
                                  onChange={(e) => handleUpload(selection, key, e.target.files?.[0])}
                                />
                              </label>
                            ) : (
                              <p className="muted" style={{ marginTop: 6 }}>
                                {canUpload
                                  ? 'Ce dossier est confié à un autre compte.'
                                  : 'Dépôt réservé au profil « montage ».'}
                              </p>
                            )}
                          </>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </article>
          )
        })}
      </div>
    </div>
  )
}
