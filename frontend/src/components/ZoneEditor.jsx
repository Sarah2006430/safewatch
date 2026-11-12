import { useEffect, useState } from 'react'
import { RefreshCw, Trash2, Undo2 } from 'lucide-react'
import { api, snapshotUrl } from '../lib/api'
import { Button, Field, inputCls } from './ui'

/**
 * Draw restricted / water zones on a still frame from the camera.
 * Points are stored normalised (0..1) so they work at any resolution.
 */
export default function ZoneEditor({ camera, onSaved }) {
  const [src, setSrc] = useState(snapshotUrl(camera.id))
  const [imgOk, setImgOk] = useState(true)
  const [points, setPoints] = useState([])
  const [form, setForm] = useState({ name: '', kind: 'restricted', dwell_seconds: 2 })
  const [error, setError] = useState('')

  useEffect(() => { setPoints([]) }, [camera.id])

  const click = (e) => {
    const r = e.currentTarget.getBoundingClientRect()
    const x = +((e.clientX - r.left) / r.width).toFixed(4)
    const y = +((e.clientY - r.top) / r.height).toFixed(4)
    setPoints((p) => [...p, [x, y]])
  }

  const save = async () => {
    setError('')
    try {
      await api(`/api/cameras/${camera.id}/zones`, {
        method: 'POST',
        body: { ...form, dwell_seconds: Number(form.dwell_seconds), roi: points },
      })
      setPoints([])
      setForm({ ...form, name: '' })
      onSaved?.()
    } catch (e) { setError(e.message) }
  }

  const remove = async (id) => {
    await api(`/api/zones/${id}`, { method: 'DELETE' })
    onSaved?.()
  }

  const poly = (pts) => pts.map(([x, y]) => `${x * 100},${y * 100}`).join(' ')

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_16rem]">
      <div>
        <div className="relative aspect-video cursor-crosshair select-none overflow-hidden bg-black ring-1 ring-slate-700" onClick={click}>
          {imgOk
            ? <img src={src} alt="" className="absolute inset-0 h-full w-full object-fill" onError={() => setImgOk(false)} draggable={false} />
            : <div className="absolute inset-0 flex items-center justify-center p-6 text-center text-xs text-slate-500">No frame from the detector yet — start the detection service, or draw on the blank canvas.</div>}
          <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 h-full w-full">
            {camera.zones.map((z) => (
              <polygon key={z.id} points={poly(z.roi)} fill={z.kind === 'restricted' ? 'rgba(232,197,71,.22)' : 'rgba(37,184,232,.25)'}
                       stroke={z.kind === 'restricted' ? '#e8c547' : '#25b8e8'} strokeWidth="0.4" />
            ))}
            {points.length > 0 && (
              <polygon points={poly(points)} fill="rgba(255,176,32,.2)" stroke="#ffb020" strokeWidth="0.5" strokeDasharray="1.5 1" />
            )}
            {points.map(([x, y], i) => <circle key={i} cx={x * 100} cy={y * 100} r="0.9" fill="#ffb020" />)}
          </svg>
        </div>
        <div className="mt-2 flex gap-2 text-xs">
          <Button variant="ghost" onClick={() => setPoints((p) => p.slice(0, -1))} disabled={!points.length}><Undo2 size={14} /> Undo point</Button>
          <Button variant="ghost" onClick={() => setPoints([])} disabled={!points.length}>Clear</Button>
          <Button variant="ghost" onClick={() => { setImgOk(true); setSrc(snapshotUrl(camera.id)) }}><RefreshCw size={14} /> Refresh frame</Button>
          <span className="ml-auto self-center text-slate-500">Click to add polygon points ({points.length})</span>
        </div>
      </div>

      <div className="space-y-3">
        <Field label="Zone name"><input className={inputCls} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Rail track / Pool" /></Field>
        <Field label="Zone type">
          <select className={inputCls} value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
            <option value="restricted">Restricted area (intrusion)</option>
            <option value="water">Water body (distress)</option>
          </select>
        </Field>
        <Field label="Dwell time before alert (s)">
          <input type="number" min="0" step="0.5" className={inputCls} value={form.dwell_seconds} onChange={(e) => setForm({ ...form, dwell_seconds: e.target.value })} />
        </Field>
        {error && <div className="text-xs text-red-400">{error}</div>}
        <Button className="w-full" disabled={points.length < 3 || !form.name} onClick={save}>Save zone</Button>

        <div className="border-t border-slate-800 pt-3">
          <div className="mb-2 text-xs font-semibold uppercase text-slate-500">Existing zones</div>
          {!camera.zones.length && <div className="text-xs text-slate-500">None yet</div>}
          {camera.zones.map((z) => (
            <div key={z.id} className="mb-1 flex items-center gap-2 border border-slate-800 bg-slate-950 px-2 py-1.5 text-sm">
              <span className="mono text-[9px] font-bold uppercase" style={{ color: z.kind === 'restricted' ? '#e8c547' : '#25b8e8' }}>{z.kind === 'restricted' ? 'RSTR' : 'WATR'}</span>
              <span className="flex-1 truncate">{z.name}</span>
              <span className="text-xs text-slate-500">{z.dwell_seconds}s</span>
              <button className="text-slate-500 hover:text-red-400" onClick={() => remove(z.id)}><Trash2 size={14} /></button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
