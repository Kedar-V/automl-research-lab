import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { createSession } from '../api/gateway'
import { MockBanner } from '../components/MockBanner'
import { SCENARIOS, type ScenarioName } from '../types/events'

export function SetupPage() {
  const navigate = useNavigate()
  const [taskType, setTaskType] = useState('classification')
  const [targetColumn, setTargetColumn] = useState('churned')
  const [metric, setMetric] = useState('f1')
  const [targetScore, setTargetScore] = useState(0.7)
  const [budget, setBudget] = useState(10)
  const [scenario, setScenario] = useState<ScenarioName>('happy')
  const [datasetLabel, setDatasetLabel] = useState('churn_sample.csv')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const res = await createSession({
        target_column: targetColumn,
        task_type: taskType,
        metric,
        target_score: targetScore,
        experiment_budget: budget,
        scenario,
        mock: true,
      })
      const params = new URLSearchParams({
        scenario,
        dataset: datasetLabel,
        target: targetColumn,
        metric,
        targetScore: String(targetScore),
        budget: String(budget),
      })
      navigate(`/session/${res.session_id}?${params.toString()}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="lab-grid min-h-screen">
      <MockBanner visible />
      <main className="mx-auto flex min-h-[calc(100vh-2.5rem)] max-w-3xl flex-col justify-center px-6 py-12">
        <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-teal">
          New research session
        </p>
        <h1 className="mt-2 font-display text-5xl font-semibold leading-tight text-paper sm:text-6xl">
          AutoML Research Lab
        </h1>
        <p className="mt-4 max-w-xl text-base text-mist">
          A team of AI agents that designs, runs, critiques and improves machine learning
          experiments. Choose a dataset and an objective, then watch the agents work.
        </p>

        <form onSubmit={onSubmit} className="mt-10 space-y-8">
          <section>
            <h2 className="font-mono text-xs uppercase tracking-wider text-mist">1. Dataset</h2>
            <button
              type="button"
              onClick={() => setDatasetLabel('churn_sample.csv')}
              className={`mt-3 w-full border px-4 py-4 text-left transition ${
                datasetLabel === 'churn_sample.csv'
                  ? 'border-teal bg-teal/10'
                  : 'border-line bg-panel/40 hover:border-mist'
              }`}
            >
              <span className="font-medium text-paper">churn_sample.csv</span>
              <span className="mt-1 block text-sm text-mist">
                Bundled sample · tabular, binary target
              </span>
            </button>
            <p className="mt-2 text-xs text-mist">
              CSV upload is accepted by the mock gateway; real split arrives in Stage C1.
            </p>
          </section>

          <section className="grid gap-4 sm:grid-cols-2">
            <h2 className="font-mono text-xs uppercase tracking-wider text-mist sm:col-span-2">
              2. Target column
            </h2>
            <label className="block text-sm">
              <span className="text-mist">Task type</span>
              <select
                className="mt-1 w-full border border-line bg-ink-2 px-3 py-2 text-paper"
                value={taskType}
                onChange={(e) => setTaskType(e.target.value)}
              >
                <option value="classification">Classification</option>
                <option value="regression">Regression</option>
              </select>
            </label>
            <label className="block text-sm">
              <span className="text-mist">Target column</span>
              <input
                className="mt-1 w-full border border-line bg-ink-2 px-3 py-2 text-paper"
                value={targetColumn}
                onChange={(e) => setTargetColumn(e.target.value)}
                required
              />
            </label>
          </section>

          <section className="grid gap-4 sm:grid-cols-3">
            <h2 className="font-mono text-xs uppercase tracking-wider text-mist sm:col-span-3">
              3. Objective
            </h2>
            <label className="block text-sm">
              <span className="text-mist">Metric</span>
              <select
                className="mt-1 w-full border border-line bg-ink-2 px-3 py-2 text-paper"
                value={metric}
                onChange={(e) => setMetric(e.target.value)}
              >
                <option value="f1">F1, positive class</option>
                <option value="accuracy">Accuracy</option>
                <option value="roc_auc">ROC AUC</option>
              </select>
            </label>
            <label className="block text-sm">
              <span className="text-mist">Target score</span>
              <input
                type="number"
                step="0.01"
                min={0}
                max={1}
                className="mt-1 w-full border border-line bg-ink-2 px-3 py-2 text-paper"
                value={targetScore}
                onChange={(e) => setTargetScore(Number(e.target.value))}
              />
            </label>
            <label className="block text-sm">
              <span className="text-mist">Experiment budget</span>
              <input
                type="number"
                min={1}
                max={50}
                className="mt-1 w-full border border-line bg-ink-2 px-3 py-2 text-paper"
                value={budget}
                onChange={(e) => setBudget(Number(e.target.value))}
              />
            </label>
          </section>

          <section>
            <h2 className="font-mono text-xs uppercase tracking-wider text-mist">
              Demo scenario (mock)
            </h2>
            <select
              className="mt-2 w-full border border-line bg-ink-2 px-3 py-2 text-paper"
              value={scenario}
              onChange={(e) => setScenario(e.target.value as ScenarioName)}
            >
              {SCENARIOS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </section>

          <section className="border border-line bg-panel/30 px-4 py-3 text-sm text-mist">
            <p className="font-mono text-[10px] uppercase tracking-wider text-teal">Fixed protocol</p>
            <ul className="mt-2 list-disc space-y-1 pl-5">
              <li>Train, validation and test sets are split once, with a fixed seed.</li>
              <li>Preprocessing is fitted on training data only.</li>
              <li>The sealed holdout is never shown to agents. It is opened once, at the end.</li>
              <li>Every run has retry, timeout, compute and experiment limits.</li>
            </ul>
          </section>

          {error && (
            <p className="border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="w-full bg-teal px-4 py-3 text-center text-base font-medium text-white hover:bg-teal-dim disabled:opacity-60"
          >
            {busy ? 'Starting…' : 'Start research session'}
          </button>
        </form>
      </main>
    </div>
  )
}
