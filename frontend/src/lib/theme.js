// Light (default) / dark theme, remembered per browser.
const KEY = 'safewatch_theme'

export function getTheme() {
  try { return localStorage.getItem(KEY) === 'dark' ? 'dark' : 'light' } catch { return 'light' }
}

export function applyTheme(theme) {
  document.documentElement.dataset.theme = theme
  try { localStorage.setItem(KEY, theme) } catch { /* storage unavailable */ }
  window.dispatchEvent(new CustomEvent('theme:change', { detail: theme }))
}
