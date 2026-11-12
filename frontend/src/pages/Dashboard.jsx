import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import IncidentDetail from '../components/IncidentDetail'
import IncidentFeed from '../components/IncidentFeed'
import IncidentMap from '../components/IncidentMap'
import { CameraThumb } from '../components/LiveStream'
import StatsBar from '../components/StatsBar'
import { useData } from '../context/DataContext'
import { api } from '../lib/api'
import { AGENCIES, INCIDENT_TYPES, OPEN_STATUSES } from '../lib/constants'

function CameraRibbon({ cameras, incidents, compact }) {
  const active = cameras.filter((c) => c.is_active)
  if (!active.length) return null
  return (
    <div className="scroll-thin pointer-events-auto flex min-w-0 gap-2 overflow-x-auto pb-1">
      {active.slice(0, 6).map((c) => {
        const alert = incidents.find((i) => i.camera_id === c.id && i.status === 'pending')
        const meta = alert && INCIDENT_TYPES[alert.type]
        return (
          <div key={c.id} className={`hud scan relative shrink-0 ${compact ? "w-36" : "w-44"} overflow-hidden border bg-black ${alert ? 'hud-alert border-[var(--color-alert)]' : 'border-slate-700'}`}>
            <CameraThumb cameraId={c.id} className="aspect-video w-full" />
            <div className="absolute inset-x-0 bottom-0 flex items-center gap-1.5 bg-gradient-to-t from-black/95 to-transparent px-2 pb-1 pt-4">
              <span className={`h-1.5 w-1.5 ${c.status === 'online' ? 'bg-[var(--color-ok)]' : 'bg-[var(--color-alert)]'}`} />
              <span className="mono truncate text-[10px] uppercase text-slate-200">CAM{String(c.id).padStart(2, '0')} · {c.name}</span>
            </div>
            {meta && (
              <div className="mono absolute left-0 top-0 flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-bold text-black" style={{ background: meta.color }}>
                {meta.icon}{meta.short}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

function Legend() {
  return (
    <div className="pointer-events-auto border border-slate-800 overlay px-3 py-2 backdrop-blur">
      <div className="label mb-1.5">Map key</div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1">
        {Object.values(INCIDENT_TYPES).map((m) => (
          <div key={m.short} className="mono flex items-center gap-1.5 text-[10px] uppercase text-slate-300">
            <span className="h-2 w-2 rotate-45" style={{ background: m.color }} />{m.short}
          </div>
        ))}
        {Object.values(AGENCIES).map((a) => (
          <div key={a.label} className="mono flex items-center gap-1.5 text-[10px] uppercase text-slate-400">
            <span className="h-2 w-2" style={{ background: a.color }} />{a.label}
          </div>
        ))}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const { incidents, cameras, units, subscribe, setIncidents } = useData()
  const [params, setParams] = useSearchParams()
  const selectedId = params.get('incident') ? Number(params.get('incident')) : null
  const [detail, setDetail] = useState(null)
  const [showClosed, setShowClosed] = useState(false)

  const select = useCallback((id) => setParams(id ? { incident: String(id) } : {}), [setParams])

  const load = useCallback(async (id) => {
    try {
      const d = await api(`/api/incidents/${id}`)
      setDetail(d)
    } catch { setDetail(null) }
  }, [])

  useEffect(() => {
    if (selectedId) load(selectedId)
    else setDetail(null)
  }, [selectedId, load])

  // Refresh the open incident whenever anything related to it changes in real time
  useEffect(() => subscribe(({ event, data }) => {
    if (!selectedId) return
    const id = data?.incident_id ?? data?.incident?.id ?? data?.id
    if (event.startsWith('incident_') && data.id === selectedId) load(selectedId)
    else if (event.startsWith('dispatch_') && id === selectedId) load(selectedId)
    else if (event === 'unit_updated' && detail?.status !== 'resolved') load(selectedId)
  }), [subscribe, selectedId, load, detail?.status])

  const onChange = (d) => {
    setDetail(d)
    setIncidents((list) => list.map((i) => (i.id === d.id ? { ...i, ...d } : i)))
  }

  const openCount = incidents.filter((i) => OPEN_STATUSES.includes(i.status)).length

  return (
    <div className="flex h-full flex-col">
      <StatsBar />
      <div className="flex min-h-0 flex-1">
        <section className="w-[22rem] shrink-0 border-r border-slate-800 panel">
          <IncidentFeed incidents={incidents} selectedId={selectedId} onSelect={select} />
        </section>
        <section className="relative min-w-0 flex-1 overflow-hidden">
          <IncidentMap
            incidents={incidents}
            cameras={cameras}
            units={units}
            selected={detail}
            onSelect={select}
            showClosed={showClosed}
          />
          {/* vignette so overlays read on any tile */}
          <div className="pointer-events-none absolute inset-0 z-[400] shadow-[inset_0_0_120px_rgba(0,0,0,.75)]" />
          <div className="pointer-events-none absolute left-16 top-3 z-[1000] flex items-center gap-3">
            <div className="pointer-events-auto border border-slate-800 overlay px-3 py-1.5 backdrop-blur">
              <div className="mono text-[9px] uppercase tracking-[.16em] text-slate-500">Situation</div>
              <div className="num text-lg uppercase">{openCount ? `${openCount} active incident${openCount > 1 ? 's' : ''}` : 'All sectors clear'}</div>
            </div>
            <label className="pointer-events-auto mono flex items-center gap-2 border border-slate-800 overlay px-3 py-2 text-[10px] uppercase tracking-wider text-slate-300 backdrop-blur">
              <input type="checkbox" checked={showClosed} onChange={(e) => setShowClosed(e.target.checked)} />
              Show closed
            </label>
          </div>
          <div className="pointer-events-none absolute inset-x-3 bottom-6 z-[1000] flex items-end justify-between gap-3">
            <CameraRibbon cameras={cameras} incidents={incidents} compact={!!detail} />
            <div className="hidden 2xl:block"><Legend /></div>
          </div>
        </section>
        {detail && (
          <section className="rise w-[27rem] shrink-0 border-l border-slate-800 panel-2">
            <IncidentDetail incident={detail} onChange={onChange} onClose={() => select(null)} />
          </section>
        )}
      </div>
    </div>
  )
}
