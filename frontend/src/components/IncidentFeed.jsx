import { useMemo, useState } from 'react'
import { INCIDENT_TYPES, OPEN_STATUSES } from '../lib/constants'
import { pct, timeAgo } from '../lib/format'
import { Empty, SeverityBadge, StatusBadge } from './ui'

const TABS = [
  { key: 'open', label: 'Active' },
  { key: 'pending', label: 'Review' },
  { key: 'all', label: 'All' },
]

export default function IncidentFeed({ incidents, selectedId, onSelect }) {
  const [tab, setTab] = useState('open')
  const [types, setTypes] = useState([])

  const counts = useMemo(() => ({
    open: incidents.filter((i) => OPEN_STATUSES.includes(i.status)).length,
    pending: incidents.filter((i) => i.status === 'pending').length,
    all: incidents.length,
  }), [incidents])

  const list = useMemo(() => incidents.filter((i) => {
    if (tab === 'open' && !OPEN_STATUSES.includes(i.status)) return false
    if (tab === 'pending' && i.status !== 'pending') return false
    if (types.length && !types.includes(i.type)) return false
    return true
  }), [incidents, tab, types])

  const toggleType = (t) => setTypes((s) => (s.includes(t) ? s.filter((x) => x !== t) : [...s, t]))

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-800">
        <div className="flex items-center justify-between px-4 pb-2 pt-3">
          <div className="label">Incident queue</div>
          <div className="mono text-[10px] text-slate-500">{list.length} shown</div>
        </div>
        <div className="grid grid-cols-3 border-y border-slate-800">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`mono relative py-2 text-[11px] uppercase tracking-wider transition ${tab === t.key ? 'bg-slate-900 text-slate-50' : 'text-slate-500 hover:text-slate-200'}`}
            >
              {tab === t.key && <span className="absolute inset-x-0 bottom-0 h-[2px] bg-[var(--color-signal)]" />}
              {t.label} <span className={t.key === 'pending' && counts.pending ? 'text-[var(--color-alert)]' : 'text-slate-600'}>{counts[t.key]}</span>
            </button>
          ))}
        </div>
        <div className="flex gap-1 px-3 py-2">
          {Object.entries(INCIDENT_TYPES).map(([k, m]) => {
            const on = types.includes(k)
            return (
              <button
                key={k}
                onClick={() => toggleType(k)}
                title={m.label}
                className={`flex h-7 flex-1 items-center justify-center border transition ${on ? 'text-black' : 'border-slate-800 text-slate-400 hover:border-slate-600 hover:text-slate-50'}`}
                style={on ? { background: m.color, borderColor: m.color } : undefined}
              >
                {m.icon}
              </button>
            )
          })}
        </div>
      </div>

      <div className="scroll-thin flex-1 overflow-y-auto">
        {!list.length && <Empty>Queue clear · no incidents</Empty>}
        {list.map((i) => {
          const meta = INCIDENT_TYPES[i.type] || {}
          const active = selectedId === i.id
          const hot = i.status === 'pending'
          return (
            <button
              key={i.id}
              onClick={() => onSelect(i.id)}
              className={`rise group relative flex w-full gap-3 border-b border-slate-800/80 px-3 py-3 text-left transition ${active ? 'bg-slate-800/70' : hot ? 'bg-[var(--color-alert)]/[.06] hover:bg-[var(--color-alert)]/[.1]' : 'hover:bg-slate-900'}`}
            >
              <span className="absolute inset-y-0 left-0 w-[3px]" style={{ background: active ? 'var(--color-signal)' : hot ? meta.color : 'transparent' }} />
              <div className="relative h-[60px] w-[88px] shrink-0 overflow-hidden bg-black">
                {i.snapshot_url
                  ? <img src={i.snapshot_url} alt="" className="h-full w-full object-cover opacity-90 transition group-hover:opacity-100" loading="lazy" />
                  : <div className="flex h-full items-center justify-center" style={{ color: meta.color }}>{meta.Icon && <meta.Icon size={22} />}</div>}
                <span className="absolute left-0 top-0 flex h-5 w-5 items-center justify-center text-black" style={{ background: meta.color }}>
                  {meta.Icon && <meta.Icon size={12} strokeWidth={2.6} />}
                </span>
                {i.clip_url && <span className="mono absolute bottom-0 right-0 bg-black/80 px-1 text-[9px] text-slate-300">CLIP</span>}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="mono text-[10px] text-slate-500">#{String(i.id).padStart(4, '0')}</span>
                  <SeverityBadge severity={i.severity} />
                  <span className="mono ml-auto text-[10px] text-slate-500">{timeAgo(i.detected_at)}</span>
                </div>
                <div className="mt-0.5 truncate text-[14px] font-semibold text-slate-100">{meta.label}</div>
                <div className="truncate text-xs text-slate-400">{i.camera_name || 'Deleted camera'}</div>
                <div className="mt-1.5 flex items-center gap-2">
                  <StatusBadge status={i.status} />
                  <span className="mono text-[10px] text-slate-400">AI {pct(i.confidence)}</span>
                  {i.detection_count > 1 && <span className="mono text-[10px] text-slate-500">×{i.detection_count}</span>}
                </div>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
