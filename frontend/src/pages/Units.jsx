import { useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import IncidentMap, { mapCenter } from '../components/IncidentMap'
import MapPicker from '../components/MapPicker'
import { Button, Card, Field, inputCls, Modal, PageHeader } from '../components/ui'
import { useData } from '../context/DataContext'
import { api } from '../lib/api'
import { AGENCIES, UNIT_STATUS_STYLES } from '../lib/constants'
import { latlonText, timeAgo } from '../lib/format'

const STATUSES = ['available', 'dispatched', 'en_route', 'on_scene', 'offline']

function UnitForm({ center, onClose }) {
  const [f, setF] = useState({ name: '', agency: 'police', contact: '', location: null })
  const [error, setError] = useState('')
  const save = async () => {
    if (!f.location) return setError('Click the map to set the unit base location')
    try {
      await api('/api/units', { method: 'POST', body: { name: f.name, agency: f.agency, contact: f.contact, lat: f.location.lat, lon: f.location.lon } })
      onClose()
    } catch (e) { setError(e.message) }
  }
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <Field label="Unit name"><input className={inputCls} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Ambulance A4" /></Field>
        <Field label="Agency">
          <select className={inputCls} value={f.agency} onChange={(e) => setF({ ...f, agency: e.target.value })}>
            {Object.entries(AGENCIES).map(([k, a]) => <option key={k} value={k}>{a.label}</option>)}
          </select>
        </Field>
      </div>
      <Field label="Contact (radio / phone)"><input className={inputCls} value={f.contact} onChange={(e) => setF({ ...f, contact: e.target.value })} /></Field>
      <Field label={`Location — ${latlonText(f.location)}`}><MapPicker value={f.location} center={center} onChange={(location) => setF({ ...f, location })} /></Field>
      {error && <div className="text-sm text-[var(--color-alert)]">{error}</div>}
      <div className="flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button disabled={!f.name} onClick={save}>Add unit</Button>
      </div>
    </div>
  )
}

export default function Units() {
  const { units, cameras, incidents } = useData()
  const [adding, setAdding] = useState(false)
  const setStatus = (u, status) => api(`/api/units/${u.id}`, { method: 'PATCH', body: { status } })
  const remove = async (u) => { if (confirm(`Remove ${u.name}?`)) await api(`/api/units/${u.id}`, { method: 'DELETE' }) }

  return (
    <div className="flex h-full flex-col lg:flex-row">
      <div className="scroll-thin w-full overflow-y-auto p-4 lg:w-[32rem] lg:shrink-0">
        <PageHeader kicker="Police · medical · fire · rescue" title="Response units">
          <Button onClick={() => setAdding(true)}><Plus size={16} /> Add unit</Button>
        </PageHeader>
        {Object.entries(AGENCIES).map(([k, a]) => {
          const list = units.filter((u) => u.agency === k)
          return (
            <Card key={k} className="mb-3 border-l-[3px] p-3" style={{ borderLeftColor: a.color }}>
              <div className="mb-2 flex items-center gap-2">
                <span style={{ color: a.color }}>{a.icon}</span>
                <span className="num text-lg uppercase">{a.label}</span>
                <span className="mono ml-auto text-[10px] uppercase text-slate-500">{list.filter((u) => u.status === 'available').length}/{list.length} ready</span>
              </div>
              {list.map((u) => (
                <div key={u.id} className="flex items-center gap-2 border-t border-slate-800 py-2 text-sm first:border-0">
                  <div className="min-w-0 flex-1">
                    <div className="truncate">{u.name}</div>
                    <div className="text-[11px] text-slate-500">{u.contact && `TEL ${u.contact} · `}updated {timeAgo(u.updated_at)}</div>
                  </div>
                  <select value={u.status} onChange={(e) => setStatus(u, e.target.value)}
                          className={`mono border border-slate-700 bg-slate-950 px-2 py-1 text-[11px] uppercase ${UNIT_STATUS_STYLES[u.status]}`}>
                    {STATUSES.map((s) => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
                  </select>
                  <button className="text-slate-500 hover:text-[var(--color-alert)]" onClick={() => remove(u)}><Trash2 size={14} /></button>
                </div>
              ))}
            </Card>
          )
        })}
      </div>
      <div className="min-h-[300px] flex-1 border-l border-slate-800">
        <IncidentMap incidents={incidents} cameras={cameras} units={units} />
      </div>
      {adding && <Modal title="Add response unit" onClose={() => setAdding(false)}><UnitForm center={mapCenter(cameras, units)} onClose={() => setAdding(false)} /></Modal>}
    </div>
  )
}
