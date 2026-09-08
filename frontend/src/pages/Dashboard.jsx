import { useEffect, useState } from 'react'
import { api, errorMessage, formatMoney, formatTime } from '../api'
import { StatusBadge, MATCH_METHODS } from '../components/StatusBadge'

const SOURCE_LABEL = { INTERNAL: 'Internal ledger', EXTERNAL: 'External statement' }

export default function Dashboard({ navigate, embeddedRunId }) {
  const [files, setFiles] = useState([])
  const [runs, setRuns] = useState([])
  const [latestRunId, setLatestRunId] = useState(null)
  const [unresolved, setUnresolved] = useState([])
  const [summary, setSummary] = useState(null)

  const [internalFile, setInternalFile] = useState(null)
  const [externalFile, setExternalFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [starting, setStarting] = useState(false)
  const [message, setMessage] = useState({ type: '', text: '' })

  const refresh = async () => {
    try {
      const [f, r, d] = await Promise.all([api.listFiles(), api.listRuns(), api.dashboard()])
      setFiles(f)
      setRuns(r)
      setLatestRunId(d.latest_run ? d.latest_run.id : null)
      setSummary(d.latest_run ? d.latest_run.summary : null)
      setUnresolved(d.unresolved || [])
      if (embeddedRunId) setLatestRunId(embeddedRunId)
    } catch (e) {
      setMessage({ type: 'error', text: errorMessage(e) })
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  const onUpload = async (source) => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.csv,text/csv'
    input.onchange = async () => {
      const file = input.files[0]
      if (!file) return
      setUploading(true)
      setMessage({ type: '', text: '' })
      const fd = new FormData()
      fd.append('file', file)
      fd.append('source', source)
      try {
        const body = await api.uploadFile(fd)
        setMessage({ type: 'success', text: `${SOURCE_LABEL[source]} imported (${body.file.record_count} records).` })
        await refresh()
      } catch (e) {
        setMessage({ type: 'error', text: errorMessage(e) })
      } finally {
        setUploading(false)
      }
    }
    input.click()
  }

  const onStart = async () => {
    if (!internalFile || !externalFile) return
    setStarting(true)
    setMessage({ type: '', text: '' })
    try {
      const run = await api.startRun(internalFile, externalFile)
      setMessage({ type: 'success', text: `Reconciliation run #${run.id} completed.` })
      setInternalFile(null)
      setExternalFile(null)
      await refresh()
    } catch (e) {
      setMessage({ type: 'error', text: errorMessage(e) })
    } finally {
      setStarting(false)
    }
  }

  const latestRun = runs.find((r) => r.id === latestRunId) || runs[0]
  const summaryCounts = summary
    ? [
        { label: 'Matched', value: summary.matched, cls: 'ok' },
        { label: 'Discrepancy', value: summary.discrepancies, cls: 'warn' },
        { label: 'Internal missing', value: summary.unmatched_internal, cls: 'err' },
        { label: 'External missing', value: summary.unmatched_external, cls: 'err' },
        { label: 'Cancelled', value: summary.cancelled, cls: '' },
        { label: 'Manually resolved', value: (summary.manually_matched || 0) + (summary.accepted_unmatched || 0), cls: '' },
      ]
    : []

  return (
    <div>
      {message.text && (
        <div className={`alert ${message.type || 'info'}`} role="status">
          {message.text}
        </div>
      )}

      {/* Upload + start run */}
      <div className="panel">
        <h2>Run reconciliation</h2>
        <div className="grid grid-3" style={{ alignItems: 'end' }}>
          <div className="field" style={{ margin: 0 }}>
            <label>Internal ledger CSV</label>
            <select value={internalFile || ''} onChange={(e) => setInternalFile(Number(e.target.value))}>
              <option value="">Select an imported file…</option>
              {files
                .filter((f) => f.source === 'INTERNAL')
                .map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.filename} ({f.record_count} rec)
                  </option>
                ))}
            </select>
            <div style={{ marginTop: 8 }}>
              <button className="btn secondary small" onClick={() => onUpload('INTERNAL')} disabled={uploading}>
                {uploading ? 'Uploading…' : 'Upload internal CSV'}
              </button>
            </div>
          </div>

          <div className="field" style={{ margin: 0 }}>
            <label>External statement CSV</label>
            <select value={externalFile || ''} onChange={(e) => setExternalFile(Number(e.target.value))}>
              <option value="">Select an imported file…</option>
              {files
                .filter((f) => f.source === 'EXTERNAL')
                .map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.filename} ({f.record_count} rec)
                  </option>
                ))}
            </select>
            <div style={{ marginTop: 8 }}>
              <button className="btn secondary small" onClick={() => onUpload('EXTERNAL')} disabled={uploading}>
                {uploading ? 'Uploading…' : 'Upload external CSV'}
              </button>
            </div>
          </div>

          <div className="field" style={{ margin: 0 }}>
            <label>&nbsp;</label>
            <button className="btn" onClick={onStart} disabled={!internalFile || !externalFile || starting}>
              {starting ? 'Running…' : '▶ Start New Run'}
            </button>
          </div>
        </div>
        <p className="muted" style={{ marginTop: 10, fontSize: 13 }}>
          Files are deduplicated by SHA-256; corrected uploads create transaction version history.
        </p>
      </div>

      {/* Summary */}
      {summaryCounts.length > 0 && (
        <div className="panel">
          <div className="row">
            <h2 style={{ margin: 0 }}>Last Run</h2>
            {latestRun && (
              <span className="muted" style={{ fontSize: 13 }}>
                Run #{latestRun.id} · {latestRun.completed_at ? formatTime(latestRun.completed_at) : '—'}
              </span>
            )}
            <div className="spacer" />
            <button className="btn ghost small" onClick={() => navigate({ name: 'results', runId: latestRunId })}>
              View all results →
            </button>
          </div>
          <div className="grid grid-4" style={{ marginTop: 8 }}>
            {summaryCounts.map((s) => (
              <div key={s.label} className={`stat ${s.cls}`}>
                <div className="num">{s.value}</div>
                <div className="label">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Unresolved transactions */}
      <div className="panel">
        <h2>Unresolved transactions</h2>
        {unresolved.length === 0 ? (
          <p className="muted">Nothing to resolve — everything matches. 🎉</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Status</th>
                <th>Internal ID</th>
                <th>External ID</th>
                <th>Instrument</th>
                <th>Amount</th>
                <th>Time</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {unresolved.map((r) => (
                <tr key={r.id}>
                  <td><StatusBadge status={r.status} /></td>
                  <td className="mono">{r.internal_transaction?.source_transaction_id || '—'}</td>
                  <td className="mono">{r.external_transaction?.source_transaction_id || '—'}</td>
                  <td>{r.internal_transaction?.instrument || r.external_transaction?.instrument || '—'}</td>
                  <td>{formatMoney(r.internal_transaction?.amount ?? r.external_transaction?.amount)}</td>
                  <td>{formatTime(r.internal_transaction?.transaction_time ?? r.external_transaction?.transaction_time)}</td>
                  <td>
                    <button className="btn ghost small" onClick={() => navigate({ name: 'detail', resultId: r.id })}>
                      View
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Full results of latest run */}
      {latestRun && <LatestRunResults key={latestRun.id} run={latestRun} navigate={navigate} />}
    </div>
  )
}

function LatestRunResults({ run, navigate }) {
  const [rows, setRows] = useState(null)
  const [filter, setFilter] = useState('')
  const [error, setError] = useState('')
  const FILTERS = [
    ['', 'All'],
    ['DISCREPANCY', 'Discrepancies'],
    ['UNMATCHED_INTERNAL', 'Unmatched internal'],
    ['UNMATCHED_EXTERNAL', 'Unmatched external'],
    ['MATCHED', 'Matched'],
    ['MANUALLY_RESOLVED', 'Manually resolved'],
  ]

  useEffect(() => {
    let cancelled = false
    api
      .runResults(run.id, filter)
      .then((data) => !cancelled && setRows(data))
      .catch((e) => !cancelled && setError(errorMessage(e)))
    return () => {
      cancelled = true
    }
  }, [run.id, filter])

  return (
    <div className="panel">
      <h2>Run #{run.id} — All results</h2>
      <div className="filters">
        {FILTERS.map(([val, label]) => (
          <button key={val} className={filter === val ? 'active' : ''} onClick={() => setFilter(val)}>
            {label}
          </button>
        ))}
      </div>
      {error && <div className="alert error">{error}</div>}
      {rows === null ? (
        <p className="muted">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="muted">No results for this filter.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Status</th>
              <th>Match</th>
              <th>Internal ID</th>
              <th>External ID</th>
              <th>Instrument</th>
              <th>Amount</th>
              <th>Time</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td><StatusBadge status={r.status} /></td>
                <td className="muted">{MATCH_METHODS[r.match_method] || r.match_method}</td>
                <td className="mono">{r.internal_transaction?.source_transaction_id || '—'}</td>
                <td className="mono">{r.external_transaction?.source_transaction_id || '—'}</td>
                <td>{r.internal_transaction?.instrument || r.external_transaction?.instrument || '—'}</td>
                <td>
                  {r.internal_transaction?.amount !== undefined && r.external_transaction?.amount !== undefined
                    ? `${formatMoney(r.internal_transaction.amount)} / ${formatMoney(r.external_transaction.amount)}`
                    : formatMoney(r.internal_transaction?.amount ?? r.external_transaction?.amount)}
                </td>
                <td>{formatTime(r.internal_transaction?.transaction_time ?? r.external_transaction?.transaction_time)}</td>
                <td>
                  <button className="btn ghost small" onClick={() => navigate({ name: 'detail', resultId: r.id })}>
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}