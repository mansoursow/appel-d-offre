export default function Toolbar({
  q, onQChange,
  category, onCategoryChange,
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
