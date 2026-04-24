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
import { type PipelineNodeState, type NodeStatus, type SlackStageState } from "@/lib/sse";
import { motion } from "framer-motion";

const statusStyles: Record<NodeStatus, { bg: string; border: string; shadow: string }> = {
  idle: { bg: "bg-gray-800", border: "border-gray-600", shadow: "" },
  running: { bg: "bg-blue-950", border: "border-blue-400", shadow: "node-running" },
  done: { bg: "bg-green-950", border: "border-green-400", shadow: "node-done" },
  error: { bg: "bg-red-950", border: "border-red-400", shadow: "node-error" },
  skipped: { bg: "bg-yellow-950", border: "border-yellow-500", shadow: "" },
};

const nodeLabels: Record<string, { label: string; icon: string; description: string }> = {
  classify: { label: "Classify", icon: "🔍", description: "LLM Router — Detect + triage" },
  codegen: { label: "Codegen", icon: "🔧", description: "LLM Coder — Generate fix + test" },
  open_pr: { label: "Open PR", icon: "📦", description: "GitHub — Branch & pull request" },
  notify: { label: "Report", icon: "📢", description: "Slack — Incident report" },
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

function SlackNode({ data }: { data: { label: string; icon: string; sent: boolean } }) {
  return (
    <motion.div
      initial={{ scale: 0.8, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      className={`px-3 py-2 rounded-lg border text-center cursor-default min-w-[120px] ${
        data.sent
          ? "bg-emerald-950 border-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.2)]"
          : "bg-gray-900 border-gray-700"
      }`}
    >
      <Handle type="target" position={Position.Top} className="!bg-gray-600 !w-1.5 !h-1.5" />
      <div className="text-sm mb-0.5">{data.icon}</div>
      <div className={`text-[10px] font-medium ${data.sent ? "text-emerald-300" : "text-gray-500"}`}>
        {data.label}
      </div>
      <div className={`text-[9px] mt-0.5 ${data.sent ? "text-emerald-400" : "text-gray-600"}`}>
        {data.sent ? "✓ sent" : "pending"}
      </div>
    </motion.div>
  );
}

const nodeTypes = { pipeline: PipelineNode, slack: SlackNode };

export default function PipelineGraph({
  nodeStates,
  slackStages,
}: {
  nodeStates: PipelineNodeState;
  slackStages: SlackStageState;
}) {
  const nodes: Node[] = [
    // Main pipeline nodes
    {
      id: "classify",
      type: "pipeline",
      position: { x: 50, y: 80 },
      data: { nodeKey: "classify", status: nodeStates.classify },
    },
    {
      id: "codegen",
      type: "pipeline",
      position: { x: 300, y: 80 },
      data: { nodeKey: "codegen", status: nodeStates.codegen },
    },
    {
      id: "open_pr",
      type: "pipeline",
      position: { x: 550, y: 80 },
      data: { nodeKey: "open_pr", status: nodeStates.open_pr },
    },
    {
      id: "notify",
      type: "pipeline",
      position: { x: 800, y: 80 },
      data: { nodeKey: "notify", status: nodeStates.notify },
    },
    // Slack notification stage nodes
    {
      id: "slack_detected",
      type: "slack",
      position: { x: 20, y: 230 },
      data: { label: "Detection", icon: "🚨", sent: slackStages.detected },
    },
    {
      id: "slack_triaged",
      type: "slack",
      position: { x: 155, y: 230 },
      data: { label: "Triage", icon: "🧭", sent: slackStages.triaged },
    },
    {
      id: "slack_review_ready",
      type: "slack",
      position: { x: 555, y: 230 },
      data: { label: "Review Ready", icon: "📋", sent: slackStages.review_ready },
    },
    {
      id: "slack_incident_report",
      type: "slack",
      position: { x: 800, y: 230 },
      data: { label: "Incident Report", icon: "📊", sent: slackStages.incident_report },
    },
    // Skip node
    {
      id: "skip",
      type: "default",
      position: { x: 300, y: 310 },
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
    // Main pipeline edges
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
    // Slack stage edges (connect pipeline nodes to their Slack sub-steps)
    {
      id: "e-classify-slack-detected",
      source: "classify",
      target: "slack_detected",
      type: "straight",
      style: { stroke: slackStages.detected ? "#10b981" : "#374151", strokeDasharray: "4,4" },
    },
    {
      id: "e-classify-slack-triaged",
      source: "classify",
      target: "slack_triaged",
      type: "straight",
      style: { stroke: slackStages.triaged ? "#10b981" : "#374151", strokeDasharray: "4,4" },
    },
    {
      id: "e-pr-slack-review",
      source: "open_pr",
      target: "slack_review_ready",
      type: "straight",
      style: { stroke: slackStages.review_ready ? "#10b981" : "#374151", strokeDasharray: "4,4" },
    },
    {
      id: "e-notify-slack-report",
      source: "notify",
      target: "slack_incident_report",
      type: "straight",
      style: { stroke: slackStages.incident_report ? "#10b981" : "#374151", strokeDasharray: "4,4" },
    },
  ];

  return (
    <div className="w-full h-[400px] rounded-xl border border-card-border bg-card overflow-hidden">
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
