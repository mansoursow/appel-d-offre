export const CATEGORY_LABELS = {
  appel_offre: "Appel d'offres",
  ami: "Avis à manifestation d'intérêt",
  autre: 'Autre avis',
}

export const DOSSIER_STATUS_LABELS = {
  complet: 'Dossier complet',
  en_cours: 'En préparation',
  urgent: 'Échéance proche',
  en_retard: 'En retard',
  rejete: 'Non retenu',
}

export const JOURNAL_STATUS_LABELS = {
  photos: 'Avis photographiés',
  neant: 'NÉANT',
  ras: 'RAS',
}

/** Profils autorisés à retenir ou écarter un avis (et à confier un dossier). */
export const SELECTION_ROLES = ['admin', 'selectionneur', 'superviseur']

/** « Nom complet (identifiant) » : le nom seul ne dit pas quel compte on choisit. */
export function userLabel(user) {
  if (!user) return ''
  return user.full_name && user.full_name !== user.username
    ? `${user.full_name} (${user.username})`
    : user.username
}

/** Affiche une date ISO en JJ/MM/AAAA ; laisse le texte intact sinon. */
export function formatDate(value) {
  if (!value) return null
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(value)
  return m ? `${m[3]}/${m[2]}/${m[1]}` : value
}

export function formatDateTime(value) {
  if (!value) return null
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString('fr-FR', {
    day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

export function todayIso() {
  const now = new Date()
  const offset = now.getTimezoneOffset() * 60000
  return new Date(now.getTime() - offset).toISOString().slice(0, 10)
}

export function isExpired(deadlineIso) {
  return Boolean(deadlineIso) && deadlineIso < todayIso()
}

/** Nombre de jours entiers entre aujourd'hui et une échéance ISO (YYYY-MM-DD).
 *  Négatif si l'échéance est passée, 0 si c'est aujourd'hui, null si inconnue. */
export function daysUntil(deadlineIso) {
  if (!deadlineIso) return null
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(deadlineIso)
  if (!m) return null
  const end = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
  const now = new Date()
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  return Math.round((end - start) / 86400000)
}

/** Libellé court de compte à rebours pour une échéance. */
export function countdownLabel(deadlineIso) {
  const d = daysUntil(deadlineIso)
  if (d === null) return 'Échéance non précisée'
  if (d < 0) return `Expiré depuis ${Math.abs(d)} j`
  if (d === 0) return "Dernier jour !"
  if (d === 1) return 'J‑1 · demain'
  return `J‑${d} · ${d} jours restants`
}

/** Niveau d'urgence (pour la couleur) : expired | urgent | soon | ok | unknown. */
export function countdownLevel(deadlineIso) {
  const d = daysUntil(deadlineIso)
  if (d === null) return 'unknown'
  if (d < 0) return 'expired'
  if (d <= 2) return 'urgent'
  if (d <= 7) return 'soon'
  return 'ok'
}

export function formatSize(bytes) {
  if (!bytes && bytes !== 0) return ''
  if (bytes < 1024) return `${bytes} o`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} Ko`
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`
}

/** Formule lisible pour le délai restant avant une échéance. */
export function deadlineHint(daysLeft) {
  if (daysLeft === null || daysLeft === undefined) return 'Échéance inconnue'
  if (daysLeft < 0) return `Échéance dépassée depuis ${Math.abs(daysLeft)} j`
  if (daysLeft === 0) return "Échéance aujourd'hui"
  if (daysLeft === 1) return 'Échéance demain'
  return `Échéance dans ${daysLeft} jours`
}

export function isImage(contentType, name = '') {
  if (contentType && contentType.startsWith('image/')) return true
  return /\.(jpe?g|png|webp|gif)$/i.test(name)
}

/** Montant en francs CFA, avec des espaces comme séparateurs de milliers. */
export function formatFcfa(amount) {
  if (amount === null || amount === undefined) return null
  return `${Number(amount).toLocaleString('fr-FR').replace(/\u202f|\u00a0/g, ' ')} F`
}

/** Écart en pourcentage par rapport à l'offre ADOC, signe compris. */
export function formatEcart(pct) {
  if (pct === null || pct === undefined) return null
  const rounded = Math.round(pct * 10) / 10
  if (rounded === 0) return 'identique'
  return `${rounded > 0 ? '+' : ''}${rounded.toLocaleString('fr-FR')} %`
}
