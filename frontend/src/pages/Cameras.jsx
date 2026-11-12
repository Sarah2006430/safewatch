import { useState } from 'react'
import { Pencil, Plus, Shapes, Trash2, Upload } from 'lucide-react'
import ImportRecording from '../components/ImportRecording'
import { CameraThumb } from '../components/LiveStream'
import MapPicker from '../components/MapPicker'
import { mapCenter } from '../components/IncidentMap'
import ZoneEditor from '../components/ZoneEditor'
import { Button, Card, Empty, Field, inputCls, Modal, PageHeader } from '../components/ui'
import { useData } from '../context/DataContext'
import { api } from '../lib/api'
import { DETECTION_KEYS, INCIDENT_TYPES } from '../lib/constants'
import { latlonText, timeAgo } from '../lib/format'

const EMPTY = { name: '', stream_url: '', address: '', heading: '', detections: DETECTION_KEYS, is_active: true, location: null, calibration: '' }

function CameraForm({ initial, center, onClose }) {
  const [f, setF] = useState(() => initial
    ? { ...initial, heading: initial.heading ?? '', calibration: initial.calibration ? JSON.stringify(initial.calibration) : '' }
    : EMPTY)
  const [error, setError] = useState('')
  const set = (k, v) => setF((s) => ({ ...s, [k]: v }))
  const toggleDet = (k) => set('detections', f.detections.includes(k) ? f.detections.filter((x) => x !== k) : [...f.detections, k])

  const save = async () => {
    setError('')
    if (!f.location) return setError('Click the map to set the camera location')
    let calibration = null
    if (f.calibration.trim()) {
      try { calibration = JSON.parse(f.calibration) } catch { return setError('Calibration must be valid JSON') }
    }
    const body = {
      name: f.name, stream_url: f.stream_url, address: f.address, is_active: f.is_active,
      heading: f.heading === '' ? null : Number(f.heading), detections: f.detections,
      lat: f.location.lat, lon: f.location.lon,
      ...(calibration ? { calibration } : initial ? { clear_calibration: true } : {}),
    }
    try {
      await api(initial ? `/api/cameras/${initial.id}` : '/api/cameras', { method: initial ? 'PATCH' : 'POST', body })
      onClose()
    } catch (e) { setError(e.message) }
  }

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="space-y-3">
        <Field label="Camera name"><input className={inputCls} value={f.name} onChange={(e) => set('name', e.target.value)} placeholder="North Gate CCTV" /></Field>
        <Field label="Stream URL" hint="RTSP: rtsp://user:pass@192.168.1.64:554/stream1 · HTTP/MJPEG URL · video file path · webcam index (0)">
          <input className={inputCls} value={f.stream_url} onChange={(e) => set('stream_url', e.target.value)} placeholder="rtsp://..." />
        </Field>
        <Field label="Address / landmark"><input className={inputCls} value={f.address} onChange={(e) => set('address', e.target.value)} /></Field>
        <Field label="Heading (° the camera faces, optional)"><input type="number" className={inputCls} value={f.heading} onChange={(e) => set('heading', e.target.value)} /></Field>
        <Field label="Detections enabled">
          <div className="flex flex-wrap gap-2">
            {DETECTION_KEYS.map((k) => (
              <button key={k} type="button" onClick={() => toggleDet(k)}
                className={`mono flex items-center gap-1.5 border px-2.5 py-1 text-[11px] uppercase tracking-wide ${f.detections.includes(k) ? 'text-black' : 'border-slate-700 text-slate-500'}`}
                style={f.detections.includes(k) ? { background: INCIDENT_TYPES[k].color, borderColor: INCIDENT_TYPES[k].color } : undefined}>
                {INCIDENT_TYPES[k].icon} {INCIDENT_TYPES[k].short}
              </button>
            ))}
          </div>
        </Field>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.is_active} onChange={(e) => set('is_active', e.target.checked)} /> Active (analysed by detector)</label>
      </div>
      <div className="space-y-3">
        <Field label={`Location — click map (${latlonText(f.location)})`}>
          <MapPicker value={f.location} center={center} onChange={(v) => set('location', v)} height={260} />
        </Field>
        <Field label="Ground calibration (advanced, optional)" hint='Maps image points to GPS for precise incident location: {"image":[[x,y]×4 normalised 0-1],"geo":[[lat,lon]×4]}'>
          <textarea className={`${inputCls} h-20 font-mono text-xs`} value={f.calibration} onChange={(e) => set('calibration', e.target.value)} />
        </Field>
      </div>
      {error && <div className="text-sm text-[var(--color-alert)] md:col-span-2">{error}</div>}
      <div className="flex justify-end gap-2 md:col-span-2">
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button onClick={save} disabled={!f.name || !f.stream_url}>{initial ? 'Save changes' : 'Add camera'}</Button>
      </div>
    </div>
  )
}

