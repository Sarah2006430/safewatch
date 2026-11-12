let ctx

/** Short two-tone siren using the Web Audio API (no audio files needed). */
export function playAlarm(critical = false) {
  try {
    ctx = ctx || new (window.AudioContext || window.webkitAudioContext)()
    const now = ctx.currentTime
    const tones = critical ? [880, 660, 880, 660] : [880, 660]
    tones.forEach((f, i) => {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.type = 'square'
      osc.frequency.value = f
      gain.gain.setValueAtTime(0.08, now + i * 0.22)
      gain.gain.exponentialRampToValueAtTime(0.0001, now + i * 0.22 + 0.2)
      osc.connect(gain).connect(ctx.destination)
      osc.start(now + i * 0.22)
      osc.stop(now + i * 0.22 + 0.21)
    })
  } catch { /* audio blocked until user interacts */ }
}

export function notifyBrowser(title, body) {
  try {
    if (!('Notification' in window)) return
    if (Notification.permission === 'granted') new Notification(title, { body })
    else if (Notification.permission === 'default') Notification.requestPermission()
  } catch { /* ignore */ }
}
