import { useEffect, useState } from 'react'
import { INCIDENT_TYPES } from '../lib/constants'
import { Card } from './ui'

const TYPE_FOR = { falls: 'fall', fire: 'fire', smoke: 'smoke' }

function Rate({ label, value, of, tone }) {
  const pctv = of ? Math.round((value / of) * 100) : 0
  return (
    <div>
      <div className="mono flex justify-between text-[10px] uppercase tracking-wider text-slate-500">
        <span>{label}</span><span>{value}/{of} clips</span>
      </div>
      <div className="mt-1 flex items-center gap-2">
        <div className="h-2 flex-1 bg-slate-800"><div className="h-full" style={{ width: `${pctv}%`, background: tone }} /></div>
        <span className="num w-12 text-right text-xl" style={{ color: tone }}>{pctv}%</span>
      </div>
    </div>
  )
}

/** Clip-level results of detector/benchmark_datasets.py on public research datasets. */
export default function Benchmark() {
  const [data, setData] = useState(null)
  useEffect(() => {
    fetch('/benchmark.json', { cache: 'no-store' }).then((r) => (r.ok ? r.json() : null)).then(setData).catch(() => setData(null))
  }, [])
  if (!data?.results?.length) return null

  return (
    <Card className="mb-4 p-4">
      <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2">
        <div className="label">Validated on public datasets</div>
        <div className="mono text-[10px] text-slate-500">
          pose: {data.models?.pose} · fire/smoke: {data.models?.fire_smoke}
          {data.models?.fire_smoke_metrics && ` (mAP50 ${data.models.fire_smoke_metrics.mAP50})`} · run {data.generated_at?.replace('T', ' ')}
        </div>
      </div>
      <p className="mb-4 max-w-3xl text-xs text-slate-400">
        Every clip below is real recorded footage, run through the same YOLO models and detection logic as the live cameras.
        Detection rate is counted on clips that contain the event; false alarms are counted on control clips that don't.
      </p>
      <div className="grid gap-3 md:grid-cols-3">
        {data.results.map((r) => {
          const meta = INCIDENT_TYPES[TYPE_FOR[r.suite]] || {}
          return (
            <div key={r.suite} className="border border-slate-800 panel p-3">
              <div className="mb-3 flex items-center gap-2">
                <span style={{ color: meta.color }}>{meta.icon}</span>
                <span className="num text-xl uppercase">{r.title}</span>
              </div>
              <div className="space-y-2.5">
                <Rate label="Detected" value={r.detected} of={r.positives} tone="var(--color-ok)" />
                <Rate label="False alarms" value={r.false_alarm_clips} of={r.negatives} tone="var(--color-alert)" />
              </div>
              {r.baseline && (
                <div className="mono mt-3 border-t border-slate-800 pt-2 text-[10px] text-slate-500">
                  Colour heuristic baseline: {r.baseline.detected}/{r.positives} detected · {r.baseline.false_alarm_clips}/{r.negatives} false alarms
                </div>
              )}
              <div className="mono mt-2 text-[10px] leading-relaxed text-slate-500">{r.dataset}</div>
            </div>
          )
        })}
      </div>
    </Card>
  )
}
