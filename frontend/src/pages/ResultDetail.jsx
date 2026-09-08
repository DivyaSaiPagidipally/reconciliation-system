import { useEffect, useState } from 'react'
import { api, errorMessage, formatMoney, formatTime } from '../api'
import { StatusBadge } from '../components/StatusBadge'

const FIELD_LABELS = {
  instrument: 'Instrument',
  side: 'Side',
  quantity: 'Quantity',
  price: 'Price',
  amount: 'Amount',
  transaction_time: 'Time',
}

export default function ResultDetail({ resultId, navigate }) {
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState({ type: '', text: '' })

  const load = async () => {
    try {
      setResult(await api.resultDetail(resultId))
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  useEffect(() => {
    load()
  }, [resultId])

  if (error) return <div className="alert error">{error}</div>
  if (!result) return <p className="muted">Loading…</p>

  const { status: status, internal_transaction: itx, external_transaction: etx, differences, reason } = result
  const canMatch =
    status === 'UNMATCHED_INTERNAL' || status === 'UNMATCHED_EXTERNAL' || status === 'DISCREPANCY' || status === 'MATCHED'
  const canAccept = status === 'UNMATCHED_INTERNAL' || status === 'UNMATCHED_EXTERNAL'

  return (
    <div>
      {message.text && <div className={`alert ${message.type}`}>{message.text}</div>}
      <div className="panel">
        <div className="row">
          <h2>
            Transaction result <span className="dim">#{result.id}</span>
          </h2>
          <StatusBadge status={status} />
          <span className="muted" style={{ fontSize: 13 }}>
            {status === 'DISCREPANCY' && 'Details below show what differs and by how much.'}
          </span>
          {reason && <em className="muted">Reason: {reason}</em>}
        </div>

        <div className="detail-grid" style={{ marginTop: 14 }}>
          <div className="detail-col">
            <h3>📒 Internal ledger</h3>
            <TxTable tx={itx} />
          </div>
          <div className="detail-col">
            <h3>📄 External statement</h3>
            <TxTable tx={etx} />
          </div>
        </div>

        {differences?.length > 0 && (
          <>
            <h3 style={{ marginTop: 18 }}>Differences</h3>
            <table>
              <thead>
                <tr>
                  <th>Field</th>
                  <th>Internal</th>
                  <th>External</th>
                  <th>Difference</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {differences.map((d) => (
                  <tr key={d.field_name}>
                    <td>{FIELD_LABELS[d.field_name] || d.field_name}</td>
                    <td className="mono">{d.internal_value}</td>
                    <td className="mono">{d.external_value}</td>
                    <td className={`mono ${d.difference && !d.within_tolerance ? 'bad-text' : ''}`}>{d.difference || '—'}</td>
                    <td>
                      {d.within_tolerance ? <span className="ok-text">✓</span> : <span className="bad-text">✗</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {(canMatch || canAccept) && (
          <div className="row" style={{ marginTop: 16 }}>
            <button className="btn" onClick={() => setModal('match')}>
              Match with…
            </button>
            <button className="btn secondary" onClick={() => setModal('accept')}>
              Accept as unmatched
            </button>
            <p className="muted" style={{ margin: 0, fontSize: 13 }}>
              Decisions are persisted and automatically applied to future runs.
            </p>
          </div>
        )}
      </div>

      {modal && (
        <ResolutionModal
          modal={modal}
          result={result}
          onClose={() => setModal(null)}
          onDone={(msg) => {
            setModal(null)
            setMessage({ type: 'success', text: msg })
            load()
          }}
        />
      )}
    </div>
  )
}

function TxTable({ tx }) {
  if (!tx)
    return (
      <p className="muted" style={{ padding: 8 }}>
        No counterpart on this side.
      </p>
    )
  const rows = [
    ['ID', tx.source_transaction_id],
    ['Time', formatTime(tx.transaction_time)],
    ['Instrument', tx.instrument],
    ['Side', tx.side],
    ['Quantity', formatMoney(tx.quantity)],
    ['Price', formatMoney(tx.price)],
    ['Amount', formatMoney(tx.amount)],
    ['Status', tx.status],
  ]
  return (
    <table>
      <tbody>
        {rows.map(([k, v]) => (
          <tr key={k}>
            <td className="muted">{k}</td>
            <td className="mono">{v}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function ResolutionModal({ modal, result, onClose, onDone }) {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [reason, setReason] = useState('')
  const [extTarget, setExtTarget] = useState('')
  const [intTarget, setIntTarget] = useState('')
  const [potentialMatches, setPotentialMatches] = useState([])

  // For "match", show candidate counterparts from the other side.
  useEffect(() => {
    if (modal !== 'match') return
    api
      .dashboard()
      .then((d) => {
        const desiredStatus =
          result.status === 'UNMATCHED_INTERNAL'
            ? 'UNMATCHED_EXTERNAL'
            : result.status === 'UNMATCHED_EXTERNAL'
              ? 'UNMATCHED_INTERNAL'
              : ''
        const candidates = (d.unresolved || []).filter((r) => !desiredStatus || r.status === desiredStatus)
        setPotentialMatches(candidates)
      })
      .catch((e) => setErr(errorMessage(e)))
  }, [modal])

  const doMatch = async () => {
    setBusy(true)
    setErr('')
    try {
      // The current record's side is fixed; the user picks the counterpart
      // from the other side (either via radio button or by typing its id).
      let payload = {}
      if (result.status === 'UNMATCHED_INTERNAL') {
        payload = { external_transaction_id: Number(extTarget) }
      } else if (result.status === 'UNMATCHED_EXTERNAL') {
        payload = { internal_transaction_id: Number(intTarget) }
      } else {
        // DISCREPANCY/MATCHED re-link: pick whichever side was provided.
        payload = { external_transaction_id: Number(extTarget), internal_transaction_id: Number(intTarget) }
      }
      // Send only the populated counterpart.
      const clean = Object.fromEntries(Object.entries(payload).filter(([, v]) => v))
      await api.manualMatch(result.id, { ...clean, reason })
      onDone('Record matched and persisted.')
    } catch (e) {
      setErr(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const doAccept = async () => {
    setBusy(true)
    setErr('')
    try {
      await api.acceptUnmatched(result.id, reason)
      onDone('Accepted as unmatched. This decision will persist on future runs.')
    } catch (e) {
      setErr(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const isMatch = modal === 'match'
  const isAccept = modal === 'accept'

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>{isMatch ? 'Manually match this transaction' : 'Accept as unmatched'}</h3>
        {err && <div className="alert error">{err}</div>}

        {isMatch && result.status === 'UNMATCHED_INTERNAL' && (
          <>
            <p className="muted">
              Current record missing a counterpart on the external side. Pick one:
            </p>
            <CandidatesList candidates={potentialMatches.filter((r) => r.external_transaction)} choose={setExtTarget} chosen={extTarget} side="external" />
          </>
        )}
        {isMatch && result.status === 'UNMATCHED_EXTERNAL' && (
          <>
            <p className="muted">
              Current record missing a counterpart on the internal side. Pick one:
            </p>
            <CandidatesList candidates={potentialMatches.filter((r) => r.internal_transaction)} choose={setIntTarget} chosen={intTarget} side="internal" />
          </>
        )}
        {isMatch && result.status !== 'UNMATCHED_INTERNAL' && result.status !== 'UNMATCHED_EXTERNAL' && (
          <p className="muted">
            This result already has both sides. You can re-link by entering the counterpart{' '}
            <span className="mono">transaction id</span> below.
          </p>
        )}

        <div className="field" style={{ marginTop: 12 }}>
          <label>Counterpart transaction id (optional for re-linking)</label>
          <input
            type="number"
            placeholder="e.g. 23"
            value={extTarget || intTarget}
            onChange={(e) => {
              if (result.status === 'UNMATCHED_EXTERNAL' || (result.status === 'DISCREPANCY' && !extTarget && result.status !== 'UNMATCHED_INTERNAL')) {
                setIntTarget(e.target.value)
              } else {
                setExtTarget(e.target.value)
              }
            }}
          />
        </div>

        <div className="field">
          <label>Reason (optional)</label>
          <textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder={isAccept ? 'e.g. Late settlement / not present in internal system' : 'e.g. Verified by phone'} />
        </div>

        <div className="row">
          <button className="btn" onClick={isMatch ? doMatch : doAccept} disabled={busy || (isMatch && !extTarget && !intTarget)}>
            {busy ? <span className="spin" /> : null} {isMatch ? 'Match' : 'Accept as unmatched'}
          </button>
          <button className="btn ghost" onClick={onClose}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}

function CandidatesList({ candidates, choose, chosen, side }) {
  if (!candidates.length) return <p className="muted">No candidate counterparts loaded.</p>
  return (
    <div style={{ maxHeight: 200, overflow: 'auto', border: '1px solid var(--border)', borderRadius: 8 }}>
      {candidates.map((r) => {
        const tx = side === 'external' ? r.external_transaction : r.internal_transaction
        if (!tx) return null
        const selected = chosen ? Number(chosen) === tx.id : false
        return (
          <label
            key={tx.id}
            className="row"
            style={{
              padding: '8px 12px',
              borderBottom: '1px solid var(--border)',
              cursor: 'pointer',
              background: selected ? 'rgba(56,189,248,0.12)' : 'transparent',
            }}
          >
            <input
              type="radio"
              name="candidate"
              checked={selected}
              onChange={() => choose(tx.id)}
            />
            <span className="mono">{tx.source_transaction_id}</span>
            <span>{tx.instrument}</span>
            <span>{tx.side}</span>
            <span>{formatMoney(tx.quantity)}</span>
            <span>{formatMoney(tx.amount)}</span>
          </label>
        )
      })}
    </div>
  )
}