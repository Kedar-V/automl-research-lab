import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Background,
  Controls,
  ReactFlow,
  ReactFlowProvider,
} from '@xyflow/react'
import {
  getStudentLoopStatus,
  listSimpleLoopDatasets,
  uploadSimpleLoopDataset,
  type SimpleLoopDataset,
  type StudentLoopStatus,
} from '../api/gateway'
import {
  LiveSimpleLoopGraph,
  type SimpleLoopRuntime,
  type SimpleNodeStatus,
} from '../components/LiveSimpleLoopGraph'
import { GRAPH_NODE_TO_VISUAL } from '../graph/simpleLoopConfig'
import { guessTargetColumn, sniffCsvHeaders } from '../lib/csvHeaders'

type Step = {
  node?: string
  note?: string
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
  holdout_metrics?: { f1?: number; accuracy?: number }
  stop_reason?: string
  verdict?: { action?: string; observation?: string }
}

type StreamEvent = {
  type: string
  node?: string
  note?: string
  action?: string
  route?: string
  message?: string
  step?: Step
  cycle?: number
  best_val_f1?: number
  result?: RunResult
}

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

function EmptyStudentGraph({
  status,
  onRefresh,
  refreshing,
}: {
  status: StudentLoopStatus | null
  onRefresh: () => void
  refreshing: boolean
}) {
  const missing = status?.missing_nodes ?? []
  return (
    <section className="relative flex h-[520px] flex-col border border-line bg-panel/40">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-3 py-2">
        <div>
          <h2 className="font-display text-xl text-paper">Student graph</h2>
          <p className="text-xs text-mist">Empty until you wire build_graph() in student_loop/</p>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={refreshing}
          className="rounded border border-line bg-panel px-3 py-1.5 text-sm text-paper hover:border-teal disabled:opacity-50"
        >
          {refreshing ? 'Checking…' : 'Refresh graph'}
        </button>
      </div>
      <div className="relative min-h-0 flex-1">
        <ReactFlowProvider>
          <ReactFlow nodes={[]} edges={[]} fitView proOptions={{ hideAttribution: true }}>
            <Background gap={18} size={1} color="#2a3a32" />
            <Controls showInteractive={false} />
          </ReactFlow>
        </ReactFlowProvider>
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center p-6">
          <div className="max-w-md border border-line bg-panel/95 px-4 py-3 text-sm text-mist shadow-sm">
            <p className="font-mono text-[10px] uppercase tracking-wider text-teal">Not ready</p>
            <p className="mt-1 text-paper">
              {status?.error || 'Implement nodes, then wire build_graph().'}
            </p>
            {missing.length > 0 && (
              <ul className="mt-2 list-inside list-disc font-mono text-xs">
                {missing.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            )}
            <p className="mt-2 text-xs">
              Edit <code className="text-paper">student_loop/graph.py</code>, then Refresh.
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}

export function StudentLoopPage() {
  const [status, setStatusState] = useState<StudentLoopStatus | null>(null)
  const [statusLoading, setStatusLoading] = useState(false)
  const [catalog, setCatalog] = useState<SimpleLoopDataset[]>([])
  const [datasetFilename, setDatasetFilename] = useState('')
  const [datasetPath, setDatasetPath] = useState('')
  const [columns, setColumns] = useState<string[]>([])
  const [targetColumn, setTargetColumn] = useState('')
  const [targetScore, setTargetScore] = useState(0.8)
  const [maxCycles, setMaxCycles] = useState(3)
  const [uploading, setUploading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [runtime, setRuntime] = useState<SimpleLoopRuntime>({})
  const [activeNodeId, setActiveNodeId] = useState<string | null>(null)
  const [result, setResult] = useState<RunResult | null>(null)
  const [liveCycle, setLiveCycle] = useState(0)
  const sourceRef = useRef<EventSource | null>(null)
  const runningRef = useRef(false)

  const refreshStatus = useCallback(async () => {
    setStatusLoading(true)
    try {
      setStatusState(await getStudentLoopStatus())
    } catch (e) {
      setStatusState({
        root: '',
        available: false,
        ready: false,
        nodes: [],
        missing_nodes: [],
        error: e instanceof Error ? e.message : 'status failed',
      })
    } finally {
      setStatusLoading(false)
    }
  }, [])

  useEffect(() => {
    void refreshStatus()
  }, [refreshStatus])

  const applyDataset = useCallback((ds: SimpleLoopDataset) => {
    setDatasetFilename(ds.filename)
    setDatasetPath(ds.path || ds.filename)
    setColumns(ds.columns)
    setTargetColumn(guessTargetColumn(ds.columns) || ds.columns[0] || '')
  }, [])

  useEffect(() => {
    void (async () => {
      try {
        const rows = await listSimpleLoopDatasets()
        setCatalog(rows)
        if (rows[0]) applyDataset(rows[0])
      } catch {
        /* empty catalog ok */
      }
    })()
  }, [applyDataset])

  const onPickCatalog = (filename: string) => {
    const ds = catalog.find((d) => d.filename === filename)
    if (ds) applyDataset(ds)
  }

  const onUpload = async (file: File | null) => {
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      const text = await file.text()
      const headers = sniffCsvHeaders(text)
      const uploaded = await uploadSimpleLoopDataset(file)
      const ds: SimpleLoopDataset = {
        filename: uploaded.filename || file.name,
        path: uploaded.path,
        columns: uploaded.columns?.length ? uploaded.columns : headers,
        bytes: uploaded.bytes,
      }
      setCatalog((prev) => {
        const rest = prev.filter((p) => p.filename !== ds.filename)
        return [ds, ...rest]
      })
      applyDataset(ds)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'upload failed')
    } finally {
      setUploading(false)
    }
  }

  const resetRuntime = useCallback(() => {
    sourceRef.current?.close()
    sourceRef.current = null
    runningRef.current = false
    setBusy(false)
    setError(null)
    setResult(null)
    setRuntime({})
    setActiveNodeId(null)
    setLiveCycle(0)
  }, [])

  const onRun = useCallback(() => {
    if (!status?.ready) {
      setError('Graph not ready — wire student_loop/graph.py and Refresh')
      return
    }
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
    const source = new EventSource(`/api/student-loop/stream?${params.toString()}`)
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
        if (typeof ev.cycle === 'number') setLiveCycle(ev.cycle)
        return
      }

      if (ev.type === 'run_completed') {
        if (ev.result) setResult(ev.result)
        finish()
        return
      }

      if (ev.type === 'error') {
        setError(ev.message || 'student-loop stream error')
        finish()
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
    resetRuntime,
    status?.ready,
    targetColumn,
    targetScore,
  ])

  const ready = Boolean(status?.ready)
  const canRun = ready && Boolean(datasetFilename && targetColumn.trim()) && !busy && !uploading

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
              Student lab
            </p>
            <h1 className="font-display text-3xl font-semibold text-paper">Build Loop</h1>
            <p className="mt-1 text-sm text-mist">
              Fill <code className="text-paper">student_loop/graph.py</code>, wire the graph, then
              run
              {liveCycle > 0 ? ` · cycle ${liveCycle}` : ''}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => void refreshStatus()}
            disabled={statusLoading || busy}
            className="rounded border border-line bg-panel px-3 py-2 text-sm text-paper hover:border-teal disabled:opacity-50"
          >
            {statusLoading ? 'Checking…' : 'Refresh graph'}
          </button>
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
              ready
                ? busy
                  ? 'border-teal/50 bg-teal/15 text-teal'
                  : 'border-line bg-panel text-paper'
                : 'border-line text-mist'
            }`}
          >
            {!ready ? 'not ready' : busy ? 'running' : result ? 'completed' : error ? 'error' : 'idle'}
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

      {error && (
        <p className="border-b border-danger/40 bg-danger/10 px-6 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      <div className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6">
        {ready ? (
          <LiveSimpleLoopGraph
            runtime={runtime}
            activeNodeId={activeNodeId}
            datasetLabel={datasetFilename || null}
            targetColumn={targetColumn || null}
          />
        ) : (
          <EmptyStudentGraph
            status={status}
            onRefresh={() => void refreshStatus()}
            refreshing={statusLoading}
          />
        )}
        {result && (
          <p className="mt-4 font-mono text-sm text-mist">
            done · cycles {result.cycles ?? '—'} · best F1{' '}
            {typeof result.best_val_f1 === 'number' ? result.best_val_f1.toFixed(3) : '—'}
            {result.holdout_metrics?.f1 != null
              ? ` · holdout ${result.holdout_metrics.f1.toFixed(3)}`
              : ''}
            {result.stop_reason ? ` · ${result.stop_reason}` : ''}
          </p>
        )}
      </div>

      <footer className="border-t border-line px-6 py-3 text-center text-xs text-mist">
        Reference demo:{' '}
        <Link to="/simple-loop" className="text-teal hover:underline">
          Simple Loop
        </Link>
        {' · '}
        skeleton docs:{' '}
        <span className="font-mono text-paper">student_loop/README.md</span>
      </footer>
    </div>
  )
}
