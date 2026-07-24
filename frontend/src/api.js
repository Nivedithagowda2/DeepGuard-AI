// api.js
// Small helper module wrapping calls to the FastAPI backend (dashboard.py).
// Change BASE_URL if your backend runs on a different host/port
// (e.g., when porting to the real Arduino UNO Q + Copilot+ PC setup).

const BASE_URL = 'http://localhost:8000'

export async function resetSession() {
  const response = await fetch(`${BASE_URL}/reset_session`, { method: 'POST' })
  return response.json()
}

export async function verifyFrame(blob) {
  const formData = new FormData()
  formData.append('file', blob, 'frame.jpg')

  const response = await fetch(`${BASE_URL}/verify_frame`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    throw new Error(`Frame verification request failed: ${response.status}`)
  }

  return response.json()
}

export async function finalizeVerification() {
  const response = await fetch(`${BASE_URL}/finalize_verification`, {
    method: 'POST',
  })

  if (!response.ok) {
    throw new Error(`Finalize request failed: ${response.status}`)
  }

  return response.json()
}

export async function fetchHistory(limit = 50) {
  const response = await fetch(`${BASE_URL}/history?limit=${limit}`)
  if (!response.ok) {
    throw new Error(`History request failed: ${response.status}`)
  }
  return response.json()
}
