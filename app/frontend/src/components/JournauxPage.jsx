import { useCallback, useEffect, useState } from 'react'
import * as api from '../api.js'
import DecisionModal from './DecisionModal.jsx'
import {
  JOURNAL_STATUS_LABELS, SELECTION_ROLES, formatDate, formatDateTime, formatSize, isImage, todayIso,
} from '../utils.js'

/**
 * Journaux papier : l'assistante photographie chaque jour les avis parus dans
 * la presse, ou déclare NÉANT / RAS s'il n'y en a aucun. L'historique montre
 * en rouge les journées ouvrées restées sans dépôt.
 */
export default function JournauxPage({ user, onChanged }) {
  const [today, setToday] = useState(null)
  const [entries, setEntries] = useState([])
  const [compliance, setCompliance] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [message, setMessage] = useState(null)
  const [busy, setBusy] = useState(false)
  const [pending, setPending] = useState(null)

  const [newspaper, setNewspaper] = useState('')
  const [caption, setCaption] = useState('')
  const [entryDate, setEntryDate] = useState(todayIso())

  const isAssistante = user.role === 'assistante' || user.role === 'admin'
  const canSelect = SELECTION_ROLES.includes(user.role)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [todayEntry, list, comp] = await Promise.all([
        isAssistante ? api.fetchJournalToday() : Promise.resolve(null),
        api.fetchJournalEntries({ limit: 30 }),
        api.fetchJournalCompliance({ days: 30 }),
      ])
      setToday(todayEntry)
      setEntries(list)
      setCompliance(comp)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [isAssistante])

  useEffect(() => { load() }, [load])

  async function run(action, successMessage) {
    setBusy(true)
    setError(null)
    setMessage(null)
    try {
      await action()
      setMessage(successMessage)
      await load()
      onChanged?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  function handleFiles(event) {
    const files = Array.from(event.target.files || [])
    if (!files.length) return
    event.target.value = ''
    run(
      () => api.uploadJournalPhotos({ files, entryDate, newspaper, caption }),
      `${files.length} fichier(s) joint(s) au ${formatDate(entryDate)}.`,
    ).then(() => { setCaption('') })
  }

  function handleDeclare(status) {
    const label = status === 'neant' ? 'NÉANT' : 'RAS'
    if (!window.confirm(
      `Confirmer « ${label} » pour le ${formatDate(entryDate)} ?\n\n` +
      "Cela indique qu'aucun avis n'est paru dans la presse ce jour-là.",
    )) return
    run(
      () => api.declareJournalStatus({ status, entryDate }),
      `Journée du ${formatDate(entryDate)} déclarée « ${label} ».`,
    )
  }

  function handleDeletePhoto(photo) {
    if (!window.confirm(`Supprimer « ${photo.original_name} » ?`)) return
    run(() => api.deleteJournalPhoto(photo.id), 'Photo supprimée.')
  }

  const todayDone = compliance?.today_done
  const currentIsToday = entryDate === todayIso()

  return (
    <div className="stack">
      {error && <div className="banner banner-error">{error}</div>}
      {message && <div className="banner banner-success">{message}</div>}

      {isAssistante && (
        <section className="card card-pad today-panel">
          <div className="section-title">
            <div>
              <h2>Dépôt des journaux</h2>
              <p>
                Chaque jour ouvré : joindre la photo des avis parus dans la presse papier,
                ou déclarer NÉANT / RAS s'il n'y en a aucun.
              </p>
            </div>
            <span className={`today-status ${todayDone ? 'today-status-done' : 'today-status-todo'}`}>
              {todayDone ? "✓ Dépôt du jour effectué" : "⚠ Dépôt du jour non effectué"}
            </span>
          </div>

          <div className="row" style={{ marginBottom: 14 }}>
            <div className="field" style={{ minWidth: 190 }}>
              <label htmlFor="j-date">Journée concernée</label>
              <input
                id="j-date" type="date" className="input" max={todayIso()}
                value={entryDate} onChange={(e) => setEntryDate(e.target.value)}
              />
            </div>
            <div className="field" style={{ minWidth: 200 }}>
              <label htmlFor="j-newspaper">Journal</label>
              <input
                id="j-newspaper" className="input" placeholder="Le Soleil, EnQuête…"
                value={newspaper} onChange={(e) => setNewspaper(e.target.value)}
              />
            </div>
            <div className="field" style={{ flex: 1, minWidth: 240 }}>
              <label htmlFor="j-caption">Intitulé de l'avis (facultatif)</label>
              <input
                id="j-caption" className="input" placeholder="AO construction école — Ministère…"
                value={caption} onChange={(e) => setCaption(e.target.value)}
              />
            </div>
          </div>

          {!currentIsToday && (
            <div className="banner banner-warning">
              Vous complétez une journée passée ({formatDate(entryDate)}). La date et l'heure
              réelles du dépôt restent visibles par l'administrateur.
            </div>
          )}

          <label className="dropzone">
            <input type="file" multiple accept="image/*,.pdf" onChange={handleFiles} disabled={busy} />
            <strong>Joindre les photos des journaux</strong>
            <span>
              Photos ou scans (JPG, PNG, WEBP, HEIC, PDF) — plusieurs fichiers possibles en une fois
            </span>
          </label>

          <div className="row" style={{ marginTop: 16, alignItems: 'center' }}>
            <span className="muted">Aucun avis paru ce jour ?</span>
            <div className="declare-buttons">
              <button className="btn btn-neant" onClick={() => handleDeclare('neant')} disabled={busy}>
                NÉANT
              </button>
              <button className="btn btn-ras" onClick={() => handleDeclare('ras')} disabled={busy}>
                RAS
              </button>
            </div>
          </div>

          {today && (
            <p className="muted" style={{ marginTop: 14 }}>
              Aujourd'hui : <strong>{JOURNAL_STATUS_LABELS[today.status]}</strong>
              {today.photos.length > 0 && ` — ${today.photos.length} fichier(s)`}
              {today.created_at && ` · déposé le ${formatDateTime(today.created_at)}`}
            </p>
          )}
        </section>
      )}

      <section className="card card-pad">
        <div className="section-title">
          <div>
            <h2>Avis relevés dans la presse</h2>
            <p>
              {canSelect
                ? 'Retenez ici les avis parus dans les journaux papier sur lesquels soumissionner.'
                : 'Historique des avis photographiés.'}
            </p>
          </div>
        </div>

        {loading && <p className="empty-state">Chargement…</p>}
        {!loading && entries.length === 0 && (
          <p className="empty-state">Aucun dépôt enregistré pour le moment.</p>
        )}

        <div className="stack">
          {entries.map((entry) => (
            <div key={entry.id} className="card card-pad">
              <div className="row" style={{ justifyContent: 'space-between', marginBottom: 10 }}>
                <strong style={{ color: 'var(--adoc-navy)' }}>
                  {formatDate(entry.entry_date)} — {JOURNAL_STATUS_LABELS[entry.status]}
                </strong>
                <span className="muted">
                  {entry.user_name} · déposé le {formatDateTime(entry.created_at)}
                </span>
              </div>

              {entry.note && <p className="muted">Note : {entry.note}</p>}

              {entry.photos.length === 0 ? (
                <p className="muted">
                  {entry.status === 'photos'
                    ? 'Aucun fichier joint.'
                    : `Déclaré « ${JOURNAL_STATUS_LABELS[entry.status]} » : aucun avis paru ce jour.`}
                </p>
              ) : (
                <div className="photo-grid">
                  {entry.photos.map((photo) => (
                    <div key={photo.id} className="photo-card">
                      <a href={api.fileUrl(photo.file_url)} target="_blank" rel="noopener noreferrer">
                        {isImage(photo.content_type, photo.original_name) ? (
                          <img
                            className="photo-thumb"
                            src={api.fileUrl(photo.file_url)}
                            alt={photo.caption || photo.original_name}
                            loading="lazy"
                          />
                        ) : (
                          <div className="photo-thumb-fallback">
                            Ouvrir le document<br />{photo.original_name}
                          </div>
                        )}
                      </a>
                      <div className="photo-body">
                        <h4>{photo.caption || photo.original_name}</h4>
                        <p>
                          {photo.newspaper ? `${photo.newspaper} · ` : ''}{formatSize(photo.size_bytes)}
                        </p>
                        {photo.selection_id && (
                          <p style={{ marginTop: 4 }}>
                            <span className={`badge badge-${photo.selection_decision}`}>
                              {photo.selection_decision === 'retenu' ? 'Retenu' : 'Non retenu'}
                            </span>
                          </p>
                        )}
                      </div>
                      <div className="photo-actions">
                        {canSelect && !photo.selection_id && (
                          <>
                            <button
                              className="btn btn-sm"
                              onClick={() => setPending({
                                decision: 'retenu',
                                avis: {
                                  kind: 'photo',
                                  id: photo.id,
                                  title: photo.caption || `Avis presse — ${photo.newspaper || photo.original_name}`,
                                  entity: photo.newspaper,
                                  category: 'appel_offre',
                                },
                              })}
                            >
                              Retenir
                            </button>
                            <button
                              className="btn btn-sm btn-outline"
                              onClick={() => setPending({
                                decision: 'rejete',
                                avis: {
                                  kind: 'photo',
                                  id: photo.id,
                                  title: photo.caption || `Avis presse — ${photo.newspaper || photo.original_name}`,
                                  entity: photo.newspaper,
                                },
                              })}
                            >
                              Écarter
                            </button>
                          </>
                        )}
                        {isAssistante && !photo.selection_id && (
                          <button className="btn btn-ghost" onClick={() => handleDeletePhoto(photo)}>
                            Supprimer
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {compliance && (
        <section className="card card-pad">
          <div className="section-title">
            <div>
              <h2>Suivi des dépôts — 30 derniers jours</h2>
              <p>
                {user.role === 'assistante'
                  ? 'Votre historique personnel.'
                  : 'Historique de tous les comptes. Les journées en rouge sont restées sans dépôt.'}
              </p>
            </div>
          </div>

          <div className="stat-grid" style={{ marginBottom: 16 }}>
            <div className="stat stat-ok">
              <div className="stat-value">{compliance.days_done}</div>
              <div className="stat-label">journées déposées</div>
            </div>
            <div className={`stat${compliance.days_missing ? ' stat-alert' : ' stat-ok'}`}>
              <div className="stat-value">{compliance.days_missing}</div>
              <div className="stat-label">journées ouvrées manquantes</div>
            </div>
            <div className="stat">
              <div className="stat-value">{compliance.completion_rate}%</div>
              <div className="stat-label">taux de suivi</div>
            </div>
          </div>

          <div className="day-list">
            {compliance.days.map((day) => (
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
                      ? JOURNAL_STATUS_LABELS[day.status] + (day.photo_count ? ` (${day.photo_count})` : '')
                      : day.is_missing
                        ? 'Aucun dépôt — journée ouvrée'
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
        </section>
      )}

      {pending && (
        <DecisionModal
          avis={pending.avis}
          decision={pending.decision}
          onClose={() => setPending(null)}
          onSaved={() => { setPending(null); load(); onChanged?.() }}
        />
      )}
    </div>
  )
}
