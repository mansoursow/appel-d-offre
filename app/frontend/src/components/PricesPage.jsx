import { useCallback, useEffect, useState } from 'react'
import * as api from '../api.js'
import { formatDate, formatEcart, formatFcfa } from '../utils.js'

/**
 * Historique des prix : marché par marché, ce que le cabinet a proposé et ce
 * qu'ont proposé les concurrents. Sert à chiffrer une nouvelle offre en
 * sachant ce que les autres pratiquent habituellement sur ce type de marché.
 *
 * Les données viennent du classeur « Tableau des MI et PTF » : seules les
 * lignes dont les prix sont renseignés y figurent.
 */
export default function PricesPage({ user }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [message, setMessage] = useState(null)
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState(() => new Set())

  const [search, setSearch] = useState('')
  const [annee, setAnnee] = useState('')
  const [methode, setMethode] = useState('')
  const [nature, setNature] = useState('')
  const [issue, setIssue] = useState('')

  const isAdmin = user.role === 'admin'

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await api.fetchPriceHistory({ search, annee, methode, nature, issue }))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [search, annee, methode, nature, issue])

  // La recherche part après une courte pause : on ne rappelle pas l'API
  // à chaque lettre tapée.
  useEffect(() => {
    const timer = setTimeout(load, search ? 300 : 0)
    return () => clearTimeout(timer)
  }, [load, search])

  function toggle(id) {
    setOpen((previous) => {
      const next = new Set(previous)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  async function handleImport(event) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    if (!window.confirm(
      `Remplacer tout l'historique des prix par le contenu de « ${file.name} » ?`,
    )) return
    setBusy(true)
    setError(null)
    setMessage(null)
    try {
      const fresh = await api.importPriceWorkbook(file)
      setData(fresh)
      setMessage(`${fresh.total_marches} marché(s) chiffré(s) importé(s).`)
      setSearch(''); setAnnee(''); setMethode(''); setNature(''); setIssue('')
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const marches = data?.marches || []
  const concurrents = data?.concurrents || []
  const reperes = data?.reperes || []
  const filtre = Boolean(search || annee || methode || nature || issue)
  // Une seule nature retenue : on peut donner un repère de prix chiffré.
  const repereCible = nature ? reperes.find((r) => r.code === nature) : null

  return (
    <div className="stack">
      {error && <div className="banner banner-error">{error}</div>}
      {message && <div className="banner banner-success">{message}</div>}

      <section className="card card-pad">
        <div className="section-title">
          <div>
            <h2>Historique des prix</h2>
            <p>
              Ce que nous avons proposé et ce qu'ont proposé les concurrents sur les marchés
              passés — pour chiffrer les prochaines offres du même type.
            </p>
          </div>
        </div>

        <div className="toolbar">
          <input
            className="input search-input"
            placeholder="Objet, structure ou nom d'un concurrent (Mazars, FOCUS…)"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select className="select" value={nature} onChange={(e) => setNature(e.target.value)}>
            <option value="">Toutes les natures de marché</option>
            {(data?.natures || []).map((n) => (
              <option key={n.code} value={n.code}>{n.label} ({n.marches})</option>
            ))}
          </select>
          <select className="select" value={annee} onChange={(e) => setAnnee(e.target.value)}>
            <option value="">Toutes les années</option>
            {(data?.annees || []).map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
          <select className="select" value={methode} onChange={(e) => setMethode(e.target.value)}>
            <option value="">Toutes les méthodes</option>
            {(data?.methodes || []).map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
          <select className="select" value={issue} onChange={(e) => setIssue(e.target.value)}>
            <option value="">Gagnés et perdus</option>
            <option value="gagnes">Remportés par ADOC</option>
            <option value="perdus">Perdus</option>
          </select>
        </div>

        <div className="stat-grid" style={{ marginTop: 16 }}>
          <div className="stat">
            <div className="stat-value">{marches.length}</div>
            <div className="stat-label">
              marchés chiffrés{filtre && data ? ` sur ${data.total_marches}` : ''}
            </div>
          </div>
          <div className="stat stat-ok">
            <div className="stat-value">{data?.marches_gagnes ?? 0}</div>
            <div className="stat-label">remportés par ADOC</div>
          </div>
          <div className="stat">
            <div className="stat-value">{concurrents.length}</div>
            <div className="stat-label">concurrents rencontrés</div>
          </div>
        </div>
      </section>

      {reperes.length > 0 && (
        <section className="card card-pad">
          <div className="section-title">
            <div>
              <h2>Repères de prix par nature de marché</h2>
              <p>
                Les prix ne se comparent qu'entre marchés de même nature : un commissariat aux
                comptes ne se chiffre pas comme un plan stratégique. Pour être le moins-disant,
                il faut passer sous la colonne « le moins-disant a proposé ».
              </p>
            </div>
          </div>

          {repereCible && (
            <div className="banner banner-info">
              {repereCible.moins_disant_median ? (
                <>
                  <strong>{repereCible.label}</strong> — sur{' '}
                  {repereCible.marches_compares > 1
                    ? `les ${repereCible.marches_compares} marchés`
                    : 'le seul marché'}{' '}
                  où des prix de concurrents sont connus, l'offre la moins chère s'est située
                  en médiane à <strong>{formatFcfa(repereCible.moins_disant_median)}</strong>
                  {repereCible.concurrent_min && (
                    <>, le concurrent le plus bas étant descendu à {formatFcfa(repereCible.concurrent_min)}</>
                  )}.
                  {' '}Nous avons proposé {formatFcfa(repereCible.adoc_median)} en médiane et nous étions
                  moins-disants {repereCible.fois_moins_disant} fois sur {repereCible.marches_compares}.
                </>
              ) : (
                <>
                  <strong>{repereCible.label}</strong> — aucun prix de concurrent connu sur cette nature :
                  impossible d'en tirer un repère. Nous avons proposé {formatFcfa(repereCible.adoc_median)} en médiane.
                </>
              )}
            </div>
          )}

          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Nature du marché</th>
                  <th className="num">Marchés</th>
                  <th className="num">Remportés</th>
                  <th className="num">Notre prix médian</th>
                  <th className="num">Le moins-disant a proposé</th>
                  <th className="num">Concurrent le plus bas</th>
                  <th className="num">Fois moins-disants</th>
                </tr>
              </thead>
              <tbody>
                {reperes.map((r) => (
                  <tr
                    key={r.code}
                    className={r.code === nature ? 'ligne-adoc' : ''}
                    onClick={() => setNature(r.code === nature ? '' : r.code)}
                    style={{ cursor: 'pointer' }}
                  >
                    <td><strong>{r.label}</strong></td>
                    <td className="num">{r.marches}</td>
                    <td className="num">{r.victoires || '—'}</td>
                    <td className="num">{formatFcfa(r.adoc_median) || '—'}</td>
                    <td className="num">
                      {r.moins_disant_median
                        ? <strong>{formatFcfa(r.moins_disant_median)}</strong>
                        : <span className="muted">aucun concurrent chiffré</span>}
                    </td>
                    <td className="num">{formatFcfa(r.concurrent_min) || '—'}</td>
                    <td className="num">
                      {r.marches_compares
                        ? `${r.fois_moins_disant} / ${r.marches_compares}`
                        : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {concurrents.length > 0 && (
        <section className="card card-pad">
          <div className="section-title">
            <div>
              <h2>Ce que proposent les concurrents</h2>
              <p>
                Prix médian de chaque cabinet et écart habituel avec nos propres offres.
                Un écart négatif signifie qu'il chiffre moins cher que nous.
                {nature
                  ? ` Limité aux marchés « ${data?.natures?.find((n) => n.code === nature)?.label || ''} ».`
                  : ' Choisissez une nature de marché ci-dessus pour ne comparer que des prix comparables.'}
              </p>
            </div>
          </div>

          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Concurrent</th>
                  <th className="num">Rencontres</th>
                  <th className="num">Marchés gagnés</th>
                  <th className="num">Prix médian</th>
                  <th className="num">Fourchette</th>
                  <th className="num">Écart moyen / ADOC</th>
                </tr>
              </thead>
              <tbody>
                {concurrents.map((c) => (
                  <tr key={c.nom}>
                    <td><strong>{c.nom}</strong></td>
                    <td className="num">{c.marches}</td>
                    <td className="num">{c.victoires || '—'}</td>
                    <td className="num">{formatFcfa(c.montant_median)}</td>
                    <td className="num muted">
                      {c.montant_min === c.montant_max
                        ? '—'
                        : `${formatFcfa(c.montant_min)} → ${formatFcfa(c.montant_max)}`}
                    </td>
                    <td className="num">
                      {c.ecart_moyen_pct === null || c.ecart_moyen_pct === undefined ? (
                        <span className="muted">non comparable</span>
                      ) : (
                        <span className={c.ecart_moyen_pct < 0 ? 'ecart-bas' : 'ecart-haut'}>
                          {formatEcart(c.ecart_moyen_pct)}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="card card-pad">
        <div className="section-title">
          <div>
            <h2>Marché par marché</h2>
            <p>Cliquez sur un marché pour voir le détail des offres, de la moins chère à la plus chère.</p>
          </div>
        </div>

        {loading && <p className="empty-state">Chargement…</p>}
        {!loading && marches.length === 0 && (
          <p className="empty-state">
            {filtre
              ? 'Aucun marché ne correspond à cette recherche.'
              : "Aucun marché chiffré pour l'instant."}
          </p>
        )}

        <div className="stack">
          {marches.map((m) => {
            const deplie = open.has(m.id)
            return (
              <div key={m.id} className={`marche${m.adoc_gagnant ? ' marche-gagne' : ''}`}>
                <button className="marche-head" onClick={() => toggle(m.id)}>
                  <div className="marche-title">
                    <strong>{m.objet}</strong>
                    <span className="muted">
                      <span className="badge badge-nature">{m.nature_label}</span>
                      {[m.structure, formatDate(m.date) || m.annee, m.methode]
                        .filter(Boolean).join(' · ')}
                    </span>
                  </div>
                  <div className="marche-figures">
                    <span className="marche-prix">
                      <span className="marche-prix-label">Notre prix</span>
                      <strong>{formatFcfa(m.montant_adoc) || '—'}</strong>
                    </span>
                    <span className={`badge ${m.adoc_gagnant ? 'badge-retenu' : 'badge-rejete'}`}>
                      {m.adoc_gagnant ? 'Remporté' : `Attribué à ${m.attributaire || '?'}`}
                    </span>
                    <span className="marche-chevron">{deplie ? '▲' : '▼'}</span>
                  </div>
                </button>

                {deplie && (
                  <div className="marche-body">
                    {m.nb_offres_chiffrees > 1 && m.rang_adoc && (
                      <p className="muted" style={{ marginTop: 0 }}>
                        Notre offre arrivait au rang {m.rang_adoc} sur {m.nb_offres_chiffrees} prix connus.
                        {m.adoc_moins_disant
                          ? ' Nous étions le moins-disant.'
                          : ` Le moins-disant a proposé ${formatFcfa(m.montant_moins_disant)}.`}
                      </p>
                    )}

                    <div className="table-wrap">
                      <table className="data">
                        <thead>
                          <tr>
                            <th>Participant</th>
                            <th className="num">Prix proposé (TTC)</th>
                            <th className="num">Écart / ADOC</th>
                            <th className="num">Note</th>
                          </tr>
                        </thead>
                        <tbody>
                          {m.offres.map((o, index) => (
                            <tr key={`${o.nom}-${index}`} className={o.est_adoc ? 'ligne-adoc' : ''}>
                              <td>
                                {o.est_adoc ? <strong>ADOC (nous)</strong> : o.nom}
                                {o.est_attributaire && <span className="badge badge-retenu">Retenu</span>}
                              </td>
                              <td className="num">
                                {formatFcfa(o.montant) || <span className="muted">{o.montant_texte}</span>}
                              </td>
                              <td className="num">
                                {o.ecart_adoc_pct === null || o.ecart_adoc_pct === undefined ? (
                                  <span className="muted">—</span>
                                ) : (
                                  <span className={o.ecart_adoc_pct < 0 ? 'ecart-bas' : 'ecart-haut'}>
                                    {formatEcart(o.ecart_adoc_pct)}
                                  </span>
                                )}
                              </td>
                              <td className="num">{o.note ?? '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {montantAdocAvecMention(m) && (
                      <p className="muted">Montant ADOC tel que saisi : {texteMontantAdoc(m)}</p>
                    )}

                    {m.participants_bruts && (
                      <p className="muted">
                        Participants annoncés : {m.participants_bruts.split('\n').join(' · ')}
                      </p>
                    )}
                    {m.observations && <p className="muted">{m.observations}</p>}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </section>

      {isAdmin && (
        <section className="card card-pad">
          <div className="section-title">
            <div>
              <h2>Mettre à jour depuis le classeur</h2>
              <p>
                Envoyer le « Tableau des MI et PTF » remplace tout l'historique par son contenu.
                Seules les lignes dont la colonne « Prix des participants (TTC) » est remplie
                sont reprises.
              </p>
            </div>
          </div>
          <label className="dropzone">
            <input type="file" accept=".xlsx,.xlsm" onChange={handleImport} disabled={busy} />
            <strong>Joindre le classeur Excel</strong>
            <span>Format attendu : une feuille par année, colonnes Objet / Attribution / Prix des participants</span>
          </label>
        </section>
      )}
    </div>
  )
}

/** Le montant ADOC comporte-t-il une mention que le chiffre seul perdrait ?
 *  (par exemple « 8 850 000 (minimum); 24 780 000 (maximum) »). */
function montantAdocAvecMention(marche) {
  const offre = marche.offres.find((o) => o.est_adoc)
  if (!offre || !offre.montant_texte || offre.montant === null) return false
  const chiffres = offre.montant_texte.replace(/[^\d]/g, '')
  return chiffres !== String(offre.montant)
}

function texteMontantAdoc(marche) {
  return marche.offres.find((o) => o.est_adoc)?.montant_texte || ''
}
