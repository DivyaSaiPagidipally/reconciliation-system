const STATUS_LABELS = {
  MATCHED: 'Matched',
  DISCREPANCY: 'Discrepancy',
  UNMATCHED_INTERNAL: 'Internal only',
  UNMATCHED_EXTERNAL: 'External only',
  MANUALLY_MATCHED: 'Manually matched',
  ACCEPTED_UNMATCHED: 'Accepted unmatched',
}

export function StatusBadge({ status }) {
  const cls = String(status || '').toLowerCase()
  return <span className={`badge ${cls}`}>{STATUS_LABELS[status] || status}</span>
}

export const MATCH_METHODS = {
  ID: 'Exact ID',
  FUZZY: 'Fuzzy',
  MANUAL: 'Manual',
  NONE: '—',
}