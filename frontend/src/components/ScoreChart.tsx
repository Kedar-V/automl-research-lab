import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { ExperimentEntry } from '../types/events'

export function ScoreChart({
  experiments,
  targetScore,
}: {
  experiments: ExperimentEntry[]
  targetScore: number
}) {
  const data = experiments
    .filter((e) => typeof e.validationMetrics.f1 === 'number')
    .map((e, i) => ({
      index: i + 1,
      id: e.experimentId,
      f1: e.validationMetrics.f1,
    }))

  return (
    <section>
      <h2 className="font-display text-xl text-paper">Validation F1 by experiment</h2>
      <p className="mb-3 text-sm text-mist">
        Positive class · dashed line is the {targetScore.toFixed(2)} target
      </p>
      <div className="h-48 w-full">
        {data.length === 0 ? (
          <div className="flex h-full items-center justify-center border border-dashed border-line text-sm text-mist">
            No validation scores yet
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="rgba(154,175,165,0.15)" strokeDasharray="3 3" />
              <XAxis dataKey="index" stroke="#9aafa5" fontSize={11} />
              <YAxis domain={[0, 1]} stroke="#9aafa5" fontSize={11} width={32} />
              <Tooltip
                contentStyle={{
                  background: '#1a2420',
                  border: '1px solid #2a3a34',
                  borderRadius: 0,
                  fontSize: 12,
                }}
              />
              <ReferenceLine
                y={targetScore}
                stroke="#e8b84a"
                strokeDasharray="4 4"
                label={{ value: `Target ${targetScore.toFixed(2)}`, fill: '#e8b84a', fontSize: 11 }}
              />
              <Line
                type="monotone"
                dataKey="f1"
                stroke="#2dd4a8"
                strokeWidth={2}
                dot={{ r: 4, fill: '#2dd4a8' }}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  )
}
