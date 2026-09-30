import { useCallback, useEffect, useMemo, useState } from 'react'
import * as api from '../api.js'
import { formatDate } from '../utils.js'

/** Périodes de lancement prévues, en mois à partir d'aujourd'hui. */
const HORIZONS = [
  { value: '', label: "Toute l'année" },
  { value: '1', label: 'Lancement dans le mois' },
  { value: '3', label: 'Lancement dans 3 mois' },
  { value: '6', label: 'Lancement dans 6 mois' },
]

const MOIS = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
]

/** Dernier jour d'un mois (mois : 1 à 12), au format AAAA-MM-JJ. */
function finDeMois(annee, mois) {
  const dernier = new Date(Number(annee), Number(mois), 0).getDate()
  return `${annee}-${String(mois).padStart(2, '0')}-${String(dernier).padStart(2, '0')}`
}

const PAGE_SIZE = 50

/**
 * Plans de passation : ce que chaque ministère, collectivité ou agence prévoit
 * de lancer dans l'année, publié sur le portail officiel sénégalais. C'est le
 * seul endroit où l'on voit venir un marché avant la parution de l'avis.
 */
export default function PlansPage() {
  const [facets, setFacets] = useState(null)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [annee, setAnnee] = useState('')
  const [typeAutorite, setTypeAutorite] = useState('')
  const [autorite, setAutorite] = useState('')
  const [typeMarche, setTypeMarche] = useState('')
  const [horizon, setHorizon] = useState('')
  // Période explicite : de tel mois à tel mois, ou dates précises. Elle
  // l'emporte sur l'horizon et ne tient pas compte de la date du jour.
  const [moisDebut, setMoisDebut] = useState('')
  const [moisFin, setMoisFin] = useState('')
  const [dateDebut, setDateDebut] = useState('')
  const [dateFin, setDateFin] = useState('')
  const [q, setQ] = useState('')
  const [relevantOnly, setRelevantOnly] = useState(true)
  const [aVenir, setAVenir] = useState(true)
  const [page, setPage] = useState(1)

  useEffect(() => {
    api.fetchPlansFacets({ annee: annee || undefined, relevantOnly })
      .then((f) => {
        setFacets(f)
        if (!annee && f.annees?.length) setAnnee(String(f.annees[0]))
      })
      .catch((e) => setError(e.message))
  }, [annee, relevantOnly])

  const from = useMemo(() => {
    if (dateDebut) return dateDebut
    if (moisDebut && annee) return `${annee}-${String(moisDebut).padStart(2, '0')}-01`
    return undefined
  }, [dateDebut, moisDebut, annee])

  const to = useMemo(() => {
    if (dateFin) return dateFin
    if (moisFin && annee) return finDeMois(annee, moisFin)
    if (horizon) {
      const fin = new Date()
      fin.setMonth(fin.getMonth() + Number(horizon))
      return fin.toISOString().slice(0, 10)
    }
    return undefined
  }, [dateFin, moisFin, annee, horizon])

  // Une période choisie à la main se lit telle quelle : on n'y superpose pas
  // le filtre « à venir », sinon janvier à juin ne montrerait rien.
  const periodeChoisie = Boolean(dateDebut || dateFin || moisDebut || moisFin)
  const aVenirEffectif = periodeChoisie ? false : aVenir

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await api.fetchPlans({
        annee: annee || undefined,
        typeAutorite: typeAutorite || undefined,
        autorite: autorite || undefined,
        typeMarche: typeMarche || undefined,
        q: q || undefined,
        relevantOnly,
        aVenir: aVenirEffectif,
        from,
        to,
        page,
        pageSize: PAGE_SIZE,
      }))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [annee, typeAutorite, autorite, typeMarche, q, relevantOnly, aVenirEffectif, from, to, page])

  useEffect(() => { load() }, [load])

  // Tout changement de filtre ramène à la première page.
  useEffect(() => {
    setPage(1)
  }, [annee, typeAutorite, autorite, typeMarche, q, relevantOnly, aVenir, horizon, moisDebut, moisFin, dateDebut, dateFin])

  const total = data?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  // La liste des autorités suit le type choisi quand l'utilisateur en fixe un.
  const autorites = facets?.autorites || []

  return (
    <div className="stack">
      <section className="card card-pad">
        <div className="section-title">
          <div>
            <h2>Plans de passation</h2>
            <p>
              Ce que chaque ministère, collectivité ou agence prévoit de lancer dans l'année,
              d'après le portail officiel des marchés publics du Sénégal. Les avis ne sont pas
              encore publiés : c'est une longueur d'avance pour préparer les dossiers.
            </p>
          </div>
        </div>

        <div className="toolbar">
          <input
            type="text"
            className="input search-input"
            placeholder="Rechercher dans l'objet ou la référence…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />

          <select className="select" value={annee} onChange={(e) => setAnnee(e.target.value)}
                  aria-label="Année de gestion">
            {(facets?.annees || []).map((a) => (
              <option key={a} value={a}>Gestion {a}</option>
            ))}
          </select>

          <select className="select" value={typeAutorite} onChange={(e) => setTypeAutorite(e.target.value)}
                  aria-label="Type d'autorité">
            <option value="">Tous les types d'entité</option>
            {(facets?.types_autorite || []).map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>

          <select className="select" value={autorite} onChange={(e) => setAutorite(e.target.value)}
                  aria-label="Autorité contractante" title="Ministère, collectivité, agence…">
            <option value="">Toutes les entités ({autorites.length})</option>
            {autorites.map((a) => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>

          <select className="select" value={typeMarche} onChange={(e) => setTypeMarche(e.target.value)}
                  aria-label="Type de marché">
            <option value="">Tous les marchés</option>
            {(facets?.types_marche || []).map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>

          <select className="select" value={horizon} onChange={(e) => setHorizon(e.target.value)}
                  aria-label="Horizon de lancement" disabled={periodeChoisie}
                  title={periodeChoisie ? 'Une période précise est déjà choisie' : "À partir d'aujourd'hui"}>
            {HORIZONS.map((h) => (
              <option key={h.value} value={h.value}>{h.label}</option>
            ))}
          </select>

          <select className="select" value={moisDebut} onChange={(e) => setMoisDebut(e.target.value)}
                  aria-label="Mois de début" title="Lancements prévus à partir de ce mois">
            <option value="">Mois de début</option>
            {MOIS.map((m, i) => (
              <option key={m} value={i + 1}>De {m.toLowerCase()}</option>
            ))}
          </select>

          <select className="select" value={moisFin} onChange={(e) => setMoisFin(e.target.value)}
                  aria-label="Mois de fin" title="Lancements prévus jusqu'à la fin de ce mois">
            <option value="">Mois de fin</option>
            {MOIS.map((m, i) => (
              <option key={m} value={i + 1}>À {m.toLowerCase()}</option>
            ))}
          </select>

          <label className="row" style={{ gap: 6 }} title="Dates précises de lancement prévu">
            <span className="muted">Du</span>
            <input type="date" className="input" style={{ width: 'auto' }}
                   value={dateDebut} onChange={(e) => setDateDebut(e.target.value)} />
            <span className="muted">au</span>
            <input type="date" className="input" style={{ width: 'auto' }}
                   value={dateFin} onChange={(e) => setDateFin(e.target.value)} />
          </label>

          {periodeChoisie && (
            <button className="btn btn-sm btn-outline"
                    onClick={() => { setMoisDebut(''); setMoisFin(''); setDateDebut(''); setDateFin('') }}>
              Effacer la période
            </button>
          )}

          <label className="checkbox-label"
                 title="Ne garder que les marchés relevant de l'activité du cabinet (audit, conseil, études, formation…)">
            <input type="checkbox" checked={relevantOnly} onChange={(e) => setRelevantOnly(e.target.checked)} />
            Uniquement liés à notre activité
          </label>

          <label className="checkbox-label"
                 title={periodeChoisie
                   ? 'Sans effet : la période choisie est prise telle quelle'
                   : 'Masquer les lancements dont la date prévue est passée'}>
            <input type="checkbox" checked={aVenirEffectif} disabled={periodeChoisie}
                   onChange={(e) => setAVenir(e.target.checked)} />
            Lancements à venir seulement
          </label>
        </div>

        <div className="stat-grid" style={{ marginTop: 16 }}>
          <div className="stat">
            <div className="stat-value">{total}</div>
            <div className="stat-label">marchés prévus (filtre courant)</div>
          </div>
          <div className="stat">
            <div className="stat-value">{autorites.length}</div>
            <div className="stat-label">entités publiant un plan</div>
          </div>
          <div className="stat">
            <div className="stat-value">{facets?.total ?? '—'}</div>
            <div className="stat-label">lignes de plan collectées</div>
          </div>
        </div>
      </section>

      {error && <div className="banner banner-error">{error}</div>}

      <section className="card card-pad">
        {loading && <p className="empty-state">Chargement…</p>}
        {!loading && total === 0 && (
          <p className="empty-state">
            Aucun marché prévu ne correspond à ces filtres.
            {relevantOnly && " Décochez « Uniquement liés à notre activité » pour tout voir."}
          </p>
        )}

        {!loading && total > 0 && (
          <>
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>Lancement prévu</th>
                    <th>Attribution</th>
                    <th>Objet</th>
                    <th>Type de marché</th>
                    <th>Mode de passation</th>
                    <th>Entité</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((plan) => (
                    <tr key={plan.id}>
                      <td style={{ whiteSpace: 'nowrap' }}>
                        <strong>{formatDate(plan.date_lancement) || '—'}</strong>
                      </td>
                      <td style={{ whiteSpace: 'nowrap' }}>{formatDate(plan.date_attribution) || '—'}</td>
                      <td>
                        {plan.url ? (
                          <a href={plan.url} target="_blank" rel="noopener noreferrer">{plan.objet}</a>
                        ) : plan.objet}
                        {plan.reference && <div className="muted">Réf. {plan.reference}</div>}
                      </td>
                      <td>{plan.type_marche || '—'}</td>
                      <td>{plan.mode_passation || '—'}</td>
                      <td>
                        {plan.autorite}
                        {plan.type_autorite && <div className="muted">{plan.type_autorite}</div>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {pages > 1 && (
              <div className="row" style={{ marginTop: 14, justifyContent: 'center' }}>
                <button className="btn btn-outline btn-sm" disabled={page <= 1}
                        onClick={() => setPage((p) => p - 1)}>
                  Précédent
                </button>
                <span className="muted">Page {page} sur {pages}</span>
                <button className="btn btn-outline btn-sm" disabled={page >= pages}
                        onClick={() => setPage((p) => p + 1)}>
                  Suivant
                </button>
              </div>
            )}
          </>
        )}
      </section>
    </div>
  )
}
