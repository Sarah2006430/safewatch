import { useCallback, useEffect, useRef, useState } from 'react'
import { LocateFixed, Navigation } from 'lucide-react'
import { MapContainer, Marker, Polyline, TileLayer } from 'react-leaflet'
import { Button, Card, Empty, SeverityBadge, Tile } from '../components/ui'
import { useData } from '../context/DataContext'
import { api } from '../lib/api'
import { AGENCIES, INCIDENT_TYPES } from '../lib/constants'
import { incidentIcon, OSM_ATTRIBUTION, OSM_TILES, unitIcon } from '../lib/mapIcons'
import { fmtTime, km } from '../lib/format'
import { playAlarm } from '../lib/alarm'

const NEXT = {
  assigned: [['acknowledged', 'Acknowledge', 'warning']],
  acknowledged: [['en_route', 'En route', 'primary']],
  en_route: [['on_scene', 'Arrived on scene', 'primary']],
  on_scene: [['completed', 'Mark completed', 'success']],
}
const ACTIVE = ['assigned', 'acknowledged', 'en_route', 'on_scene']

function DispatchCard({ d, unit, onUpdate }) {
  const inc = d.incident
  const meta = INCIDENT_TYPES[inc.type] || {}
  const [busy, setBusy] = useState(false)
  const update = async (status) => {
    setBusy(true)
    try { await onUpdate(d.id, status) } finally { setBusy(false) }
  }
  const from = unit?.location
  const to = inc.location
  return (
    <Card className={`overflow-hidden ${d.status === 'assigned' ? 'border-[var(--color-alert)]' : ''}`}>
      {d.status === 'assigned' && <div className="hazard h-[4px]" />}
      <div className="flex items-center gap-3 p-3">
        <Tile meta={meta} size={40} />
        <div className="flex-1">
          <div className="flex items-center gap-2"><span className="num text-xl uppercase">{meta.label}</span> <SeverityBadge severity={inc.severity} /></div>
          <div className="text-xs text-slate-400">#{inc.id} · {inc.camera_name} {inc.camera_address && `· ${inc.camera_address}`}</div>
          <div className="text-xs text-slate-500">Assigned {fmtTime(d.created_at)} · {km(d.distance_m)} · ETA ~{d.eta_minutes ?? '?'} min</div>
        </div>
        <span className="mono border border-slate-600 px-2 py-1 text-[10px] font-semibold uppercase">{d.status.replace('_', ' ')}</span>
      </div>
      <div className="grid gap-0 md:grid-cols-2">
        {inc.snapshot_url && <img src={inc.snapshot_url} alt="" className="aspect-video w-full object-cover" />}
        {to && (
          <div className="aspect-video">
            <MapContainer center={[to.lat, to.lon]} zoom={14} className="h-full w-full">
              <TileLayer url={OSM_TILES} attribution={OSM_ATTRIBUTION} className="dark-tiles" />
              <Marker position={[to.lat, to.lon]} icon={incidentIcon(inc.type, inc.status, true)} />
              {from && <Marker position={[from.lat, from.lon]} icon={unitIcon(unit.agency, unit.status)} />}
              {from && <Polyline positions={[[from.lat, from.lon], [to.lat, to.lon]]} pathOptions={{ dashArray: '8 6', color: '#ffb020' }} />}
            </MapContainer>
          </div>
        )}
      </div>
      {inc.clip_url && <video src={inc.clip_url} controls muted className="max-h-64 w-full bg-black" />}
      <div className="flex flex-wrap gap-2 p-3">
        {(NEXT[d.status] || []).map(([s, label, v]) => <Button key={s} variant={v} disabled={busy} onClick={() => update(s)}>{label}</Button>)}
        {to && (
          <a className="inline-flex items-center gap-1.5 border border-slate-600 px-3 py-2 text-[13px] font-semibold uppercase tracking-wide hover:bg-slate-800" target="_blank" rel="noreferrer"
             href={`https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route=${from ? `${from.lat},${from.lon}` : ''};${to.lat},${to.lon}`}>
            <Navigation size={14} /> Navigate
          </a>
        )}
      </div>
    </Card>
  )
}

