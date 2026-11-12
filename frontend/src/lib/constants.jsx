import { Ambulance, Ban, Flame, LifeBuoy, PersonStanding, Shield, Truck, Waves, Wind } from 'lucide-react'

// `Icon` is the component (for custom sizes), `icon` a ready 14px element for inline use.
const t = (label, short, Icon, color, agencies) => ({ label, short, Icon, icon: <Icon size={14} strokeWidth={2.2} />, color, agencies })

export const INCIDENT_TYPES = {
  fall: t('Person Fall', 'FALL', PersonStanding, '#ff4d3d', ['medical']),
  fire: t('Fire', 'FIRE', Flame, '#ff7a1a', ['fire', 'medical', 'police']),
  smoke: t('Smoke', 'SMOKE', Wind, '#9aa4ab', ['fire']),
  intrusion: t('Restricted-Area Intrusion', 'INTRUSION', Ban, '#e8c547', ['police']),
  water_distress: t('Distress Near Water', 'WATER', Waves, '#25b8e8', ['rescue', 'medical']),
}

const a = (label, Icon, color) => ({ label, Icon, icon: <Icon size={14} strokeWidth={2.2} />, color })

export const AGENCIES = {
  police: a('Police', Shield, '#4c8dff'),
  medical: a('Medical', Ambulance, '#2fd27a'),
  fire: a('Fire Brigade', Truck, '#ff5a3c'),
  rescue: a('Rescue', LifeBuoy, '#ffb020'),
}

export const STATUS_STYLES = {
  pending: 'text-[var(--color-alert)] border-[var(--color-alert)]/60 bg-[var(--color-alert)]/10',
  verified: 'text-[var(--color-warn)] border-[var(--color-warn)]/60 bg-[var(--color-warn)]/10',
  dispatched: 'text-[var(--color-info)] border-[var(--color-info)]/60 bg-[var(--color-info)]/10',
  resolved: 'text-[var(--color-ok)] border-[var(--color-ok)]/60 bg-[var(--color-ok)]/10',
  false_alarm: 'text-slate-400 border-slate-600 bg-slate-800/40',
}

export const SEVERITY_STYLES = {
  critical: 'bg-[#ff3b30] text-white',
  high: 'bg-[#ff7a1a] text-black',
  medium: 'bg-[var(--color-warn)] text-white',
  low: 'bg-slate-600 text-white',
}

export const UNIT_STATUS_STYLES = {
  available: 'text-[var(--color-ok)]',
  dispatched: 'text-[var(--color-warn)]',
  en_route: 'text-[var(--color-info)]',
  on_scene: 'text-[#e8590c]',
  offline: 'text-slate-500',
}

export const OPEN_STATUSES = ['pending', 'verified', 'dispatched']
export const DETECTION_KEYS = Object.keys(INCIDENT_TYPES)
