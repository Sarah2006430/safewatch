const TOKEN_KEY = 'safewatch_token'

export const DETECTOR_URL = (import.meta.env.VITE_DETECTOR_URL || 'http://127.0.0.1:8100').replace(/\/$/, '')

export function getToken() {
  try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch { /* storage unavailable */ }
}

export async function api(path, { method = 'GET', body } = {}) {
  const headers = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  const res = await fetch(path, { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined })
  if (res.status === 401) {
    setToken(null)
    window.dispatchEvent(new Event('auth:logout'))
  }
  if (!res.ok) {
    let msg = res.statusText
    try {
      const data = await res.json()
      msg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    } catch { /* not json */ }
    throw new Error(msg)
  }
  return res.status === 204 ? null : res.json()
}

export const streamUrl = (cameraId) => `${DETECTOR_URL}/stream/${cameraId}`
export const snapshotUrl = (cameraId) => `${DETECTOR_URL}/snapshot/${cameraId}?t=${Date.now()}`

export const thumbUrl = (cameraId) => `${DETECTOR_URL}/snapshot/${cameraId}?annotated=1&t=${Date.now()}`

/** Multipart upload with progress callback (fetch has no upload progress). */
export function upload(path, formData, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', path)
    const token = getToken()
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    xhr.upload.onprogress = (e) => { if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total) }
    xhr.onload = () => {
      let data = null
      try { data = JSON.parse(xhr.responseText) } catch { /* not json */ }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data)
      else reject(new Error(typeof data?.detail === 'string' ? data.detail : xhr.statusText || 'Upload failed'))
    }
    xhr.onerror = () => reject(new Error('Upload failed: cannot reach the SafeWatch server. Is the "SafeWatch backend" window running? Start it with start-safewatch.bat and try again.'))
    xhr.send(formData)
  })
}
