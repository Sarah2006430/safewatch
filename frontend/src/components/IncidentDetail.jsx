import { useState } from 'react'
import { CheckCircle2, ExternalLink, MessageSquarePlus, Send, ShieldCheck, X, XCircle } from 'lucide-react'
import { api } from '../lib/api'
import { AGENCIES, INCIDENT_TYPES, OPEN_STATUSES } from '../lib/constants'
import { fmtClock, fmtTime, km, latlonText, pct } from '../lib/format'
import LiveStream from './LiveStream'
import { Button, inputCls, SeverityBadge, StatusBadge, Tile } from './ui'

const DISPATCH_STATUS = {
  assigned: 'text-[var(--color-warn)]', acknowledged: 'text-[var(--color-warn)]', en_route: 'text-[var(--color-info)]',
  on_scene: 'text-[#e8590c]', completed: 'text-[var(--color-ok)]', cancelled: 'text-slate-500',
}

const STEPS = ['pending', 'verified', 'dispatched', 'resolved']

function Progress({ status }) {
  const idx = status === 'false_alarm' ? -1 : STEPS.indexOf(status)
  return (
    <div className="grid grid-cols-4 gap-[3px]">
      {STEPS.map((s, i) => (
        <div key={s}>
          <div className={`h-[3px] ${status === 'false_alarm' ? 'bg-slate-700' : i <= idx ? 'bg-[var(--color-signal)]' : 'bg-slate-800'}`} />
          <div className={`mono mt-1 text-[9px] uppercase tracking-wider ${i === idx ? 'text-slate-100' : 'text-slate-600'}`}>{s}</div>
        </div>
      ))}
    </div>
  )
}

function Evidence({ incident }) {
  const [mode, setMode] = useState(incident.clip_url ? 'clip' : 'snapshot')
  const modes = [
    ['clip', 'Evidence clip', !!incident.clip_url],
    ['snapshot', 'Snapshot', !!incident.snapshot_url],
    ['live', 'Live', !!incident.camera_id],
  ]
  const current = mode === 'clip' && !incident.clip_url ? 'snapshot' : mode
  const hot = incident.status === 'pending'
  return (
    <div>
      <div className={`hud scan relative aspect-video overflow-hidden bg-black ${hot ? 'hud-alert' : ''}`}>
        {current === 'clip' && <video key={incident.clip_url} src={incident.clip_url} controls autoPlay muted loop playsInline className="h-full w-full object-contain" />}
        {current === 'snapshot' && (incident.snapshot_url
          ? <img src={incident.snapshot_url} alt="Evidence snapshot" className="h-full w-full object-contain" />
          : <div className="mono flex h-full items-center justify-center text-xs uppercase text-slate-500">No snapshot</div>)}
        {current === 'live' && <LiveStream cameraId={incident.camera_id} className="h-full w-full" />}
        <div className="mono pointer-events-none absolute right-3 top-2 z-10 flex items-center gap-1.5 text-[10px] uppercase text-white/90">
          {current === 'live' ? <><span className="blink h-2 w-2 rounded-full bg-[var(--color-alert)]" />Live</> : current === 'clip' ? 'Playback' : 'Still'}
        </div>
        {!incident.clip_url && (
          <div className="mono absolute bottom-2 left-3 z-10 flex items-center gap-1.5 bg-black/80 px-2 py-0.5 text-[10px] uppercase text-slate-300">
            <span className="blink h-1.5 w-1.5 bg-[var(--color-alert)]" /> Recording evidence clip
          </div>
        )}
      </div>
      <div className="grid grid-cols-3 border-x border-b border-slate-800">
        {modes.map(([k, label, ok]) => (
          <button
            key={k}
            disabled={!ok}
            onClick={() => setMode(k)}
            className={`mono relative py-1.5 text-[10px] uppercase tracking-wider disabled:opacity-30 ${current === k ? 'bg-slate-800 text-slate-50' : 'text-slate-500 hover:text-slate-200'}`}
          >
            {current === k && <span className="absolute inset-x-0 top-0 h-[2px] bg-[var(--color-signal)]" />}
            {label}
          </button>
        ))}
      </div>
    </div>
  )
}

