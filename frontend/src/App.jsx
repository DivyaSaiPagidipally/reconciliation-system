import { useState } from 'react'
import Dashboard from './pages/Dashboard.jsx'
import ResultDetail from './pages/ResultDetail.jsx'

// Simple client-side navigation: the app has three meaningful views
// (dashboard/home, run results, result detail). React state is enough —
// react-router would be overkill for a take-home.
function App() {
  const [view, setView] = useState({ name: 'dashboard' })

  const navigate = (viewObj) => {
    setView(viewObj)
    window.scrollTo(0, 0)
  }

  let page
  if (view.name === 'results') {
    page = <Dashboard key={`results-${view.runId}`} embeddedRunId={view.runId} navigate={navigate} />
  } else if (view.name === 'detail') {
    page = <ResultDetail key={view.resultId} resultId={view.resultId} navigate={navigate} />
  } else {
    page = <Dashboard navigate={navigate} />
  }

  return (
    <div className="app">
      <header className="row">
        <h1>🧾 Transaction Reconciliation</h1>
        <div className="spacer" />
        {view.name !== 'dashboard' && (
          <button className="btn ghost small" onClick={() => navigate({ name: 'dashboard' })}>
            ← Back
          </button>
        )}
      </header>
      {page}
    </div>
  )
}

export default App