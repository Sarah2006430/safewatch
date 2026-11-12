import { useEffect, useState } from 'react'
import { VideoOff } from 'lucide-react'
import { streamUrl, thumbUrl } from '../lib/api'

/** Live annotated MJPEG feed from the detection service. */
export default function LiveStream({ cameraId, className = '' }) {
  const [failed, setFailed] = useState(false)
  const [nonce, setNonce] = useState(0)

  if (failed) {
    return (
      <div className={`flex flex-col items-center justify-center gap-2 bg-black text-xs text-slate-500 ${className}`}>
        <VideoOff size={22} />
        <span className="mono uppercase tracking-wider">No signal from detector</span>
        <button className="mono text-[11px] uppercase text-[var(--color-signal)] hover:underline" onClick={() => { setFailed(false); setNonce(nonce + 1) }}>Retry link</button>
      </div>
    )
  }
  return (
    <img
      key={nonce}
      src={`${streamUrl(cameraId)}?n=${nonce}`}
      alt="Live camera"
      className={`bg-black object-contain ${className}`}
      onError={() => setFailed(true)}
    />
  )
}

/** Low-cost live thumbnail: polls the latest annotated frame instead of holding a stream open. */
export function CameraThumb({ cameraId, interval = 1000, className = '' }) {
  // Each new frame is preloaded off-screen and only swapped in once it has loaded,
  // so a failed request (detector restarting, busy CPU) keeps the last good frame and retries.
  const [src, setSrc] = useState(null)
  useEffect(() => {
    let alive = true
    let busy = false
    const tick = () => {
      if (busy) return
      busy = true
      const url = thumbUrl(cameraId)
      const img = new Image()
      // Give up on a request that hangs, so one stuck request can never freeze the thumbnail.
      const giveUp = setTimeout(() => { img.onload = img.onerror = null; img.src = ''; busy = false }, 4000)
      img.onload = () => { clearTimeout(giveUp); busy = false; if (alive) setSrc(url) }
      img.onerror = () => { clearTimeout(giveUp); busy = false }
      img.src = url
    }
    tick()
    const t = setInterval(tick, interval)
    return () => { alive = false; clearInterval(t) }
  }, [cameraId, interval])
  return src
    ? <img src={src} alt="" className={`bg-black object-cover ${className}`} />
    : (
      <div className={`flex flex-col items-center justify-center gap-1 bg-black text-white/60 ${className}`}>
        <VideoOff size={16} />
        <span className="mono text-[9px] uppercase tracking-wider">No signal · detector off?</span>
      </div>
    )
}
