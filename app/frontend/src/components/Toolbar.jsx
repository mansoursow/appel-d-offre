/** Périodes proposées : valeur = nombre de jours en arrière depuis aujourd'hui. */
export const PERIODS = [
  { value: '', label: 'Toutes les périodes' },
  { value: '7', label: 'Cette semaine (7 j)' },
  { value: '30', label: 'Ce mois-ci (30 j)' },
  { value: '90', label: 'Ce trimestre (3 mois)' },
  { value: '182', label: 'Ce semestre (6 mois)' },
  { value: '365', label: 'Cette année (12 mois)' },
]

export default function Toolbar({
  q, onQChange,
  category, onCategoryChange,
  sources = [], sourceId, onSourceIdChange,
  period, onPeriodChange,
  sort, onSortChange,
  hideExpired, onHideExpiredChange,
  hideDecided, onHideDecidedChange,
  relevantOnly, onRelevantOnlyChange,
  onRefresh, refreshing, lastRefreshSummary,
}) {
  return (
    <div className="toolbar">
      <input
        type="text"
        placeholder="Rechercher un mot-clé (titre, entité)…"
        value={q}
        onChange={(e) => onQChange(e.target.value)}
        className="input search-input"
      />

      <select value={category} onChange={(e) => onCategoryChange(e.target.value)} className="select">
        <option value="">Tous les types</option>
        <option value="appel_offre">Appels d'offres</option>
        <option value="ami">Avis à manifestation d'intérêt</option>
        <option value="autre">Autres avis</option>
      </select>

      <select
        value={sourceId}
        onChange={(e) => onSourceIdChange(e.target.value)}
        className="select"
        title="N'afficher que les avis d'un site précis"
        aria-label="Filtrer par site"
      >
        <option value="">Tous les sites</option>
        {sources.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}{s.tender_count ? ` (${s.tender_count})` : ''}
          </option>
        ))}
      </select>

      <select
        value={period}
        onChange={(e) => onPeriodChange(e.target.value)}
        className="select"
        title="Période de publication des avis"
        aria-label="Filtrer par période"
      >
        {PERIODS.map((p) => (
          <option key={p.value} value={p.value}>{p.label}</option>
        ))}
      </select>

      <select
        value={sort}
        onChange={(e) => onSortChange(e.target.value)}
        className="select"
        title="Ordre d'affichage des avis"
        aria-label="Trier les avis"
      >
        <option value="deadline">Échéance la plus proche</option>
        <option value="deadline_desc">Échéance la plus lointaine</option>
        <option value="published">Publication la plus récente</option>
      </select>

      {onRelevantOnlyChange && (
        <label
          className="checkbox-label"
          title="N'affiche que les avis liés à l'activité du cabinet (audit, comptabilité, conseil, études, évaluation, formation, assistance technique…). Décochez pour voir tous les avis collectés."
        >
          <input
            type="checkbox"
            checked={relevantOnly}
            onChange={(e) => onRelevantOnlyChange(e.target.checked)}
          />
          Uniquement les avis liés à notre activité
        </label>
      )}

      <label className="checkbox-label">
        <input
          type="checkbox"
          checked={hideExpired}
          onChange={(e) => onHideExpiredChange(e.target.checked)}
        />
        Masquer les offres expirées
      </label>

      {onHideDecidedChange && (
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={hideDecided}
            onChange={(e) => onHideDecidedChange(e.target.checked)}
          />
          Masquer les avis déjà traités
        </label>
      )}

      <button onClick={onRefresh} disabled={refreshing} className="btn">
        {refreshing ? 'Collecte en cours…' : 'Rafraîchir'}
      </button>

      {lastRefreshSummary && (
        <span className="refresh-summary" title={lastRefreshSummary.detail}>
          {lastRefreshSummary.text}
        </span>
      )}
    </div>
  )
}
