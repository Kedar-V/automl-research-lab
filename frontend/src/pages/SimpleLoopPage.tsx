import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  listSimpleLoopDatasets,
  listSimpleLoopModels,
  listSimpleLoopRuns,
  uploadSimpleLoopDataset,
  type SimpleLoopDataset,
  type SimpleLoopModel,
  type SimpleLoopRunRecord,
} from '../api/gateway'
import { BestVsPrevious } from '../components/BestVsPrevious'
import { BudgetPanel } from '../components/BudgetPanel'
import { ExperimentTimeline } from '../components/ExperimentTimeline'
import {
  LiveSimpleLoopGraph,
  type SimpleLoopRuntime,
  type SimpleNodeStatus,
} from '../components/LiveSimpleLoopGraph'
import { ScoreChart } from '../components/ScoreChart'
import { SelfHealPanel } from '../components/SelfHealPanel'
import { SessionMeta } from '../components/SessionMeta'
import { SimpleLoopRunHistory } from '../components/SimpleLoopRunHistory'
import { GRAPH_NODE_TO_VISUAL } from '../graph/simpleLoopConfig'
import { guessTargetColumn, sniffCsvHeaders } from '../lib/csvHeaders'
import { initialSessionState } from '../state/sessionReducer'
import type { EventEnvelope, ExperimentEntry, SessionState } from '../types/events'

type Step = {
  node?: string
  note?: string
  used_llm?: boolean
  f1?: number
  repaired?: boolean
  experiment_id?: string
  model_family?: string
  validation_metrics?: Record<string, number>
  duration_seconds?: number
  status?: string
  verdict?: { action?: string; observation?: string }
  metrics?: { f1?: number; accuracy?: number }
}

type RunResult = {
  cycles?: number
  best_val_f1?: number
  holdout_metrics?: { f1?: number; accuracy?: number; n_holdout?: number }
  verdict?: { action?: string; observation?: string }
  stop_reason?: string
  best_spec?: Record<string, unknown>
  steps?: Step[]
}

type StreamEvent = {
  type: string
  node?: string
  status?: string
  note?: string
  action?: string
  route?: string
  message?: string
  step?: Step
  cycle?: number
  best_val_f1?: number
  dataset_path?: string
  target_column?: string
  verdict?: { action?: string; observation?: string }
  result?: RunResult
}

const METRIC = 'f1'
const STRATEGY = 'model_search' as const
const TRAIN_TIMEOUT = 120
const SELF_HEAL_BUDGET = 3

function setStatus(
  prev: SimpleLoopRuntime,
  id: string,
  status: SimpleNodeStatus,
  note?: string,
): SimpleLoopRuntime {
  return {
    ...prev,
    [id]: { status, note: note ?? prev[id]?.note },
  }
}

function upsertExperiment(
  list: ExperimentEntry[],
  entry: ExperimentEntry,
): ExperimentEntry[] {
  const i = list.findIndex((e) => e.experimentId === entry.experimentId)
  if (i < 0) return [...list, entry]
  const next = [...list]
  next[i] = { ...next[i], ...entry }
  return next
}

function makeHealEvent(expId: string, note?: string): EventEnvelope {
  return {
    timestamp: new Date().toISOString(),
    session_id: 'simple-loop',
    correlation_id: `heal-${expId}`,
    source_service: 'simple-loop',
    source_agent: 'error_repair',
    type: 'activity',
    payload: {
      kind: 'self_heal',
      experiment_id: expId,
      self_heal_attempt: 1,
      self_heal_budget: SELF_HEAL_BUDGET,
      repaired: true,
      note: note ?? 'train.py repair',
      trigger: 'execution_failed',
    },
    mock: false,
  }
}

