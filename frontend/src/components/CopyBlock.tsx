import { useState } from 'react'

export function CopyBlock({ code }: { code: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      /* clipboard unavailable */
    }
  }
  return (
    <div className="relative">
      <pre className="overflow-x-auto rounded border border-line bg-ink-2 p-3 pr-20 font-mono text-xs text-paper">
        {code}
      </pre>
      <button
        type="button"
        onClick={copy}
        className="absolute right-2 top-2 rounded border border-line bg-panel px-2 py-0.5 text-xs text-mist hover:border-teal hover:text-teal"
      >
        {copied ? 'Copied' : 'Copy'}
      </button>
    </div>
  )
}
