import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import React from 'react'
import { create, act } from 'react-test-renderer'
import { createServer } from 'vite'

let server, Dashboard
const originalFetch = globalThis.fetch
const emptyMessage = 'No reconciliation runs yet — upload both files and start one.'

before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
  ;({ default: Dashboard } = await server.ssrLoadModule('/src/pages/Dashboard.jsx'))
})

after(async () => {
  globalThis.fetch = originalFetch
  await server.close()
})

const response = (body) => ({ ok: true, json: async () => body })
const text = (tree) => JSON.stringify(tree.toJSON())

test('empty dashboard offers guidance instead of tables', async () => {
  globalThis.fetch = async (url) => response(url.endsWith('/dashboard') ? { latest_run: null, unresolved: [] } : [])
  let tree
  await act(async () => { tree = create(React.createElement(Dashboard, { navigate: () => {} })) })
  assert.match(text(tree), new RegExp(emptyMessage))
  assert.equal(tree.root.findAllByType('table').length, 0)
  assert.doesNotMatch(text(tree), /Nothing to resolve/)
  assert.match(text(tree), /Start New Run/)
  tree.unmount()
})

test('starting a run replaces empty state with summary and results', async () => {
  const files = [
    { id: 1, source: 'INTERNAL', filename: 'internal.csv', record_count: 1 },
    { id: 2, source: 'EXTERNAL', filename: 'external.csv', record_count: 1 },
  ]
  const run = { id: 7, completed_at: null }
  const result = { id: 9, status: 'DISCREPANCY', match_method: 'EXACT', internal_transaction: { source_transaction_id: 'L-1', amount: '12' } }
  const summary = { matched: 1, discrepancies: 1, unmatched_internal: 0, unmatched_external: 0, cancelled: 0 }
  let started = false
  globalThis.fetch = async (url, options) => {
    if (url === '/api/files/list') return response(files)
    if (url === '/api/reconciliation-runs' && options.method === 'POST') {
      assert.deepEqual(JSON.parse(options.body), { internal_file_id: 1, external_file_id: 2 })
      started = true
      return response(run)
    }
    if (url.endsWith('/list')) return response(started ? [run] : [])
    if (url.endsWith('/dashboard')) return response(started ? { latest_run: { ...run, summary }, unresolved: [result] } : { latest_run: null, unresolved: [] })
    if (url.endsWith('/results')) return response([result])
    throw new Error(`Unexpected URL: ${url}`)
  }
  let tree
  await act(async () => { tree = create(React.createElement(Dashboard, { navigate: () => {} })) })
  assert.match(text(tree), new RegExp(emptyMessage))
  const selects = tree.root.findAllByType('select')
  await act(async () => {
    selects[0].props.onChange({ target: { value: '1' } })
    selects[1].props.onChange({ target: { value: '2' } })
  })
  const start = tree.root.findAllByType('button').find((button) => button.children.includes('▶ Start New Run'))
  await act(async () => { await start.props.onClick() })
  assert.doesNotMatch(text(tree), new RegExp(emptyMessage))
  assert.match(text(tree), /Last Run/)
  assert.match(text(tree), /Matched/)
  assert.ok(tree.root.findAllByType('h2').some((heading) => heading.children.join('') === 'Run #7 — All results'))
  assert.match(text(tree), /L-1/)
  assert.equal(tree.root.findAllByType('table').length, 2)
  tree.unmount()
})

test('loading and failed refresh do not claim there are no runs', async () => {
  let rejectFetch
  globalThis.fetch = () => new Promise((resolve, reject) => { rejectFetch = reject })
  let tree
  await act(async () => { tree = create(React.createElement(Dashboard, { navigate: () => {} })) })
  assert.doesNotMatch(text(tree), new RegExp(emptyMessage))
  await act(async () => { rejectFetch(new Error('Network error')) })
  assert.match(text(tree), /Network error/)
  assert.doesNotMatch(text(tree), new RegExp(emptyMessage))
  tree.unmount()
})
