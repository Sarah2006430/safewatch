import { useState } from 'react'
import { Maximize2 } from 'lucide-react'
import LiveStream, { CameraThumb } from '../components/LiveStream'
import { Empty, Modal } from '../components/ui'
import { useData } from '../context/DataContext'
import { INCIDENT_TYPES, OPEN_STATUSES } from '../lib/constants'

export default function LiveWall() {
  const { cameras, incidents } = useData()
  const [focus, setFocus] = useState(null)
  const active = cameras.filter((c) => c.is_active)
  const alertsFor = (id) => incidents.filter((i) => i.camera_id === id && OPEN_STATUSES.includes(i.status))

  return (
    <div className="scroll-thin h-full overflow-y-auto bg-black p-3">
      {!active.length && <Empty>No active cameras. Add one under Cameras.</Empty>}
      <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
        {active.map((c) => {
          const alerts = alertsFor(c.id)
          const hot = alerts.some((a) => a.status === 'pending')
          return (
            <div key={c.id} className={`border panel ${hot ? 'border-[var(--color-alert)] shadow-[0_0_30px_rgba(255,59,48,.25)]' : 'border-slate-800'}`}>
              {hot && <div className="hazard h-[4px]" />}
              <div className={`hud scan relative aspect-video ${hot ? 'hud-alert' : ''}`}>
                {/* Tiles poll snapshots: an MJPEG stream per tile would use up the browser's
                    6-connections-per-host limit and starve every other request to the detector. */}
                <CameraThumb cameraId={c.id} interval={250} className="h-full w-full" />
                <button onClick={() => setFocus(c)} className="absolute bottom-3 right-3 z-10 border border-white/20 bg-black/70 p-1.5 text-white hover:bg-black"><Maximize2 size={14} /></button>
              </div>
              <div className="flex items-center gap-2 border-t border-slate-800 px-3 py-2">
                <span className={`h-2 w-2 ${c.status === 'online' ? 'bg-[var(--color-ok)] shadow-[0_0_8px_var(--color-ok)]' : 'blink bg-[var(--color-alert)]'}`} />
                <span className="mono text-[10px] text-slate-500">CAM{String(c.id).padStart(2, '0')}</span>
                <span className="flex-1 truncate text-sm font-medium">{c.name}</span>
                {Object.entries(alerts.reduce((acc, a) => ({ ...acc, [a.type]: (acc[a.type] || 0) + 1 }), {})).map(([type, n]) => {
                  const m = INCIDENT_TYPES[type]
                  return (
                    <span key={type} title={`${n} open ${m?.label} incident(s)`} className="mono flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-bold text-black" style={{ background: m?.color }}>
                      {m?.icon}{m?.short}{n > 1 && ` ×${n}`}
                    </span>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
      {focus && (
        <Modal title={focus.name} onClose={() => setFocus(null)} wide>
          <div className="hud scan relative"><LiveStream cameraId={focus.id} className="aspect-video w-full" /></div>
        </Modal>
      )}
    </div>
  )
}
