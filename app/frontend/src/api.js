// Adresse de l'API.
// - En production, le backend sert lui-meme cette interface : les appels
//   partent donc de l'origine courante (chaine vide = meme domaine).
// - En developpement, Vite tourne sur le port 5173 et l'API sur le 8000.
// - VITE_API_URL force une adresse precise (frontend heberge separement).
const API_URL =
  import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '')
const TOKEN_KEY = 'veille-ao-token'

// --------------------------------------------------------------------------
// Jeton de session
// --------------------------------------------------------------------------
export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* navigation privée : la session ne survivra pas au rechargement */
  }
}

/** URL d'un fichier protégé (photo, offre) utilisable dans <img> ou <a>.
 *  Le jeton passe en paramètre : une balise <img> ne peut pas porter d'en-tête. */
export function fileUrl(path) {
  if (!path) return null
  const token = getToken()
  return `${API_URL}${path}${token ? `?token=${encodeURIComponent(token)}` : ''}`
}

// --------------------------------------------------------------------------
// Appels HTTP
// --------------------------------------------------------------------------
export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

async function request(path, { method = 'GET', body, formData } = {}) {
  const headers = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    body: formData || (body !== undefined ? JSON.stringify(body) : undefined),
  })

  if (!res.ok) {
    let detail = ''
    try {
      const payload = await res.json()
      detail = typeof payload.detail === 'string' ? payload.detail : JSON.stringify(payload.detail)
    } catch {
      detail = await res.text().catch(() => '')
    }
    throw new ApiError(detail || `Erreur ${res.status}`, res.status)
  }

  if (res.status === 204) return null
  return res.json()
}

// --------------------------------------------------------------------------
// Authentification
// --------------------------------------------------------------------------
export async function login(username, password) {
  const data = await request('/api/auth/login', { method: 'POST', body: { username, password } })
  setToken(data.token)
  return data.user
}

export function fetchMe() {
  return request('/api/auth/me')
}

export function changePassword(currentPassword, newPassword) {
  return request('/api/auth/password', {
    method: 'POST',
    body: { current_password: currentPassword, new_password: newPassword },
  })
}

export async function logout() {
  try {
    await request('/api/auth/logout', { method: 'POST' })
  } catch {
    /* la session était peut-être déjà expirée côté serveur */
  }
  setToken(null)
}

// --------------------------------------------------------------------------
// Veille automatique
// --------------------------------------------------------------------------
export function fetchTenders({ zone, category, sourceId, q, onlyActive = true, relevantOnly = true, sort = 'deadline', page = 1, pageSize = 50 } = {}) {
  const params = new URLSearchParams()
  if (zone) params.set('zone', zone)
  if (category) params.set('category', category)
  if (sourceId) params.set('source_id', sourceId)
  if (q) params.set('q', q)
  params.set('only_active', onlyActive ? 'true' : 'false')
  params.set('relevant_only', relevantOnly ? 'true' : 'false')
  params.set('sort', sort)
  params.set('page', page)
  params.set('page_size', pageSize)
  return request(`/api/tenders?${params.toString()}`)
}

export function fetchSources() {
  return request('/api/sources')
}

export function fetchStats() {
  return request('/api/stats')
}

export function refresh(sourceId) {
  const params = sourceId ? `?source_id=${encodeURIComponent(sourceId)}` : ''
  return request(`/api/refresh${params}`, { method: 'POST' })
}

// --------------------------------------------------------------------------
// Journaux papier
// --------------------------------------------------------------------------
export function fetchJournalToday() {
  return request('/api/journal/today')
}

export function fetchJournalEntries({ from, to, userId, limit = 60 } = {}) {
  const params = new URLSearchParams()
  if (from) params.set('from', from)
  if (to) params.set('to', to)
  if (userId) params.set('user_id', userId)
  params.set('limit', limit)
  return request(`/api/journal/entries?${params.toString()}`)
}

export function uploadJournalPhotos({ files, entryDate, newspaper, caption }) {
  const formData = new FormData()
  for (const file of files) formData.append('files', file)
  if (entryDate) formData.append('entry_date', entryDate)
  if (newspaper) formData.append('newspaper', newspaper)
  if (caption) formData.append('caption', caption)
  return request('/api/journal/photos', { method: 'POST', formData })
}

export function declareJournalStatus({ status, entryDate, note }) {
  return request('/api/journal/status', {
    method: 'POST',
    body: { status, entry_date: entryDate, note },
  })
}

export function deleteJournalPhoto(photoId) {
  return request(`/api/journal/photos/${photoId}`, { method: 'DELETE' })
}

export function fetchJournalCompliance({ days = 30, userId } = {}) {
  const params = new URLSearchParams({ days: String(days) })
  if (userId) params.set('user_id', userId)
  return request(`/api/journal/compliance?${params.toString()}`)
}

// --------------------------------------------------------------------------
// Sélection des avis et dossiers de soumission
// --------------------------------------------------------------------------
export function fetchSelections({ decision, status, assignedToMe } = {}) {
  const params = new URLSearchParams()
  if (decision) params.set('decision', decision)
  if (status) params.set('status', status)
  if (assignedToMe) params.set('assigned_to_me', 'true')
  return request(`/api/selections?${params.toString()}`)
}

/** Comptes « montage » auxquels le responsable sélection peut confier un dossier. */
export function fetchAssignableUsers() {
  return request('/api/users/assignable')
}

export function createSelection(payload) {
  return request('/api/selections', { method: 'POST', body: payload })
}

export function updateSelection(selectionId, payload) {
  return request(`/api/selections/${selectionId}`, { method: 'PATCH', body: payload })
}

export function uploadSubmissionDocument(selectionId, docType, file) {
  const formData = new FormData()
  formData.append('doc_type', docType)
  formData.append('file', file)
  return request(`/api/selections/${selectionId}/documents`, { method: 'POST', formData })
}

export function deleteSubmissionDocument(documentId) {
  return request(`/api/documents/${documentId}`, { method: 'DELETE' })
}

// --------------------------------------------------------------------------
// Administration
// --------------------------------------------------------------------------
export function fetchAdminDashboard(days = 30) {
  return request(`/api/admin/dashboard?days=${days}`)
}

export function fetchAdminAlerts(days = 30) {
  return request(`/api/admin/alerts?days=${days}`)
}

export function fetchAdminCompliance({ days = 30, userId } = {}) {
  const params = new URLSearchParams({ days: String(days) })
  if (userId) params.set('user_id', userId)
  return request(`/api/admin/journal-compliance?${params.toString()}`)
}

export function fetchActivityLogs({ userId, role, action, limit = 200 } = {}) {
  const params = new URLSearchParams({ limit: String(limit) })
  if (userId) params.set('user_id', userId)
  if (role) params.set('role', role)
  if (action) params.set('action', action)
  return request(`/api/admin/logs?${params.toString()}`)
}

export function fetchUsers() {
  return request('/api/admin/users')
}

export function createUser(payload) {
  return request('/api/admin/users', { method: 'POST', body: payload })
}

export function updateUser(userId, payload) {
  return request(`/api/admin/users/${userId}`, { method: 'PATCH', body: payload })
}
