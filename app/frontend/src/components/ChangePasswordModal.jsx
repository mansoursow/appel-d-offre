import { useState } from 'react'
import Modal from './Modal.jsx'
import PasswordField from './PasswordField.jsx'
import * as api from '../api.js'

export default function ChangePasswordModal({ forced, onDone, onClose }) {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    if (next !== confirm) {
      setError('Les deux saisies du nouveau mot de passe ne correspondent pas.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const user = await api.changePassword(current, next)
      onDone(user)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      title="Changer le mot de passe"
      subtitle={
        forced
          ? "Le mot de passe initial doit être remplacé avant d'utiliser l'application."
          : 'Choisissez un nouveau mot de passe (6 caractères minimum).'
      }
      onClose={onClose}
      closable={!forced}
    >
      {error && <div className="banner banner-error">{error}</div>}

      <form className="stack" onSubmit={handleSubmit}>
        <PasswordField
          id="pwd-current"
          label="Mot de passe actuel"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          autoComplete="current-password"
        />
        <PasswordField
          id="pwd-new"
          label="Nouveau mot de passe"
          value={next}
          onChange={(e) => setNext(e.target.value)}
          autoComplete="new-password"
          minLength={6}
        />
        <PasswordField
          id="pwd-confirm"
          label="Confirmer le nouveau mot de passe"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          autoComplete="new-password"
          minLength={6}
        />

        <div className="modal-actions">
          {!forced && (
            <button type="button" className="btn btn-outline" onClick={onClose}>Annuler</button>
          )}
          <button type="submit" className="btn" disabled={busy}>
            {busy ? 'Enregistrement…' : 'Enregistrer'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
