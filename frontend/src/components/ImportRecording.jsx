import { useRef, useState } from 'react'
import { FileVideo, Upload } from 'lucide-react'
import { upload } from '../lib/api'
import { DETECTION_KEYS, INCIDENT_TYPES } from '../lib/constants'
import { latlonText } from '../lib/format'
import MapPicker from './MapPicker'
import { Button, Field, inputCls } from './ui'

const ACCEPT = '.mp4,.avi,.mov,.mkv,.webm,.mpg,.mpeg,.m4v'

/**
 * Import recorded CCTV footage. The file is stored by the backend and registered as a
 * camera; the detector picks it up within ~15 s and analyses it exactly like a live feed
 * (looping), raising real alerts with evidence clips.
 */
export default function ImportRecording({ center, onClose }) {
  const [file, setFile] = useState(null)
  const [name, setName] = useState('')
  const [address, setAddress] = useState('')
  const [location, setLocation] = useState(null)
  const [dets, setDets] = useState(DETECTION_KEYS)
  const [progress, setProgress] = useState(null)
  const [error, setError] = useState('')
  const input = useRef(null)

  const pick = (f) => {
    if (!f) return
    setFile(f)
    if (!name) setName(f.name.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' '))
  }
  const toggle = (k) => setDets((d) => (d.includes(k) ? d.filter((x) => x !== k) : [...d, k]))

  const submit = async () => {
    setError('')
    const fd = new FormData()
    fd.append('file', file)
    fd.append('name', name)
    fd.append('address', address)
    fd.append('detections', dets.join(','))
    if (location) { fd.append('lat', location.lat); fd.append('lon', location.lon) }
    try {
      setProgress(0)
      await upload('/api/cameras/import', fd, setProgress)
      onClose()
    } catch (e) {
      setError(e.message)
      setProgress(null)
    }
  }

  return (
    <div className="grid gap-5 md:grid-cols-2">
      <div className="space-y-4">
        <div
          onClick={() => input.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => { e.preventDefault(); pick(e.dataTransfer.files?.[0]) }}
          className="flex cursor-pointer flex-col items-center justify-center gap-2 border-2 border-dashed border-slate-600 bg-slate-950 px-4 py-8 text-center hover:border-[var(--color-signal)]"
        >
          {file ? <FileVideo size={28} className="text-[var(--color-signal)]" /> : <Upload size={28} className="text-slate-400" />}
          <div className="text-sm font-medium">{file ? file.name : 'Drop a video here or click to browse'}</div>
          <div className="mono text-[10px] uppercase tracking-wider text-slate-500">
            {file ? `${(file.size / 1048576).toFixed(1)} MB` : 'MP4 · AVI · MOV · MKV · WEBM · MPG — up to 1 GB'}
          </div>
          <input ref={input} type="file" accept={ACCEPT} className="hidden" onChange={(e) => pick(e.target.files?.[0])} />
        </div>
        <Field label="Camera name"><input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} placeholder="Platform 3 CCTV (recorded)" /></Field>
        <Field label="Address / landmark"><input className={inputCls} value={address} onChange={(e) => setAddress(e.target.value)} /></Field>
        <Field label="Analyse for">
          <div className="flex flex-wrap gap-2">
            {DETECTION_KEYS.map((k) => {
              const m = INCIDENT_TYPES[k]
              const on = dets.includes(k)
              return (
                <button key={k} type="button" onClick={() => toggle(k)}
                  className={`mono flex items-center gap-1.5 border px-2.5 py-1 text-[11px] uppercase tracking-wide ${on ? 'text-white' : 'border-slate-700 text-slate-500'}`}
                  style={on ? { background: m.color, borderColor: m.color } : undefined}>
                  {m.icon} {m.short}
                </button>
              )
            })}
          </div>
        </Field>
        <p className="text-xs text-slate-400">
          The recording plays in a loop and is analysed by the detector in real time, just like a live RTSP camera.
          Draw restricted or water zones afterwards under <b>Zones</b> to enable intrusion / water alerts.
        </p>
      </div>
      <div className="space-y-4">
        <Field label={`Where was it recorded? Click the map (${latlonText(location)})`}>
          <MapPicker value={location} center={center} onChange={setLocation} height={300} />
        </Field>
        {progress !== null && (
          <div>
            <div className="mono mb-1 flex justify-between text-[10px] uppercase text-slate-400"><span>Uploading</span><span>{Math.round(progress * 100)}%</span></div>
            <div className="h-2 bg-slate-800"><div className="h-full bg-[var(--color-signal)] transition-all" style={{ width: `${progress * 100}%` }} /></div>
          </div>
        )}
        {error && <div className="text-sm text-[var(--color-alert)]">{error}</div>}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={submit} disabled={!file || !name.trim() || !dets.length || progress !== null}>
            <Upload size={15} /> Import &amp; analyse
          </Button>
        </div>
      </div>
    </div>
  )
}