export default function Responder() {
  const { subscribe, units } = useData()
  const [data, setData] = useState({ unit: null, dispatches: [] })
  const [sharing, setSharing] = useState(false)
  const watchId = useRef(null)
  const lastSent = useRef(0)

  const load = useCallback(() => api('/api/dispatches/mine').then(setData).catch(() => {}), [])
  useEffect(() => { load() }, [load])

  useEffect(() => subscribe(({ event, data: d }) => {
    if (!data.unit) return
    if ((event === 'dispatch_created' || event === 'dispatch_updated') && d.unit_id === data.unit.id) {
      if (event === 'dispatch_created') playAlarm(true)
      load()
    }
  }), [subscribe, data.unit, load])

  // Share live GPS position of the unit so the control room map stays accurate
  useEffect(() => {
    if (!sharing || !data.unit || !navigator.geolocation) return
    watchId.current = navigator.geolocation.watchPosition((pos) => {
      if (Date.now() - lastSent.current < 10000) return
      lastSent.current = Date.now()
      api(`/api/units/${data.unit.id}`, { method: 'PATCH', body: { lat: pos.coords.latitude, lon: pos.coords.longitude } }).catch(() => {})
    }, () => setSharing(false), { enableHighAccuracy: true })
    return () => navigator.geolocation.clearWatch(watchId.current)
  }, [sharing, data.unit])

  const updateStatus = async (id, status) => { await api(`/api/dispatches/${id}/status`, { method: 'POST', body: { status } }); load() }

  if (!data.unit) return <Empty>Your account is not linked to a response unit.</Empty>
  const unit = units.find((u) => u.id === data.unit.id) || data.unit
  const active = data.dispatches.filter((d) => ACTIVE.includes(d.status))
  const past = data.dispatches.filter((d) => !ACTIVE.includes(d.status))

  return (
    <div className="scroll-thin mx-auto h-full max-w-4xl overflow-y-auto p-4">
      <Card className="mb-4 flex flex-wrap items-center gap-3 p-4">
        <Tile meta={AGENCIES[unit.agency]} size={48} />
        <div className="flex-1">
          <div className="num text-2xl uppercase">{unit.name}</div>
          <div className="mono text-[10px] uppercase tracking-wider text-slate-400">{AGENCIES[unit.agency]?.label} · status: {unit.status.replace('_', ' ')}</div>
        </div>
        <Button variant={sharing ? 'success' : 'ghost'} onClick={() => setSharing(!sharing)}>
          <LocateFixed size={15} /> {sharing ? 'Sharing live location' : 'Share live location'}
        </Button>
      </Card>
      <div className="label mb-2">Active assignments · {active.length}</div>
      {!active.length && <Empty>No active assignments. Stand by.</Empty>}
      <div className="space-y-4">{active.map((d) => <DispatchCard key={d.id} d={d} unit={unit} onUpdate={updateStatus} />)}</div>
      {!!past.length && (
        <>
          <div className="label mb-2 mt-6">Recent</div>
          {past.map((d) => (
            <div key={d.id} className="mb-1 flex items-center justify-between border border-slate-800 bg-slate-900 px-3 py-2 text-sm">
              <span className="flex items-center gap-2"><span style={{ color: INCIDENT_TYPES[d.incident.type]?.color }}>{INCIDENT_TYPES[d.incident.type]?.icon}</span><span className="mono text-[11px] text-slate-500">#{d.incident.id}</span>{INCIDENT_TYPES[d.incident.type]?.label}</span>
              <span className="mono text-[10px] uppercase text-slate-500">{d.status}</span>
            </div>
          ))}
        </>
      )}
    </div>
  )
}