export default function Cameras() {
  const { cameras, units } = useData()
  const [editing, setEditing] = useState(null) // null | 'new' | camera
  const [zonesFor, setZonesFor] = useState(null)
  const [importing, setImporting] = useState(false)
  const center = mapCenter(cameras, units)
  const zoneCam = zonesFor && cameras.find((c) => c.id === zonesFor)

  const remove = async (c) => {
    if (!confirm(`Delete camera "${c.name}"? Its zones will be removed too.`)) return
    await api(`/api/cameras/${c.id}`, { method: 'DELETE' })
  }
  const toggle = (c) => api(`/api/cameras/${c.id}`, { method: 'PATCH', body: { is_active: !c.is_active } })

  return (
    <div className="scroll-thin h-full overflow-y-auto p-4">
      <PageHeader kicker="RTSP · CCTV · IP cameras analysed by YOLO in real time" title="Camera network">
        <Button variant="ghost" onClick={() => setImporting(true)}><Upload size={16} /> Import recording</Button>
        <Button onClick={() => setEditing('new')}><Plus size={16} /> Add camera</Button>
      </PageHeader>
      {!cameras.length && <Empty>No cameras yet.</Empty>}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {cameras.map((c) => (
          <Card key={c.id} className="overflow-hidden">
            <div className="hud scan relative aspect-video bg-black">
              {c.is_active
                ? <CameraThumb cameraId={c.id} className="h-full w-full" />
                : <div className="mono flex h-full items-center justify-center text-xs uppercase text-slate-500">Camera disabled</div>}
              <span className="mono absolute right-3 top-2 z-10 text-[10px] text-white/80">CAM{String(c.id).padStart(2, '0')}</span>
            </div>
            <div className="space-y-2 p-3">
              <div className="flex items-center gap-2">
                <span className={`h-2 w-2 ${!c.is_active ? 'bg-slate-600' : c.status === 'online' ? 'bg-[var(--color-ok)] shadow-[0_0_8px_var(--color-ok)]' : 'blink bg-[var(--color-alert)]'}`} />
                <span className="flex-1 truncate font-medium">{c.name}</span>
                <span className="mono text-[10px] uppercase text-slate-500">{c.is_active ? c.status : 'disabled'}</span>
              </div>
              <div className="truncate font-mono text-[11px] text-slate-500" title={c.stream_url}>{c.stream_url.replace(/\/\/([^:@/]+):([^@/]+)@/, '//$1:••••@')}</div>
              <div className="text-xs text-slate-400">{c.address} · {latlonText(c.location)}</div>
              {c.status_message && c.status !== 'online' && <div className="mono text-[11px] text-[var(--color-signal)]">{c.status_message}</div>}
              <div className="text-[11px] text-slate-500">Last frame: {timeAgo(c.last_seen)} · {c.zones.length} zone(s)</div>
              <div className="flex flex-wrap gap-1">
                {c.detections.map((d) => <span key={d} title={INCIDENT_TYPES[d]?.label} className="flex h-6 w-6 items-center justify-center border border-slate-700" style={{ color: INCIDENT_TYPES[d]?.color }}>{INCIDENT_TYPES[d]?.icon}</span>)}
              </div>
              <div className="flex gap-2 pt-1">
                <Button variant="ghost" className="flex-1" onClick={() => setZonesFor(c.id)}><Shapes size={14} /> Zones</Button>
                <Button variant="ghost" onClick={() => setEditing(c)}><Pencil size={14} /></Button>
                <Button variant="ghost" onClick={() => toggle(c)}>{c.is_active ? 'Disable' : 'Enable'}</Button>
                <Button variant="ghost" onClick={() => remove(c)}><Trash2 size={14} /></Button>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {importing && (
        <Modal title="Import CCTV recording" onClose={() => setImporting(false)} wide>
          <ImportRecording center={center} onClose={() => setImporting(false)} />
        </Modal>
      )}
      {editing && (
        <Modal title={editing === 'new' ? 'Add camera' : `Edit ${editing.name}`} onClose={() => setEditing(null)} wide>
          <CameraForm initial={editing === 'new' ? null : editing} center={center} onClose={() => setEditing(null)} />
        </Modal>
      )}
      {zoneCam && (
        <Modal title={`Zones — ${zoneCam.name}`} onClose={() => setZonesFor(null)} wide>
          <ZoneEditor camera={zoneCam} />
        </Modal>
      )}
    </div>
  )
}
