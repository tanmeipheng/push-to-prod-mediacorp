"use client";

import {
  ReactFlow,
  Background,
  type Node,
  type Edge,
  Position,
  Handle,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { type PipelineNodeState, type NodeStatus } from "@/lib/sse";
import { motion } from "framer-motion";

const statusStyles: Record<NodeStatus, { bg: string; border: string; shadow: string }> = {
  idle: { bg: "bg-gray-800", border: "border-gray-600", shadow: "" },
  running: { bg: "bg-blue-950", border: "border-blue-400", shadow: "node-running" },
  done: { bg: "bg-green-950", border: "border-green-400", shadow: "node-done" },
  error: { bg: "bg-red-950", border: "border-red-400", shadow: "node-error" },
  skipped: { bg: "bg-yellow-950", border: "border-yellow-500", shadow: "" },
};

const nodeLabels: Record<string, { label: string; icon: string; description: string }> = {
  classify: { label: "Classify", icon: "🔍", description: "LLM Router — Fault classification" },
  codegen: { label: "Codegen", icon: "🔧", description: "LLM Coder — Generate fix + test" },
  open_pr: { label: "Open PR", icon: "📦", description: "GitHub — Branch & pull request" },
  notify: { label: "Notify", icon: "📢", description: "Slack — Send alert" },
};

function PipelineNode({ data }: { data: { nodeKey: string; status: NodeStatus } }) {
  const { nodeKey, status } = data;
  const info = nodeLabels[nodeKey];
  const style = statusStyles[status];

  return (
    <motion.div
      initial={{ scale: 0.9, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      className={`px-6 py-4 rounded-xl border-2 min-w-[160px] text-center cursor-default ${style.bg} ${style.border} ${style.shadow}`}
    >
      <Handle type="target" position={Position.Left} className="!bg-gray-500 !w-2 !h-2" />
      <div className="text-2xl mb-1">{info.icon}</div>
      <div className="text-white font-semibold text-sm">{info.label}</div>
      <div className="text-gray-400 text-xs mt-1">{info.description}</div>
      <div className="mt-2">
        <span
          className={`inline-block text-[10px] font-medium uppercase tracking-wider px-2 py-0.5 rounded-full
            ${status === "idle" ? "bg-gray-700 text-gray-300" : ""}
            ${status === "running" ? "bg-blue-900 text-blue-200" : ""}
            ${status === "done" ? "bg-green-900 text-green-200" : ""}
            ${status === "error" ? "bg-red-900 text-red-200" : ""}
            ${status === "skipped" ? "bg-yellow-900 text-yellow-200" : ""}
          `}
        >
          {status}
        </span>
      </div>
      <Handle type="source" position={Position.Right} className="!bg-gray-500 !w-2 !h-2" />
    </motion.div>
  );
}

const nodeTypes = { pipeline: PipelineNode };

export default function PipelineGraph({ nodeStates }: { nodeStates: PipelineNodeState }) {
  const nodes: Node[] = [
    {
      id: "classify",
      type: "pipeline",
      position: { x: 50, y: 100 },
      data: { nodeKey: "classify", status: nodeStates.classify },
    },
    {
      id: "codegen",
      type: "pipeline",
      position: { x: 300, y: 100 },
      data: { nodeKey: "codegen", status: nodeStates.codegen },
    },
    {
      id: "open_pr",
      type: "pipeline",
      position: { x: 550, y: 100 },
      data: { nodeKey: "open_pr", status: nodeStates.open_pr },
    },
    {
      id: "notify",
      type: "pipeline",
      position: { x: 800, y: 100 },
      data: { nodeKey: "notify", status: nodeStates.notify },
    },
    {
      id: "skip",
      type: "default",
      position: { x: 300, y: 250 },
      data: { label: "⏭ Skip (unknown fault)" },
      style: {
        background: "#1c1917",
        color: "#a8a29e",
        border: "2px dashed #78716c",
        borderRadius: "12px",
        padding: "12px 20px",
        fontSize: "12px",
      },
    },
  ];

  const edges: Edge[] = [
    {
      id: "e-classify-codegen",
      source: "classify",
      target: "codegen",
      animated: nodeStates.classify === "running",
      style: { stroke: nodeStates.classify === "done" ? "#22c55e" : "#475569" },
      label: "transient",
      labelStyle: { fill: "#94a3b8", fontSize: 10 },
    },
    {
      id: "e-codegen-pr",
      source: "codegen",
      target: "open_pr",
      animated: nodeStates.codegen === "running",
      style: { stroke: nodeStates.codegen === "done" ? "#22c55e" : "#475569" },
    },
    {
      id: "e-pr-notify",
      source: "open_pr",
      target: "notify",
      animated: nodeStates.open_pr === "running",
      style: { stroke: nodeStates.open_pr === "done" ? "#22c55e" : "#475569" },
    },
    {
      id: "e-classify-skip",
      source: "classify",
      target: "skip",
      animated: false,
      style: { stroke: "#78716c", strokeDasharray: "5,5" },
      label: "unknown",
      labelStyle: { fill: "#78716c", fontSize: 10 },
    },
  ];

  return (
    <div className="w-full h-[340px] rounded-xl border border-card-border bg-card overflow-hidden">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        panOnDrag={false}
        zoomOnScroll={false}
        zoomOnPinch={false}
        zoomOnDoubleClick={false}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#1e293b" gap={20} />
      </ReactFlow>
    </div>
  );
}
