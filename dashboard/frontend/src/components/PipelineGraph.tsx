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
  idle: { bg: "bg-gray-800/80", border: "border-gray-600/60", shadow: "" },
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
      className={`px-5 py-3.5 rounded-xl border-2 w-[150px] text-center cursor-default ${style.bg} ${style.border} ${style.shadow}`}
    >
      <Handle type="target" position={Position.Left} className="!bg-gray-500 !w-2 !h-2" />
      <div className="text-xl mb-1">{info.icon}</div>
      <div className="text-white font-semibold text-sm">{info.label}</div>
      <div className="text-gray-400 text-[10px] mt-0.5 leading-tight">{info.description}</div>
      <div className="mt-1.5">
        <span
          className={`inline-block text-[9px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full
            ${status === "idle" ? "bg-gray-700/60 text-gray-400" : ""}
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
      className={`px-3 py-2 rounded-lg border text-center cursor-default w-[110px] ${
        data.sent
          ? "bg-emerald-950 border-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.2)]"
          : "bg-gray-900/60 border-gray-700/50"
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

// Centered layout constants
const PIPELINE_Y = 60;
const SLACK_Y = 195;
const NODE_SPACING = 220;
const START_X = 60;

export default function PipelineGraph({
  nodeStates,
  slackStages,
}: {
  nodeStates: PipelineNodeState;
  slackStages: SlackStageState;
}) {
  const nodes: Node[] = [
    // Main pipeline nodes — evenly spaced, centered row
    {
      id: "classify",
      type: "pipeline",
      position: { x: START_X, y: PIPELINE_Y },
      data: { nodeKey: "classify", status: nodeStates.classify },
    },
    {
      id: "codegen",
      type: "pipeline",
      position: { x: START_X + NODE_SPACING, y: PIPELINE_Y },
      data: { nodeKey: "codegen", status: nodeStates.codegen },
    },
    {
      id: "open_pr",
      type: "pipeline",
      position: { x: START_X + NODE_SPACING * 2, y: PIPELINE_Y },
      data: { nodeKey: "open_pr", status: nodeStates.open_pr },
    },
    {
      id: "notify",
      type: "pipeline",
      position: { x: START_X + NODE_SPACING * 3, y: PIPELINE_Y },
      data: { nodeKey: "notify", status: nodeStates.notify },
    },
    // Slack notification nodes — aligned beneath their parent pipeline nodes
    {
      id: "slack_detected",
      type: "slack",
      position: { x: START_X - 10, y: SLACK_Y },
      data: { label: "Detection", icon: "🚨", sent: slackStages.detected },
    },
    {
      id: "slack_triaged",
      type: "slack",
      position: { x: START_X + 120, y: SLACK_Y },
      data: { label: "Triage", icon: "🧭", sent: slackStages.triaged },
    },
    {
      id: "slack_review_ready",
      type: "slack",
      position: { x: START_X + NODE_SPACING * 2 + 20, y: SLACK_Y },
      data: { label: "Review Ready", icon: "📋", sent: slackStages.review_ready },
    },
    {
      id: "slack_incident_report",
      type: "slack",
      position: { x: START_X + NODE_SPACING * 3 + 20, y: SLACK_Y },
      data: { label: "Incident Report", icon: "📊", sent: slackStages.incident_report },
    },
  ];

  const edges: Edge[] = [
    // Main pipeline edges
    {
      id: "e-classify-codegen",
      source: "classify",
      target: "codegen",
      animated: nodeStates.classify === "running",
      style: { stroke: nodeStates.classify === "done" ? "#22c55e" : "#475569", strokeWidth: 2 },
      label: "transient",
      labelStyle: { fill: "#94a3b8", fontSize: 10 },
    },
    {
      id: "e-codegen-pr",
      source: "codegen",
      target: "open_pr",
      animated: nodeStates.codegen === "running",
      style: { stroke: nodeStates.codegen === "done" ? "#22c55e" : "#475569", strokeWidth: 2 },
    },
    {
      id: "e-pr-notify",
      source: "open_pr",
      target: "notify",
      animated: nodeStates.open_pr === "running",
      style: { stroke: nodeStates.open_pr === "done" ? "#22c55e" : "#475569", strokeWidth: 2 },
    },
    // Slack stage edges
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
    <div className="w-full h-full rounded-xl border border-card-border bg-card overflow-hidden">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.15 }}
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
