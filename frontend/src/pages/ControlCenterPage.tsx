import { useCallback, useReducer, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { pauseSession, resetSession, resumeSession } from '../api/gateway'
import { ActivityLog } from '../components/ActivityLog'
import { BestVsPrevious } from '../components/BestVsPrevious'
import { BudgetPanel } from '../components/BudgetPanel'
import { ExperimentTimeline } from '../components/ExperimentTimeline'
import { GraphPlaceholder } from '../components/GraphPlaceholder'
import { MockBanner } from '../components/MockBanner'
import { ScoreChart } from '../components/ScoreChart'
import { ServiceHealthStrip } from '../components/ServiceHealthStrip'
import { SessionMeta } from '../components/SessionMeta'
import { TopBar } from '../components/TopBar'
import { useEventStream } from '../hooks/useEventStream'
import { initialSessionState, sessionReducer } from '../state/sessionReducer'
import type { EventEnvelope } from '../types/events'

export function ControlCenterPage() {
  const { sessionId = null } = useParams()
  const [params] = useSearchParams()
  const [busy, setBusy] = useState(false)

  const [state, dispatch] = useReducer(
    sessionReducer,
    undefined,
    () =>
      initialSessionState({
        sessionId,
        status: 'running',
        mock: true,
        scenario: params.get('scenario') ?? 'happy',
        dataset: params.get('dataset') ?? 'churn_sample.csv',
        targetColumn: params.get('target') ?? 'churned',
        metric: params.get('metric') ?? 'f1',
        targetScore: Number(params.get('targetScore') ?? 0.7),
        experimentBudget: Number(params.get('budget') ?? 10),
      }),
  )

  const onEvent = useCallback((event: EventEnvelope) => {
    dispatch({ type: 'EVENT', event })
  }, [])

  useEventStream(sessionId, state.status !== 'reset', onEvent)

  async function onPause() {
    if (!sessionId) return
    setBusy(true)
    try {
      await pauseSession(sessionId)
      dispatch({ type: 'STATUS', status: 'paused' })
    } finally {
      setBusy(false)
    }
  }

  async function onResume() {
    if (!sessionId) return
    setBusy(true)
    try {
      await resumeSession(sessionId)
      dispatch({ type: 'STATUS', status: 'running' })
    } finally {
      setBusy(false)
    }
  }

  async function onReset() {
    if (!sessionId) return
    setBusy(true)
    try {
      await resetSession(sessionId)
      dispatch({ type: 'STATUS', status: 'reset' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="lab-grid flex min-h-screen flex-col">
      <MockBanner visible={state.mock} />
      <ServiceHealthStrip health={state.serviceHealth} />
      <TopBar
        state={state}
        onPause={onPause}
        onResume={onResume}
        onReset={onReset}
        busy={busy}
      />
      <SessionMeta state={state} />

      <div className="mx-auto grid w-full max-w-[1400px] flex-1 gap-6 px-4 py-6 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="flex min-h-0 flex-col gap-6">
          <GraphPlaceholder />
          <ExperimentTimeline experiments={state.experiments} />
        </div>
        <div className="flex min-h-0 flex-col gap-6">
          <ScoreChart experiments={state.experiments} targetScore={state.targetScore} />
          <BestVsPrevious experiments={state.experiments} />
          <BudgetPanel state={state} />
          <ActivityLog items={state.activity} />
        </div>
      </div>

      <footer className="border-t border-line px-6 py-3 text-center text-xs text-mist">
        <Link to="/" className="text-teal hover:underline">
          New session
        </Link>
        {' · '}
        Stage B1 Control Center · live agent graph planned for B2
      </footer>
    </div>
  )
}
