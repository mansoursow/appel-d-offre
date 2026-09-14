import { useEffect, useState } from 'react'
import Modal from './Modal.jsx'
import * as api from '../api.js'
import { formatDate } from '../utils.js'

/**
 * Fenêtre de décision du responsable sélection : retenir ou écarter un avis,
 * fixer l'échéance si la source ne l'a pas donnée, et désigner qui montera le
 * dossier (offres technique et financière).
 */
export default function DecisionModal({ avis, decision, onClose, onSaved }) {
  const [comment, setComment] = useState('')
  const [deadline, setDeadline] = useState(avis.deadline_iso || '')
  const [assignedTo, setAssignedTo] = useState('')
  const [monteurs, setMonteurs] = useState([])
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const retenu = decision === 'retenu'

  useEffect(() => {
    if (!retenu) return
    api.fetchAssignableUsers()
      .then(setMonteurs)
      .catch(() => setMonteurs([]))
  }, [retenu])

  async function handleSubmit(event) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const saved = await api.createSelection({
        tender_id: avis.kind === 'tender' ? avis.id : null,
        journal_photo_id: avis.kind === 'photo' ? avis.id : null,
        decision,
        comment: comment || null,
        deadline_iso: deadline || null,
        assigned_to_id: assignedTo ? Number(assignedTo) : null,
        title: avis.title || null,
        entity: avis.entity || null,
        category: avis.category || null,
        url: avis.url || null,
      })
      onSaved(saved)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      title={retenu ? 'Retenir cet avis' : 'Écarter cet avis'}
      subtitle={avis.title}
      onClose={onClose}
    >
      {error && <div className="banner banner-error">{error}</div>}

      <form className="stack" onSubmit={handleSubmit}>
        {retenu && (
          <>
            <div className="field">
              <label htmlFor="dec-deadline">Date limite de dépôt</label>
              <input
                id="dec-deadline"
                type="date"
                className="input"
                value={deadline}
                onChange={(e) => setDeadline(e.target.value)}
              />
              <span className="muted">
                {avis.deadline_iso
                  ? `Échéance relevée sur la source : ${formatDate(avis.deadline_iso)}`
                  : "Aucune échéance trouvée automatiquement : saisissez-la pour que les rappels fonctionnent."}
              </span>
            </div>

            <div className="field">
              <label htmlFor="dec-assign">Responsable du montage du dossier</label>
              <select
                id="dec-assign"
                className="select"
                value={assignedTo}
                onChange={(e) => setAssignedTo(e.target.value)}
              >
                <option value="">— À désigner plus tard —</option>
                {monteurs.map((u) => (
                  <option key={u.id} value={u.id}>{u.full_name || u.username}</option>
                ))}
              </select>
              <span className="muted">
                Cette personne devra joindre l'offre technique et l'offre financière avant l'échéance.
                Elle est prévenue par e-mail (sans responsable désigné, tous les comptes montage le sont).
              </span>
            </div>
          </>
        )}

        <div className="field">
          <label htmlFor="dec-comment">Commentaire {retenu ? '(facultatif)' : '— motif du rejet'}</label>
          <textarea
            id="dec-comment"
            className="textarea"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder={retenu ? 'Points d\'attention, pièces à préparer…' : 'Hors périmètre, délai trop court…'}
          />
        </div>

        <div className="modal-actions">
          <button type="button" className="btn btn-outline" onClick={onClose}>Annuler</button>
          <button type="submit" className={`btn${retenu ? '' : ' btn-danger'}`} disabled={busy}>
            {busy ? 'Enregistrement…' : retenu ? 'Confirmer et retenir' : "Confirmer l'écartement"}
          </button>
        </div>
      </form>
    </Modal>
  )
}
