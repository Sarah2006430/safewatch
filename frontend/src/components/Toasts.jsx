import { X } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useData } from '../context/DataContext'
import { INCIDENT_TYPES } from '../lib/constants'
import { pct } from '../lib/format'
import { SeverityBadge, Tile } from './ui'

export default function Toasts() {
  const { toasts, dismissToast } = useData()
  const { isStaff } = useAuth()
  const navigate = useNavigate()

  return (
    <div className="pointer-events-none fixed right-4 top-16 z-[3000] flex w-[22rem] flex-col gap-2">
      {toasts.map(({ id, incident }) => {
        const meta = INCIDENT_TYPES[incident.type] || {}
        return (
          <div
            key={id}
            className="toast-in pointer-events-auto cursor-pointer overflow-hidden border border-[var(--color-alert)]/70 panel-2 shadow-[0_20px_60px_rgba(0,0,0,.25)]"
            onClick={() => { if (isStaff) navigate(`/?incident=${incident.id}`); dismissToast(id) }}
          >
            <div className="hazard h-[4px]" />
            <div className="flex items-start gap-3 p-3">
              <Tile meta={meta} size={40} />
              <div className="min-w-0 flex-1">
                <div className="mono flex items-center gap-1.5 text-[10px] uppercase tracking-[.16em] text-[var(--color-alert)]">
                  <span className="blink h-1.5 w-1.5 bg-current" /> New alert · #{String(incident.id).padStart(4, '0')}
                </div>
                <div className="flex items-center gap-2">
                  <span className="num text-xl uppercase">{meta.label}</span>
                  <SeverityBadge severity={incident.severity} />
                </div>
                <div className="truncate text-xs text-slate-400">{incident.camera_name} · AI {pct(incident.confidence)}</div>
              </div>
              <button onClick={(e) => { e.stopPropagation(); dismissToast(id) }} className="text-slate-500 hover:text-slate-50"><X size={14} /></button>
            </div>
            {incident.snapshot_url && (
              <div className="hud hud-alert scan relative">
                <img src={incident.snapshot_url} alt="" className="h-36 w-full object-cover" />
              </div>
            )}
            <div className="mono border-t border-slate-800 px-3 py-1.5 text-[10px] uppercase tracking-wider text-slate-400">Click to review evidence and verify →</div>
          </div>
        )
      })}
    </div>
  )
}
