import { useCallback, useMemo, useState } from 'react'
import {
  Background,
  Controls,
  MarkerType,
  ReactFlow,
  ReactFlowProvider,
  applyNodeChanges,
  type Edge,
  type Node,
  type NodeChange,
  type NodeMouseHandler,
  type OnNodesChange,
} from '@xyflow/react'
import {
  SIMPLE_LOOP_EDGES,
  SIMPLE_LOOP_NODES,
  SIMPLE_LOOP_POSITIONS,
  type SimpleLoopNodeId,
} from '../graph/simpleLoopConfig'
import {
  SimpleLoopFlowNode,
  type SimpleLoopFlowNodeData,
} from './graph/SimpleLoopFlowNode'

const nodeTypes = { simple: SimpleLoopFlowNode }

export type SimpleNodeStatus = 'pending' | 'running' | 'completed' | 'failed'

export type SimpleLoopRuntime = Record<string, { status: SimpleNodeStatus; note?: string }>

function edgeStyle(kind: string, animated: boolean): Partial<Edge> {
  const stroke = animated ? '#0d8f6e' : kind === 'data' ? '#5a7267' : '#14241e'
  return {
    // Orthogonal routes with sharp corners — stays clean on the grid.
    type: 'step',
    pathOptions: { offset: 12, borderRadius: 0 },
    animated,
    markerEnd: {
      type: MarkerType.ArrowClosed,
      width: 12,
      height: 12,
      color: stroke,
    },
    style: {
      stroke,
      strokeWidth: animated ? 2.25 : 1.5,
      strokeDasharray: kind === 'data' ? '6 4' : undefined,
      opacity: animated ? 1 : 0.8,
    },
    labelStyle: { fill: '#5a7267', fontSize: 10, fontWeight: 500 },
    labelBgStyle: { fill: '#ffffff', fillOpacity: 0.92 },
    labelBgPadding: [4, 2] as [number, number],
  }
}

function SimpleLegend() {
  return (
    <div className="absolute bottom-3 left-3 z-10 border border-line bg-panel/95 px-3 py-2 text-[10px] text-mist shadow-sm">
      <p className="mb-1 font-mono uppercase tracking-wider text-paper">Legend</p>
      <ul className="space-y-1">
        <li className="flex items-center gap-2">
          <span className="inline-block h-px w-6 bg-paper" /> control flow
        </li>
        <li className="flex items-center gap-2">
          <span className="inline-block h-px w-6 border-t border-dashed border-mist" /> data / memory
        </li>
        <li className="flex items-center gap-2">
          <span className="inline-block h-3 w-5 border border-dashed border-mist bg-ink-2" /> dataset file
        </li>
      </ul>
    </div>
  )
}

function initialNodes(): Node[] {
  return SIMPLE_LOOP_NODES.map((n) => ({
    id: n.id,
    type: 'simple',
    position: SIMPLE_LOOP_POSITIONS[n.id],
    data: {
      title: n.title,
      role: n.role,
      service: n.service,
      status: 'pending',
      kind: n.kind,
    } satisfies SimpleLoopFlowNodeData,
    draggable: true,
  }))
}

function LiveSimpleLoopGraphInner({
  runtime,
  activeNodeId,
}: {
  runtime: SimpleLoopRuntime
  activeNodeId: string | null
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [nodes, setNodes] = useState<Node[]>(initialNodes)

  const displayNodes: Node[] = useMemo(() => {
    return nodes.map((node) => {
      const meta = SIMPLE_LOOP_NODES.find((n) => n.id === node.id)
      const rt = runtime[node.id]
      const data: SimpleLoopFlowNodeData = {
        title: meta?.title ?? node.id,
        role: meta?.role ?? '',
        service: meta?.service ?? '',
        status: rt?.status ?? 'pending',
        kind: meta?.kind ?? 'code',
      }
      return {
        ...node,
        data,
        selected: selectedId === node.id,
        draggable: true,
      }
    })
  }, [nodes, runtime, selectedId])

  const onNodesChange: OnNodesChange = useCallback((changes: NodeChange[]) => {
    setNodes((prev) => applyNodeChanges(changes, prev))
  }, [])

  const resetLayout = useCallback(() => {
    setNodes(initialNodes())
    setSelectedId(null)
  }, [])

  const edges: Edge[] = useMemo(() => {
    const running = new Set(
      Object.entries(runtime)
        .filter(([, r]) => r.status === 'running')
        .map(([id]) => id),
    )
    return SIMPLE_LOOP_EDGES.map((e) => {
      const animated = running.has(e.target)
      return {
        id: e.id,
        source: e.source,
        target: e.target,
        sourceHandle: e.sourceHandle,
        targetHandle: e.targetHandle,
        label: e.label,
        ...edgeStyle(e.kind, animated),
      }
    })
  }, [runtime])

  const onNodeClick: NodeMouseHandler = (_e, node) => {
    setSelectedId(node.id)
  }

  const selected = SIMPLE_LOOP_NODES.find((n) => n.id === (selectedId as SimpleLoopNodeId))
  const selectedRt = selectedId ? runtime[selectedId] : undefined

  return (
    <section className="relative flex h-[520px] flex-col border border-line bg-panel/40">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-3 py-2">
        <div>
          <h2 className="font-display text-xl text-paper">Live agent graph</h2>
          <p className="text-xs text-mist">
            Simple research loop · status from SSE only
            {activeNodeId ? ` · active: ${activeNodeId}` : ''}
          </p>
        </div>
        <button
          type="button"
          onClick={resetLayout}
          className="border border-line px-2 py-1 font-mono text-[11px] text-mist hover:border-teal hover:text-teal"
        >
          Reset layout
        </button>
      </div>
      <div className="relative min-h-0 flex-1">
        <ReactFlow
          nodes={displayNodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onNodeClick={onNodeClick}
          fitView
          fitViewOptions={{ padding: 0.18 }}
          nodesDraggable
          nodesConnectable={false}
          elementsSelectable
          snapToGrid
          snapGrid={[20, 20]}
          proOptions={{ hideAttribution: true }}
          minZoom={0.35}
          maxZoom={1.4}
          defaultEdgeOptions={{ type: 'step' }}
        >
          <Background gap={20} color="#c8d5ce" />
          <Controls showInteractive={false} />
          <SimpleLegend />
        </ReactFlow>
        {selected && (
          <aside className="absolute right-3 top-3 z-10 w-64 border border-line bg-panel/95 p-3 text-sm shadow-sm">
            <div className="flex items-start justify-between gap-2">
              <p className="font-medium text-paper">{selected.title}</p>
              <button
                type="button"
                className="font-mono text-xs text-mist hover:text-teal"
                onClick={() => setSelectedId(null)}
              >
                close
              </button>
            </div>
            <p className="mt-1 text-xs text-mist">{selected.role}</p>
            <p className="mt-2 font-mono text-[10px] uppercase tracking-wide text-teal">
              {selectedRt?.status ?? 'pending'} · {selected.kind.replace('_', '+')}
            </p>
            {selectedRt?.note && (
              <p className="mt-2 text-xs leading-snug text-mist">{selectedRt.note}</p>
            )}
          </aside>
        )}
      </div>
    </section>
  )
}

export function LiveSimpleLoopGraph(props: {
  runtime: SimpleLoopRuntime
  activeNodeId: string | null
}) {
  return (
    <ReactFlowProvider>
      <LiveSimpleLoopGraphInner {...props} />
    </ReactFlowProvider>
  )
}
