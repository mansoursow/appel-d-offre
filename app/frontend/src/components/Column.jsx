import TenderCard from './TenderCard.jsx'

export default function Column({ title, subtitle, tenders, loading, selectionsByTender, canSelect, onDecide }) {
  return (
    <section className="column">
      <header className="column-header">
        <h2>{title}</h2>
        <span className="column-count">{tenders.length}</span>
      </header>
      {subtitle && <p className="muted">{subtitle}</p>}

      {loading && <p className="empty-state">Chargement…</p>}

      {!loading && tenders.length === 0 && (
        <p className="empty-state">
          Aucun avis pour le moment. Lancez la collecte avec le bouton « Rafraîchir ».
        </p>
      )}

      <div className="column-list">
        {tenders.map((tender) => (
          <TenderCard
            key={tender.id}
            tender={tender}
            selection={selectionsByTender?.get(tender.id)}
            canSelect={canSelect}
            onDecide={onDecide}
          />
        ))}
      </div>
    </section>
  )
}
