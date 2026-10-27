import type { ExperimentEntry } from '../types/events'

export function ExperimentTimeline({ experiments }: { experiments: ExperimentEntry[] }) {
  const completed = experiments.filter((e) => e.status === 'completed').length
  const running = experiments.filter((e) => e.status === 'running').length

  return (
    <section className="min-h-0 flex-1 overflow-auto">
      <div className="mb-3 flex items-baseline justify-between gap-2">
        <h2 className="font-display text-xl text-paper">Experiment timeline</h2>
        <p className="font-mono text-xs text-mist">
          {completed} completed · {running} in progress
        </p>
      </div>
      <p className="mb-4 text-sm text-mist">
        Each experiment links to the Judge verdict that motivated it. Metrics arrive only from SSE.
      </p>

      {experiments.length === 0 ? (
        <p className="rounded border border-dashed border-line px-4 py-8 text-center text-sm text-mist">
          Waiting for trial events…
        </p>
      ) : (
        <ol className="space-y-3">
          {experiments.map((exp, i) => (
            <li
              key={exp.experimentId}
              className="border-l-2 border-teal/40 bg-panel/60 py-3 pl-4 pr-3"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h3 className="text-sm font-medium text-paper">
                  <span className="mr-2 font-mono text-mist">{i + 1}</span>
                  {exp.modelFamily ?? exp.experimentId}
                </h3>
                <span className="font-mono text-[11px] uppercase tracking-wide text-mist">
                  {exp.status}
                  {typeof exp.durationSeconds === 'number'
                    ? ` · ${exp.durationSeconds.toFixed(1)} s`
                    : ''}
                </span>
              </div>
              {exp.note && <p className="mt-1 text-xs text-amber">{exp.note}</p>}
              <MetricRow metrics={exp.validationMetrics} label="Val" />
              <MetricRow metrics={exp.trainMetrics} label="Train" />
              {exp.verdictAction && (
                <p className="mt-2 text-sm text-paper/90">
                  <span className="font-mono text-xs text-teal">Judge · {exp.verdictAction}</span>
                  {exp.observation ? ` — ${exp.observation}` : ''}
                </p>
              )}
              {exp.nextAction && (
                <p className="mt-1 text-xs text-mist">Next action: {exp.nextAction}</p>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

function MetricRow({
  metrics,
  label,
}: {
  metrics: Record<string, number>
  label: string
}) {
  const entries = Object.entries(metrics)
  if (!entries.length) return null
  return (
    <div className="mt-2 flex flex-wrap gap-3 font-mono text-xs text-mist">
      {entries.map(([k, v]) => (
        <span key={k}>
          {label} {k} <span className="text-paper">{v.toFixed(2)}</span>
        </span>
      ))}
    </div>
  )
}
