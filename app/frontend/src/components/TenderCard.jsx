import { CATEGORY_LABELS, formatDate, isExpired, countdownLabel, countdownLevel } from '../utils.js'

export default function TenderCard({ tender, selection, canSelect, onDecide }) {
  const categoryLabel = CATEGORY_LABELS[tender.category] || tender.category
  const published = formatDate(tender.published_date)
  const deadline = formatDate(tender.deadline_date || tender.deadline_iso)
  const expired = isExpired(tender.deadline_iso)
  const cdLevel = countdownLevel(tender.deadline_iso)
  const cdLabel = countdownLabel(tender.deadline_iso)

  const decisionClass = selection ? ` tender-card-${selection.decision}` : ''

  return (
    <article className={`tender-card${expired ? ' tender-card-expired' : ''}${decisionClass}`}>
      <div className="tender-card-header">
        <span className={`badge badge-${tender.category || 'autre'}`}>{categoryLabel}</span>
        <span className="badge badge-source">{tender.source_name}</span>
        {tender.deadline_iso && (
          <span className={`countdown countdown-${cdLevel}`} title={`Échéance : ${deadline}`}>
            {cdLabel}
          </span>
        )}
        {expired && !tender.deadline_iso && <span className="badge badge-expired">Expiré</span>}
        {selection && (
          <span className={`badge badge-${selection.decision}`}>
            {selection.decision === 'retenu' ? 'Retenu' : 'Non retenu'}
          </span>
        )}
      </div>

      <h3 className="tender-title">
        <a href={tender.url} target="_blank" rel="noopener noreferrer">{tender.title}</a>
      </h3>

      {tender.entity && <p className="tender-entity">{tender.entity}</p>}
      {tender.description && <p className="tender-description">{tender.description}</p>}

      <div className="tender-footer">
        {tender.country && <span>{tender.country}</span>}
        {published && <span>Publié : {published}</span>}
        {deadline && <span>Échéance : {deadline}</span>}
      </div>

      {canSelect && !selection && (
        <div className="tender-actions">
          <button className="btn btn-sm" onClick={() => onDecide(tender, 'retenu')}>
            Retenir cet avis
          </button>
          <button className="btn btn-sm btn-outline" onClick={() => onDecide(tender, 'rejete')}>
            Ne pas soumissionner
          </button>
        </div>
      )}

      {selection && (
        <div className="tender-actions">
          <span className="muted">
            {selection.decision === 'retenu' ? 'Retenu' : 'Écarté'} par {selection.selected_by_name}
            {selection.assigned_to_name ? ` · montage : ${selection.assigned_to_name}` : ''}
          </span>
        </div>
      )}
    </article>
  )
}
