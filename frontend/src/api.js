// Small fetch wrapper around the Django REST API.
async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = body.detail || body.error || `Request failed (${res.status})`
    throw new Error(detail)
  }
  return body
}

export const api = {
  // Files
  uploadFile: (formData) =>
    fetch('/api/files', { method: 'POST', body: formData }).then(async (res) => {
      const body = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(body.detail || body.code || 'Upload failed')
      return body
    }),
  listFiles: () => request('/api/files/list'),

  // Runs
  startRun: (internal_file_id, external_file_id) =>
    request('/api/reconciliation-runs', {
      method: 'POST',
      body: JSON.stringify({ internal_file_id, external_file_id }),
    }),
  listRuns: () => request('/api/reconciliation-runs/list'),
  dashboard: () => request('/api/reconciliation-runs/dashboard'),
  runResults: (runId, status) =>
    request(`/api/reconciliation-runs/${runId}/results${status ? `?status=${status}` : ''}`),

  // Results
  resultDetail: (resultId) => request(`/api/reconciliation-results/${resultId}`),
  manualMatch: (resultId, { external_transaction_id, internal_transaction_id, reason }) =>
    request(`/api/reconciliation-results/${resultId}/match`, {
      method: 'POST',
      body: JSON.stringify({ external_transaction_id, internal_transaction_id, reason }),
    }),
  acceptUnmatched: (resultId, reason) =>
    request(`/api/reconciliation-results/${resultId}/accept`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
}

export function formatMoney(v) {
  if (v === null || v === undefined) return '—'
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  return n.toLocaleString(undefined, { maximumFractionDigits: 6 })
}

export function formatTime(v) {
  if (!v) return '—'
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return String(v)
  return d.toUTCString().slice(5, 22) + 'Z'
}

export function errorMessage(err) {
  return err && err.message ? err.message : String(err)
}