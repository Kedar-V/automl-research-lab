import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { AppNav } from '../components/AppNav'
import { CopyBlock } from '../components/CopyBlock'
import {
  CONFIRM_OUTPUT_CMD,
  ENV_CMD,
  LIST_RUNS_CMD,
  START_CMD,
  TASK_SNIPPETS,
  TRIGGER_CMD,
  UNPAUSE_CMD,
  WIRING_SNIPPET,
} from '../guide/airflowSnippets'
import {
  BUILD_GRAPH_SNIPPET,
  NODE_SNIPPETS,
  STACK_CMD,
  STATUS_CMD,
} from '../guide/langgraphSnippets'

function Step({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <section className="space-y-3 rounded border border-line bg-panel/80 p-4">
      <h2 className="font-display text-lg text-paper">
        <span className="mr-2 text-teal">{n}.</span>
        {title}
      </h2>
      {children}
    </section>
  )
}

function Code({ children }: { children: ReactNode }) {
  return <code className="font-mono text-xs text-teal">{children}</code>
}

function AirflowTab() {
  return (
    <div className="space-y-4 text-sm text-mist">
      <Step n={1} title="Start Airflow">
        <ol className="list-decimal space-y-2 pl-5">
          <li>Make sure Docker Desktop is running.</li>
          <li>
            From the repo root, if <Code>.env</Code> is missing:
            <div className="mt-2">
              <CopyBlock code={ENV_CMD} />
            </div>
          </li>
          <li>
            Start the Airflow profile:
            <div className="mt-2">
              <CopyBlock code={START_CMD} />
            </div>
          </li>
          <li>
            Open{' '}
            <a className="text-teal underline" href="http://localhost:8088" target="_blank" rel="noreferrer">
              http://localhost:8088
            </a>{' '}
            and log in with <Code>admin</Code> / <Code>admin</Code> (unless <Code>.env</Code> overrides).
          </li>
          <li>
            Confirm the DAG list has <Code>student_baseline_prep</Code> (the lab) and{' '}
            <Code>simple_loop_baseline_prep</Code> (the filled reference).
          </li>
        </ol>
        <p>Docker only. Do not install Airflow on your host.</p>
      </Step>

      <Step n={2} title="Open the skeleton">
        <p>
          Open <Code>airflow/dags/student_baseline_prep.py</Code>. Until it is wired, the DAG parses
          and the Graph tab is empty. Don&apos;t Trigger until the wiring is uncommented and the task
          bodies are filled.
        </p>
        <p>
          Each DAG is one file: pandas/sklearn code lives inside the <Code>@task</Code> bodies (no
          helper modules). Copy from <Code>airflow/dags/simple_loop_baseline_prep.py</Code>,{' '}
          <Code>airflow/dags/COPY_GUIDE.md</Code>, or the snippets below.
        </p>
      </Step>

      <Step n={3} title="Fill task bodies">
        <p>
          Replace each <Code>NotImplementedError</Code> stub with the matching body (constants like{' '}
          <Code>CUSTOMERS</Code> / <Code>TARGET</Code> are already at the top of the student file).
        </p>
        {TASK_SNIPPETS.map((s) => (
          <div key={s.id} className="space-y-1">
            <h3 className="font-mono text-paper">{s.title}</h3>
            <p>{s.hint}</p>
            <CopyBlock code={s.code} />
          </div>
        ))}
      </Step>

      <Step n={4} title="Wire the DAG">
        <p>
          Uncomment the wiring block (identical to <Code>simple_loop_baseline_prep.py</Code>) or paste:
        </p>
        <CopyBlock code={WIRING_SNIPPET} />
        <p>After you save, the Graph tab shows the full dependency graph.</p>
      </Step>

      <Step n={5} title="Run in Airflow">
        <p>
          From the <strong>repo root</strong> (Airflow already up). You can also unpause/trigger in the
          UI at{' '}
          <a className="text-teal underline" href="http://localhost:8088" target="_blank" rel="noreferrer">
            localhost:8088
          </a>
          .
        </p>
        <ol className="list-decimal space-y-3 pl-5">
          <li>
            Unpause <Code>student_baseline_prep</Code>:
            <div className="mt-2">
              <CopyBlock code={UNPAUSE_CMD} />
            </div>
          </li>
          <li>
            Trigger the DAG:
            <div className="mt-2">
              <CopyBlock code={TRIGGER_CMD} />
            </div>
          </li>
          <li>
            Wait until the run succeeds (Graph tab all green, or poll CLI):
            <div className="mt-2">
              <CopyBlock code={LIST_RUNS_CMD} />
            </div>
          </li>
          <li>
            Confirm publish + artifacts on the host:
            <div className="mt-2">
              <CopyBlock code={CONFIRM_OUTPUT_CMD} />
            </div>
          </li>
        </ol>
      </Step>
    </div>
  )
}