function DispatchPanel({ incident, onDone }) {
  const [selected, setSelected] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const toggle = (id) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]))

  const dispatch = async () => {
    setBusy(true)
    setError('')
    try {
      onDone(await api(`/api/incidents/${incident.id}/dispatch`, { method: 'POST', body: { unit_ids: selected } }))
      setSelected([])
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  const autoPick = () => setSelected(incident.suggestions.map((g) => g.units[0]?.id).filter(Boolean))

  return (
    <div className="border border-slate-800 panel">
      <div className="flex items-center justify-between border-b border-slate-800 px-3 py-2">
        <div className="label">Coordinate response</div>
        <button className="mono text-[10px] uppercase tracking-wider text-[var(--color-signal)] hover:underline" onClick={autoPick}>Nearest per agency</button>
      </div>
      <div className="divide-y divide-slate-800/70">
        {incident.suggestions.map((group) => {
          const a = AGENCIES[group.agency]
          return (
            <div key={group.agency} className="px-3 py-2">
              <div className="mono mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider" style={{ color: a.color }}>{a.icon} {a.label}</div>
              {!group.units.length && <div className="mono text-[11px] text-slate-500">No unit available</div>}
              {group.units.map((u, idx) => {
                const on = selected.includes(u.id)
                return (
                  <label key={u.id} className={`flex cursor-pointer items-center gap-2 px-2 py-1.5 text-sm transition ${on ? 'bg-[var(--color-signal)]/10 outline outline-1 outline-[var(--color-signal)]/60' : 'hover:bg-slate-800/60'}`}>
                    <input type="checkbox" checked={on} onChange={() => toggle(u.id)} />
                    <span className="flex-1 truncate">{u.name}</span>
                    {idx === 0 && <span className="mono text-[9px] uppercase text-slate-500">closest</span>}
                    <span className="mono w-14 text-right text-[11px] text-slate-400">{km(u.distance_m)}</span>
                    <span className="mono w-14 text-right text-[11px] text-slate-100">{u.eta_minutes ?? '?'} min</span>
                  </label>
                )
              })}
            </div>
          )
        })}
      </div>
      {error && <div className="px-3 pb-2 text-xs text-[var(--color-alert)]">{error}</div>}
      <div className="p-3 pt-1">
        <Button className="w-full" disabled={!selected.length || busy} onClick={dispatch}>
          <Send size={14} /> Dispatch {selected.length || ''} unit{selected.length === 1 ? '' : 's'}
        </Button>
      </div>
    </div>
  )
}

export default function IncidentDetail({ incident, onChange, onClose }) {
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const meta = INCIDENT_TYPES[incident.type] || {}
  const open = OPEN_STATUSES.includes(incident.status)

  const act = async (path, body = { notes: note }) => {
    setBusy(true)
    setError('')
    try {
      onChange(await api(`/api/incidents/${incident.id}/${path}`, { method: 'POST', body }))
      setNote('')
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  const details = Object.entries(incident.details || {}).filter(([k]) => !['geo_source'].includes(k))

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-800">
        {incident.status === 'pending' && <div className="hazard h-[4px]" />}
        <div className="flex items-start gap-3 p-4 pb-3">
          <Tile meta={meta} size={44} />
          <div className="min-w-0 flex-1">
            <div className="mono text-[10px] uppercase tracking-[.16em] text-slate-500">Incident #{String(incident.id).padStart(4, '0')}</div>
            <h2 className="num text-2xl uppercase leading-tight">{meta.label}</h2>
            <div className="mt-1 flex flex-wrap items-center gap-1.5">
              <SeverityBadge severity={incident.severity} />
              <StatusBadge status={incident.status} />
              <span className="mono text-[10px] text-slate-500">{fmtTime(incident.detected_at)}</span>
            </div>
          </div>
          <button onClick={onClose} className="p-1 text-slate-500 hover:bg-slate-800 hover:text-slate-50"><X size={18} /></button>
        </div>
        <div className="px-4 pb-3"><Progress status={incident.status} /></div>
      </div>

      <div className="scroll-thin flex-1 space-y-4 overflow-y-auto p-4">
        <Evidence key={`${incident.id}-${incident.clip_url || ''}`} incident={incident} />

        <div className="grid grid-cols-2 border-l border-t border-slate-800 text-xs">
          <Info label="Camera" value={incident.camera_name || '—'} />
          <Info label="AI confidence" value={`${pct(incident.confidence)} · ${incident.detection_count} hit${incident.detection_count > 1 ? 's' : ''}`} accent />
          <Info label={`Position · ${incident.details?.geo_source === 'calibrated' ? 'calibrated' : 'camera'}`} value={latlonText(incident.location)} mono />
          <Info label="Last seen" value={fmtClock(incident.last_detected_at)} mono />
          {incident.camera_address && <div className="col-span-2"><Info label="Address" value={incident.camera_address} /></div>}
        </div>
        {incident.location && (
          <a className="mono inline-flex items-center gap-1 text-[11px] uppercase tracking-wider text-[var(--color-signal)] hover:underline" target="_blank" rel="noreferrer"
             href={`https://www.openstreetmap.org/?mlat=${incident.location.lat}&mlon=${incident.location.lon}#map=18/${incident.location.lat}/${incident.location.lon}`}>
            Open in OpenStreetMap <ExternalLink size={11} />
          </a>
        )}

        {!!details.length && (
          <div className="border border-slate-800 panel p-3">
            <div className="label mb-2">Model output</div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
              {details.map(([k, v]) => (
                <div key={k} className="mono flex justify-between gap-2 border-b border-dotted border-slate-800 pb-0.5 text-[11px]">
                  <span className="text-slate-500">{k.replaceAll('_', ' ')}</span><span className="truncate text-slate-200">{String(v)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {open && (
          <div className="space-y-2">
            <textarea className={`${inputCls} h-16 resize-none`} placeholder="Operator notes (optional)…" value={note} onChange={(e) => setNote(e.target.value)} />
            <div className="grid grid-cols-2 gap-2">
              {incident.status === 'pending' && <Button variant="warning" disabled={busy} onClick={() => act('verify')}><CheckCircle2 size={15} /> Verify</Button>}
              {['pending', 'verified'].includes(incident.status) && <Button variant="ghost" disabled={busy} onClick={() => act('false-alarm')}><XCircle size={15} /> False alarm</Button>}
              <Button variant="success" disabled={busy} onClick={() => act('resolve')}><ShieldCheck size={15} /> Resolve</Button>
              <Button variant="ghost" disabled={busy || !note.trim()} onClick={() => act('notes')}><MessageSquarePlus size={15} /> Add note</Button>
            </div>
            {error && <div className="text-xs text-[var(--color-alert)]">{error}</div>}
          </div>
        )}

        {open && incident.suggestions && <DispatchPanel incident={incident} onDone={onChange} />}

        {!!incident.dispatches?.length && (
          <div>
            <div className="label mb-2">Assigned units</div>
            <div className="border border-slate-800">
              {incident.dispatches.map((d) => {
                const a = AGENCIES[d.unit?.agency]
                return (
                  <div key={d.id} className="flex items-center gap-2 border-b border-slate-800 px-3 py-2 text-sm last:border-0">
                    <span style={{ color: a?.color }}>{a?.icon}</span>
                    <span className="flex-1 truncate">{d.unit?.name}</span>
                    <span className="mono text-[10px] text-slate-500">{km(d.distance_m)}{d.eta_minutes != null && ` · ETA ${d.eta_minutes}m`}</span>
                    <span className={`mono text-[10px] font-semibold uppercase ${DISPATCH_STATUS[d.status]}`}>{d.status.replace('_', ' ')}</span>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        <div>
          <div className="label mb-2">Audit log</div>
          <ol className="relative ml-1 border-l border-slate-700">
            {(incident.events || []).map((e) => (
              <li key={e.id} className="mb-3 ml-4">
                <span className="absolute -left-[4px] mt-1.5 h-[7px] w-[7px] bg-[var(--color-signal)]" />
                <div className="mono text-[10px] text-slate-500">{fmtClock(e.created_at)} · {e.actor}</div>
                <div className="text-[13px] text-slate-200">{e.message}</div>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </div>
  )
}

function Info({ label, value, mono, accent }) {
  return (
    <div className="border-b border-r border-slate-800 px-3 py-2">
      <div className="mono text-[9px] uppercase tracking-[.14em] text-slate-500">{label}</div>
      <div className={`truncate ${mono ? 'mono text-[12px]' : 'text-[13px]'} ${accent ? 'text-[var(--color-signal)]' : 'text-slate-100'}`}>{value}</div>
    </div>
  )
}