export function SimpleLoopPage() {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<RunResult | null>(null)
  const [targetScore, setTargetScore] = useState(0.8)
  const [maxCycles, setMaxCycles] = useState(3)
  const [catalog, setCatalog] = useState<SimpleLoopDataset[]>([])
  const [datasetFilename, setDatasetFilename] = useState('')
  const [datasetPath, setDatasetPath] = useState<string | null>(null)
  const [columns, setColumns] = useState<string[]>([])
  const [targetColumn, setTargetColumn] = useState('')
  const [uploading, setUploading] = useState(false)
  const [runtime, setRuntime] = useState<SimpleLoopRuntime>({})
  const [activeNodeId, setActiveNodeId] = useState<string | null>(null)
  const [experiments, setExperiments] = useState<ExperimentEntry[]>([])
  const [traceEvents, setTraceEvents] = useState<EventEnvelope[]>([])
  const [liveBest, setLiveBest] = useState<number | null>(null)
  const [liveCycle, setLiveCycle] = useState(0)
  const [stopReason, setStopReason] = useState<string | null>(null)
  const [holdoutScore, setHoldoutScore] = useState<number | null>(null)
  const [runHistory, setRunHistory] = useState<SimpleLoopRunRecord[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [models, setModels] = useState<SimpleLoopModel[]>([])
  const [modelId, setModelId] = useState('')
  const sourceRef = useRef<EventSource | null>(null)
  const runningRef = useRef(false)
  const cycleRef = useRef(0)

  const refreshHistory = useCallback(async () => {
    setHistoryLoading(true)
    try {
      setRunHistory(await listSimpleLoopRuns())
    } catch {
      // Non-fatal — panel stays empty / stale
    } finally {
      setHistoryLoading(false)
    }
  }, [])

  const applyDataset = useCallback((ds: SimpleLoopDataset) => {
    setDatasetFilename(ds.filename)
    setDatasetPath(ds.path ?? ds.filename)
    setColumns(ds.columns ?? [])
    setTargetColumn((prev) =>
      prev && (ds.columns ?? []).includes(prev)
        ? prev
        : guessTargetColumn(ds.columns ?? []),
    )
  }, [])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const rows = await listSimpleLoopDatasets()
        if (cancelled) return
        setCatalog(rows)
        if (rows.length > 0) {
          applyDataset(rows[0])
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load dataset catalog')
        }
      }
    })()
    ;(async () => {
      try {
        const catalog = await listSimpleLoopModels()
        if (cancelled) return
        setModels(catalog.models ?? [])
        setModelId((prev) => prev || catalog.default || catalog.models?.[0]?.id || '')
      } catch {
        // Non-fatal — keep empty and let run use gateway default
      }
    })()
    void refreshHistory()
    return () => {
      cancelled = true
    }
  }, [applyDataset, refreshHistory])

  const resetRuntime = useCallback(() => {
    setRuntime({})
    setActiveNodeId(null)
    setExperiments([])
    setTraceEvents([])
    setLiveBest(null)
    setLiveCycle(0)
    setStopReason(null)
    setHoldoutScore(null)
    setResult(null)
    setError(null)
    cycleRef.current = 0
  }, [])

  const onPickCatalog = useCallback(
    (filename: string) => {
      const row = catalog.find((d) => d.filename === filename)
      if (row) applyDataset(row)
    },
    [applyDataset, catalog],
  )

  const onUpload = useCallback(
    async (file: File | null) => {
      if (!file) return
      if (!file.name.toLowerCase().endsWith('.csv')) {
        setError('Please upload a .csv file')
        return
      }
      setUploading(true)
      setError(null)
      try {
        // Prefer server staging (path the gateway can read); also sniff locally for snappy UX.
        const localCols = sniffCsvHeaders(await file.text())
        const uploaded = await uploadSimpleLoopDataset(file)
        const ds: SimpleLoopDataset = {
          ...uploaded,
          columns: uploaded.columns?.length ? uploaded.columns : localCols,
        }
        setCatalog((prev) => {
          const without = prev.filter((d) => d.filename !== ds.filename)
          return [ds, ...without]
        })
        applyDataset(ds)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Upload failed')
      } finally {
        setUploading(false)
      }
    },
    [applyDataset],
  )

  const onRun = useCallback(() => {
    if (!datasetFilename && !datasetPath) {
      setError('Choose or upload a CSV first')
      return
    }
    if (!targetColumn.trim()) {
      setError('Pick a target column')
      return
    }

    sourceRef.current?.close()
    resetRuntime()
    setBusy(true)
    runningRef.current = true

    const datasetRef = datasetFilename || datasetPath || ''
    const params = new URLSearchParams({
      dataset_path: datasetRef,
      target_column: targetColumn.trim(),
      target_score: String(targetScore),
      max_cycles: String(maxCycles),
    })
    if (modelId.trim()) params.set('model', modelId.trim())
    const source = new EventSource(`/api/simple-loop/stream?${params.toString()}`)
    sourceRef.current = source

    const finish = () => {
      runningRef.current = false
      setBusy(false)
      setActiveNodeId(null)
      source.close()
      if (sourceRef.current === source) sourceRef.current = null
    }

    const datasetNote = datasetFilename || datasetRef

    const handle = (msg: MessageEvent<string>) => {
      let ev: StreamEvent
      try {
        ev = JSON.parse(msg.data) as StreamEvent
      } catch {
        return
      }

      if (ev.type === 'run_started') {
        setRuntime((prev) => setStatus(prev, 'dataset', 'completed', datasetNote))
        return
      }

      if (ev.type === 'node_started' && ev.node) {
        const visual = GRAPH_NODE_TO_VISUAL[ev.node] ?? ev.node
        setActiveNodeId(visual)
        setRuntime((prev) => {
          let next = setStatus(prev, visual, 'running')
          if (ev.node === 'data_scientist') {
            next = setStatus(next, 'dataset', 'completed', datasetNote)
          }
          return next
        })
        if (ev.node === 'ml_engineer') {
          const id = `exp-${cycleRef.current + 1}`
          setExperiments((prev) =>
            upsertExperiment(prev, {
              experimentId: id,
              status: 'running',
              trainMetrics: {},
              validationMetrics: {},
              note: 'training…',
            }),
          )
        }
        if (ev.node === 'holdout_eval') {
          setRuntime((prev) => setStatus(prev, 'best_candidate', 'completed', 'candidate locked'))
        }
        return
      }

      if (ev.type === 'router' && ev.node) {
        setActiveNodeId('router')
        setRuntime((prev) =>
          setStatus(prev, 'router', 'completed', `route → ${ev.route} (${ev.action})`),
        )
        if (ev.route === 'holdout') {
          setRuntime((prev) => setStatus(prev, 'best_candidate', 'completed', 'candidate locked'))
        }
        return
      }

      if (ev.type === 'node_completed' && ev.node) {
        const visual = GRAPH_NODE_TO_VISUAL[ev.node] ?? ev.node
        const note =
          ev.note ||
          ev.step?.note ||
          ev.step?.verdict?.observation ||
          (typeof ev.step?.f1 === 'number' ? `f1 ${ev.step.f1.toFixed(3)}` : undefined)
        setRuntime((prev) => setStatus(prev, visual, 'completed', note))

        if (typeof ev.best_val_f1 === 'number' && ev.best_val_f1 >= 0) {
          setLiveBest(ev.best_val_f1)
        }
        if (typeof ev.cycle === 'number') {
          setLiveCycle(ev.cycle)
          cycleRef.current = ev.cycle
        }

        if (ev.node === 'ml_engineer' && ev.step) {
          const step = ev.step
          const expId =
            step.experiment_id ||
            `exp-${typeof ev.cycle === 'number' ? ev.cycle : cycleRef.current || 1}`
          const metrics = step.validation_metrics ?? {}
          const f1 = typeof step.f1 === 'number' ? step.f1 : metrics.f1
          const failed = step.status === 'failed' || step.status === 'error'
          setExperiments((prev) => {
            const runningIdx = prev.findIndex((e) => e.status === 'running')
            const base = runningIdx >= 0 ? prev.filter((_, i) => i !== runningIdx) : prev
            return upsertExperiment(base, {
              experimentId: expId,
              modelFamily: step.model_family,
              status: failed ? 'failed' : 'completed',
              trainMetrics: {},
              validationMetrics: {
                ...metrics,
                ...(typeof f1 === 'number' ? { f1 } : {}),
              },
              durationSeconds:
                typeof step.duration_seconds === 'number' ? step.duration_seconds : undefined,
              retryCount: step.repaired ? 1 : 0,
              note: step.note,
            })
          })
          if (step.repaired) {
            setTraceEvents((prev) => [...prev, makeHealEvent(expId, step.note)])
          }
        }

        if (ev.node === 'judge' && ev.step?.verdict) {
          const action = ev.step.verdict.action
          const observation = ev.step.verdict.observation
          setExperiments((prev) => {
            if (prev.length === 0) return prev
            const last = prev[prev.length - 1]
            return [
              ...prev.slice(0, -1),
              {
                ...last,
                verdictAction: action,
                observation,
                nextAction: action,
              },
            ]
          })
        }

        if (ev.node === 'holdout_eval' && ev.step?.metrics?.f1 != null) {
          setHoldoutScore(ev.step.metrics.f1)
        }
        return
      }

      if (ev.type === 'run_completed') {
        if (ev.result) {
          setResult(ev.result)
          if (ev.result.stop_reason) setStopReason(ev.result.stop_reason)
          if (ev.result.holdout_metrics?.f1 != null) {
            setHoldoutScore(ev.result.holdout_metrics.f1)
          }
          if (typeof ev.result.best_val_f1 === 'number') {
            setLiveBest(ev.result.best_val_f1)
          }
        }
        finish()
        void refreshHistory()
        return
      }

      if (ev.type === 'error') {
        setError(ev.message || 'simple-loop stream error')
        finish()
        void refreshHistory()
      }
    }

    ;[
      'run_started',
      'node_started',
      'node_completed',
      'router',
      'run_completed',
      'error',
      'message',
    ].forEach((t) => source.addEventListener(t, handle as EventListener))
    source.onmessage = handle
    source.onerror = () => {
      if (runningRef.current) {
        setError('SSE connection lost before run finished')
        finish()
      } else {
        source.close()
        if (sourceRef.current === source) sourceRef.current = null
      }
    }
  }, [
    datasetFilename,
    datasetPath,
    maxCycles,
    modelId,
    refreshHistory,
    resetRuntime,
    targetColumn,
    targetScore,
  ])

  const canRun = Boolean(datasetFilename && targetColumn.trim()) && !busy && !uploading

  const panelState: SessionState = useMemo(
    () =>
      initialSessionState({
        sessionId: 'simple-loop',
        status: busy ? 'running' : result ? 'completed' : error ? 'error' : 'idle',
        mode: 'live',
        dataset: datasetFilename || '—',
        targetColumn: targetColumn || '—',
        metric: METRIC,
        targetScore,
        experimentBudget: maxCycles,
        experimentsUsed: experiments.filter((e) => e.status !== 'running').length,
        selfHealBudget: SELF_HEAL_BUDGET,
        researchStrategy: STRATEGY,
        perTrialTimeoutSeconds: TRAIN_TIMEOUT,
        bestValScore: result?.best_val_f1 ?? liveBest,
        holdoutScore,
        stopReason: result?.stop_reason ?? stopReason,
        experiments,
        traceEvents,
        error,
      }),
    [
      busy,
      result,
      error,
      datasetFilename,
      targetColumn,
      targetScore,
      maxCycles,
      experiments,
      liveBest,
      holdoutScore,
      stopReason,
      traceEvents,
    ],
  )

  return (
    <div className="lab-grid flex min-h-screen flex-col">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-line px-6 py-4">
        <div className="flex min-w-0 items-start gap-3">
          <Link
            to="/"
            className="mt-1 inline-flex shrink-0 items-center gap-1.5 rounded border border-line bg-panel px-3 py-2 text-sm text-paper hover:border-teal hover:text-teal"
          >
            <span aria-hidden className="font-mono text-base leading-none">
              ←
            </span>
            Back
          </Link>
          <div className="min-w-0">
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-teal">
              Teaching path
            </p>
            <h1 className="font-display text-3xl font-semibold text-paper">
              Simple research loop
            </h1>
            <p className="mt-1 text-sm text-mist">
              LangGraph mini-loop · any CSV · live SSE
              {liveCycle > 0 ? ` · cycle ${liveCycle}` : ''}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-mist">
            Model
            <select
              value={modelId}
              onChange={(e) => setModelId(e.target.value)}
              disabled={busy || models.length === 0}
              className="max-w-[18rem] border border-line bg-ink-2 px-2 py-1.5 font-mono text-xs text-paper"
              title="LLM used by simple-loop agents"
            >
              {models.length === 0 && <option value="">Loading models…</option>}
              {models.some((m) => m.provider === 'cursor') && (
                <optgroup label="Cursor SDK">
                  {models
                    .filter((m) => m.provider === 'cursor')
                    .map((m) => (
                      <option key={m.id} value={m.id} disabled={m.available === false}>
                        {m.name}
                        {m.available === false ? ' (set CURSOR_API_KEY)' : ''}
                      </option>
                    ))}
                </optgroup>
              )}
              {models.some((m) => m.provider !== 'cursor' && m.free) && (
                <optgroup label="OpenRouter (free)">
                  {models
                    .filter((m) => m.provider !== 'cursor' && m.free)
                    .map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name}
                      </option>
                    ))}
                </optgroup>
              )}
              {models.some((m) => m.provider !== 'cursor' && !m.free) && (
                <optgroup label="OpenRouter">
                  {models
                    .filter((m) => m.provider !== 'cursor' && !m.free)
                    .map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name}
                      </option>
                    ))}
                </optgroup>
              )}
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm text-mist">
            Target score
            <input
              type="number"
              step="0.01"
              min={0.5}
              max={0.99}
              value={targetScore}
              onChange={(e) => setTargetScore(Number(e.target.value))}
              className="w-20 border border-line bg-ink-2 px-2 py-1.5 font-mono text-paper"
              disabled={busy}
            />
          </label>
          <label className="flex items-center gap-2 text-sm text-mist">
            Budget
            <input
              type="number"
              min={1}
              max={8}
              value={maxCycles}
              onChange={(e) => setMaxCycles(Number(e.target.value))}
              className="w-16 border border-line bg-ink-2 px-2 py-1.5 font-mono text-paper"
              disabled={busy}
            />
          </label>
          <span
            className={`rounded border px-2 py-1 font-mono text-[11px] uppercase tracking-wide ${
              busy
                ? 'border-teal/50 bg-teal/15 text-teal'
                : result
                  ? 'border-line bg-panel text-paper'
                  : 'border-line text-mist'
            }`}
          >
            {busy ? 'running' : result ? 'completed' : error ? 'error' : 'idle'}
          </span>
          <button
            type="button"
            disabled={!canRun}
            onClick={onRun}
            className="rounded border border-teal bg-teal px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {busy ? 'Running…' : 'Run loop'}
          </button>
          {(result || error) && (
            <button
              type="button"
              disabled={busy}
              onClick={resetRuntime}
              className="rounded border border-line bg-panel px-3 py-2 text-sm text-paper hover:border-teal"
            >
              Reset
            </button>
          )}
        </div>
      </header>

      <div className="flex flex-wrap items-end gap-4 border-b border-line px-6 py-3">
        <label className="text-sm">
          <span className="font-mono text-[10px] uppercase tracking-wider text-mist">Dataset</span>
          <select
            value={datasetFilename}
            onChange={(e) => onPickCatalog(e.target.value)}
            disabled={busy || uploading}
            className="mt-1 block min-w-[14rem] border border-line bg-ink-2 px-3 py-2 font-mono text-sm text-paper"
          >
            {catalog.length === 0 && <option value="">No CSVs yet — upload one</option>}
            {catalog.map((d) => (
              <option key={d.filename} value={d.filename}>
                {d.filename}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="font-mono text-[10px] uppercase tracking-wider text-mist">
            Target column
          </span>
          <select
            value={targetColumn}
            onChange={(e) => setTargetColumn(e.target.value)}
            disabled={busy || uploading || columns.length === 0}
            className="mt-1 block min-w-[12rem] border border-line bg-ink-2 px-3 py-2 font-mono text-sm text-paper"
          >
            {columns.length === 0 && <option value="">—</option>}
            {columns.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="font-mono text-[10px] uppercase tracking-wider text-mist">
            Upload CSV
          </span>
          <input
            type="file"
            accept=".csv,text/csv"
            disabled={busy || uploading}
            onChange={(e) => {
              const f = e.target.files?.[0] ?? null
              void onUpload(f)
              e.target.value = ''
            }}
            className="mt-1 block max-w-[16rem] text-sm text-mist file:mr-3 file:border file:border-line file:bg-panel file:px-3 file:py-1.5 file:text-sm file:text-paper"
          />
        </label>
        {uploading && <p className="pb-2 text-sm text-teal">Uploading…</p>}
      </div>

      <SessionMeta state={panelState} />

      {error && (
        <p className="border-b border-danger/40 bg-danger/10 px-6 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      <div className="mx-auto grid w-full max-w-[1400px] flex-1 gap-6 px-4 py-6 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="flex min-h-0 flex-col gap-6">
          <LiveSimpleLoopGraph
            runtime={runtime}
            activeNodeId={activeNodeId}
            datasetLabel={datasetFilename || null}
            targetColumn={targetColumn || null}
          />
          <ExperimentTimeline experiments={experiments} traceEvents={traceEvents} />
        </div>
        <div className="flex min-h-0 flex-col gap-6">
          <ScoreChart experiments={experiments} targetScore={targetScore} />
          <SelfHealPanel
            experiments={experiments}
            traceEvents={traceEvents}
            budget={SELF_HEAL_BUDGET}
          />
          <BestVsPrevious experiments={experiments} />
          <BudgetPanel state={panelState} />
          <SimpleLoopRunHistory
            runs={runHistory}
            loading={historyLoading}
            onRefresh={() => void refreshHistory()}
          />
        </div>
      </div>

      <footer className="border-t border-line px-6 py-3 text-center text-xs text-mist">
        <Link to="/" className="text-teal hover:underline">
          Projects
        </Link>
        {' · '}
        <Link to="/simple-loop" className="text-teal hover:underline">
          Simple loop
        </Link>
        {' · '}
        Live agent graph driven by SSE
      </footer>
    </div>
  )
}
