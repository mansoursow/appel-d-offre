import { useEffect } from 'react'

export default function Modal({ title, subtitle, onClose, children, closable = true }) {
  useEffect(() => {
    if (!closable) return undefined
    function onKey(event) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose, closable])

  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (closable && e.target === e.currentTarget) onClose()
      }}
    >
      <div className="modal" role="dialog" aria-modal="true">
        <h3>{title}</h3>
        {subtitle && <p className="muted" style={{ marginTop: 0 }}>{subtitle}</p>}
        {children}
      </div>
    </div>
  )
}
