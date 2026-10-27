/** Persistent while any mock service remains on the path. */

export function MockBanner({ visible }: { visible: boolean }) {
  if (!visible) return null
  return (
    <div
      role="status"
      className="border-b border-amber/40 bg-amber/15 px-4 py-2 text-center text-sm font-medium tracking-wide text-amber"
    >
      MOCK BACKEND: illustrative data, not real experiments
    </div>
  )
}