function LangGraphTab() {
  return (
    <div className="space-y-4 text-sm text-mist">
      <Step n={1} title="Start the stack + UI">
        <ol className="list-decimal space-y-2 pl-5">
          <li>Docker Desktop running.</li>
          <li>
            From the repo root:
            <div className="mt-2">
              <CopyBlock code={STACK_CMD} />
            </div>
          </li>
          <li>
            Open the student canvas:{' '}
            <Link className="text-teal underline" to="/student-loop">
              /student-loop
            </Link>
            . The graph stays empty until <Code>build_graph()</Code> is wired.
          </li>
        </ol>
      </Step>

      <Step n={2} title="Open the skeleton">
        <p>
          Edit <Code>student_loop/graph.py</Code>. Everything is self-contained in that file (no helpers
          module). Filled reference: <Code>mini_loop/graph.py</Code> — same shape, with working bodies.
          Markdown copy steps: <Code>student_loop/COPY_GUIDE.md</Code>.
        </p>
        <div>
          Optional readiness check:
          <div className="mt-2">
            <CopyBlock code={STATUS_CMD} />
          </div>
        </div>
      </Step>

      <Step n={3} title="Fill agent nodes + router">
        <p>
          Replace each <Code>raise NotImplementedError(...)</Code> body with the matching snippet
          (keep the function signatures). Imports for pandas/sklearn are already at the top of the
          student file.
        </p>
        {NODE_SNIPPETS.map((s) => (
          <div key={s.id} className="space-y-1">
            <h3 className="font-mono text-paper">{s.title}</h3>
            <p>{s.hint}</p>
            <CopyBlock code={s.code} />
          </div>
        ))}
      </Step>

      <Step n={4} title="Wire build_graph()">
        <p>
          Inside <Code>build_graph()</Code>, remove the final <Code>raise NotImplementedError</Code> and
          paste this after <Code>g = StateGraph(SimpleLoopState)</Code>:
        </p>
        <CopyBlock code={BUILD_GRAPH_SNIPPET} />
        <p>
          <Code>add_node</Code> = a box on the graph. <Code>add_edge</Code> = always go next.{' '}
          <Code>add_conditional_edges</Code> = ask the router which path. <Code>compile()</Code> freezes
          it. Topology: START → data_scientist → hypothesis → ml_engineer → judge → (memory loop or
          holdout → END).
        </p>
      </Step>

      <Step n={5} title="Refresh and run">
        <ol className="list-decimal space-y-1 pl-5">
          <li>
            On{' '}
            <Link className="text-teal underline" to="/student-loop">
              /student-loop
            </Link>
            , click Refresh (or reload the page). The live graph should appear when status is ready.
          </li>
          <li>
            Pick a CSV (e.g. <Code>Titanic-Dataset.csv</Code>, target <Code>Survived</Code>) and Run.
          </li>
          <li>Watch nodes complete over SSE. Holdout runs once at the end.</li>
        </ol>
      </Step>
    </div>
  )
}

export function GuidePage() {
  const [tab, setTab] = useState<'airflow' | 'langgraph'>('airflow')
  const tabCls = (t: string) =>
    `rounded-t border border-b-0 border-line px-4 py-1.5 text-sm ${
      tab === t ? 'bg-panel text-teal' : 'text-mist hover:text-paper'
    }`
  return (
    <div className="lab-grid min-h-screen">
      <AppNav />
      <main className="mx-auto max-w-[900px] space-y-4 px-4 py-6">
        <h1 className="font-display text-2xl text-paper">Student Guide</h1>
        <div className="flex gap-1">
          <button type="button" className={tabCls('airflow')} onClick={() => setTab('airflow')}>
            Airflow
          </button>
          <button type="button" className={tabCls('langgraph')} onClick={() => setTab('langgraph')}>
            LangGraph
          </button>
        </div>
        {tab === 'airflow' ? <AirflowTab /> : <LangGraphTab />}
      </main>
    </div>
  )
}
