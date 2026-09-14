import { useState } from 'react'
import * as api from '../api.js'
import PasswordField from './PasswordField.jsx'
import logo from '../logo.png'

export default function Login({ onLoggedIn }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const user = await api.login(username.trim(), password)
      onLoggedIn(user)
    } catch (e) {
      // Le navigateur renvoie « Failed to fetch » quand l'API ne répond pas :
      // le message brut n'aide pas l'utilisateur, on explique la cause.
      setError(
        /failed to fetch|networkerror|load failed/i.test(e.message)
          ? 'Le service est momentanément indisponible. Réessayez dans quelques instants.'
          : e.message,
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-screen">
      <div className="login-card">
        <img className="login-logo" src={logo} alt="ADOC" />
        <h1>Veille Appels d'Offres</h1>
        <p className="login-intro">Espace de travail — Sénégal &amp; sous-région UEMOA</p>

        {error && <div className="banner banner-error">{error}</div>}

        <form className="login-form" onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="login-username">Identifiant</label>
            <input
              id="login-username"
              className="input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoFocus
              required
            />
            <span className="muted">
              Un nom de compte, pas une adresse e-mail.
            </span>
          </div>

          <PasswordField
            id="login-password"
            label="Mot de passe"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />

          <button type="submit" className="btn btn-lg" disabled={busy || !username || !password}>
            {busy ? 'Connexion…' : 'Se connecter'}
          </button>
        </form>
      </div>
    </div>
  )
}
