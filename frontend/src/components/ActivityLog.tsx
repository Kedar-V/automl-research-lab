import type { ActivityItem } from '../types/events'

export function ActivityLog({ items }: { items: ActivityItem[] }) {
  const newestFirst = [...items].reverse()

  return (
    <section className="flex min-h-0 flex-col">
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <h2 className="font-display text-xl text-paper">Agent activity log</h2>
        <p className="font-mono text-[10px] uppercase tracking-wider text-mist">
          Streaming over SSE
        </p>
      </div>
      <div className="min-h-48 flex-1 overflow-auto border border-line bg-ink/50 font-mono text-xs">
        {newestFirst.length === 0 ? (
          <p className="p-4 text-mist">No events yet</p>
        ) : (
          <ul className="divide-y divide-line/60">
            {newestFirst.map((item) => (
              <li key={item.id} className="grid grid-cols-[auto_7rem_1fr] gap-3 px-3 py-2">
                <time className="text-mist tabular-nums">
                  {new Date(item.timestamp).toLocaleTimeString()}
                </time>
                <span className="truncate text-teal">{item.agent}</span>
                <span className="text-paper/90">{item.message}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}
