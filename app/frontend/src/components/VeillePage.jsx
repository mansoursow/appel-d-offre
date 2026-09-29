import { useCallback, useEffect, useMemo, useState } from 'react'
import * as api from '../api.js'
import Column from './Column.jsx'
import Toolbar from './Toolbar.jsx'
import DecisionModal from './DecisionModal.jsx'

/** Veille automatique : les avis collectés sur les ~24 sources publiques. */
export default function VeillePage({ user, onSelectionsChanged }) {
  const [senegalTenders, setSenegalTenders] = useState([])
  const [uemoaTenders, setUemoaTenders] = useState([])
  // Quand un site précis est choisi, on n'affiche qu'une liste (toutes zones
  // confondues) : sinon les avis internationaux d'un bailleur resteraient
  // invisibles, les colonnes ne couvrant que le Sénégal et l'UEMOA.
  const [sourceTenders, setSourceTenders] = useState([])
  const [sources, setSources] = useState([])
  const [selections, setSelections] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)
  const [lastRefreshSummary, setLastRefreshSummary] = useState(null)
  const [pending, setPending] = useState(null)

  const [q, setQ] = useState('')
  const [category, setCategory] = useState('')
  const [sort, setSort] = useState('deadline')
  const [hideExpired, setHideExpired] = useState(true)
  // Un avis deja traite (retenu ou ecarte) disparait des recherches par
  // defaut : il bascule dans l'onglet Dossiers. On peut le reafficher.
  const [hideDecided, setHideDecided] = useState(true)
  const [relevantOnly, setRelevantOnly] = useState(true)
  const [sourceId, setSourceId] = useState('')
  const [period, setPeriod] = useState('')

  const canSelect = ['selectionneur', 'superviseur', 'admin'].includes(user.role)

  /** Début de la période choisie, au format AAAA-MM-JJ (vide = pas de filtre). */
  const publishedFrom = useMemo(() => {
    if (!period) return undefined
    const debut = new Date()
    debut.setDate(debut.getDate() - Number(period))
    return debut.toISOString().slice(0, 10)
  }, [period])

  useEffect(() => {
    api.fetchSources()
      .then((list) => setSources(
        list.filter((s) => s.tender_count > 0).sort((a, b) => a.name.localeCompare(b.name)),
      ))
      .catch(() => setSources([]))
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = {
        category: category || undefined, q: q || undefined, onlyActive: hideExpired,
        relevantOnly, publishedFrom, sort, pageSize: 100,
      }
      if (sourceId) {
        const [avis, sels] = await Promise.all([
          api.fetchTenders({ ...params, sourceId, pageSize: 200 }),
          api.fetchSelections(),
        ])
        setSourceTenders(avis.items)
        setSelections(sels)
      } else {
        const [senegal, uemoa, sels] = await Promise.all([
          api.fetchTenders({ ...params, zone: 'senegal' }),
          api.fetchTenders({ ...params, zone: 'uemoa' }),
          api.fetchSelections(),
        ])
        setSenegalTenders(senegal.items)
        setUemoaTenders(uemoa.items)
        setSelections(sels)
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [q, category, hideExpired, relevantOnly, sort, sourceId, publishedFrom])

  useEffect(() => { load() }, [load])

  const selectionsByTender = useMemo(() => {
    const map = new Map()
    for (const s of selections) {
      if (s.tender_id) map.set(s.tender_id, s)
    }
    return map
  }, [selections])

  const visible = useCallback(
    (list) => (hideDecided ? list.filter((t) => !selectionsByTender.has(t.id)) : list),
    [hideDecided, selectionsByTender],
  )

  async function handleRefresh() {
    setRefreshing(true)
    setError(null)
    try {
      const summary = await api.refresh()
      const totalNew = summary.results.reduce((acc, r) => acc + (r.new_items || 0), 0)
      const errors = summary.results.filter((r) => r.status === 'error')
      setLastRefreshSummary({
        text: `${totalNew} nouvel(le)s annonce(s)${errors.length ? ` · ${errors.length} source(s) en erreur` : ''}`,
        detail: summary.results
          .map((r) => `${r.source_name}: ${r.status} (${r.new_items}/${r.total_found})`)
          .join('\n'),
      })
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setRefreshing(false)
    }
  }

  function handleDecide(tender, decision) {
    setPending({
      decision,
      avis: {
        kind: 'tender',
        id: tender.id,
        title: tender.title,
        entity: tender.entity,
        category: tender.category,
        deadline_iso: tender.deadline_iso,
        url: tender.url,
      },
    })
  }

  function handleSaved(saved) {
    setSelections((prev) => [saved, ...prev])
    setPending(null)
    onSelectionsChanged?.()
  }

  return (
    <>
      <Toolbar
        q={q} onQChange={setQ}
        category={category} onCategoryChange={setCategory}
        sources={sources} sourceId={sourceId} onSourceIdChange={setSourceId}
        period={period} onPeriodChange={setPeriod}
        sort={sort} onSortChange={setSort}
        hideExpired={hideExpired} onHideExpiredChange={setHideExpired}
        hideDecided={hideDecided} onHideDecidedChange={setHideDecided}
        relevantOnly={relevantOnly} onRelevantOnlyChange={setRelevantOnly}
        onRefresh={handleRefresh} refreshing={refreshing}
        lastRefreshSummary={lastRefreshSummary}
      />

      {error && <div className="banner banner-error">{error}</div>}

      {canSelect && (
        <div className="banner banner-info">
          Vous décidez des avis sur lesquels le cabinet soumissionne. Chaque décision est
          horodatée et visible par l'administrateur.
        </div>
      )}

      <main className={`columns${sourceId ? ' columns-single' : ''}`}>
        {sourceId ? (
          <Column
            title={sources.find((s) => s.id === sourceId)?.name || 'Site choisi'}
            tenders={visible(sourceTenders)}
            loading={loading}
            selectionsByTender={selectionsByTender}
            canSelect={canSelect}
            onDecide={handleDecide}
          />
        ) : (
          <>
            <Column
              title="Sénégal"
              tenders={visible(senegalTenders)}
              loading={loading}
              selectionsByTender={selectionsByTender}
              canSelect={canSelect}
              onDecide={handleDecide}
            />
            <Column
              title="Sous-région (UEMOA)"
              tenders={visible(uemoaTenders)}
              loading={loading}
              selectionsByTender={selectionsByTender}
              canSelect={canSelect}
              onDecide={handleDecide}
            />
          </>
        )}
      </main>

      {pending && (
        <DecisionModal
          avis={pending.avis}
          decision={pending.decision}
          onClose={() => setPending(null)}
          onSaved={handleSaved}
        />
      )}
    </>
  )
}
