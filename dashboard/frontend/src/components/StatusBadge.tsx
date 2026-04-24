"use client";

import { NodeStatus } from "@/lib/sse";

const statusConfig: Record<
  NodeStatus,
  { bg: string; border: string; text: string; icon: string; className: string }
> = {
  idle: {
    bg: "bg-gray-800/50",
    border: "border-gray-700",
    text: "text-gray-400",
    icon: "○",
    className: "",
  },
  running: {
    bg: "bg-blue-950/60",
    border: "border-blue-500",
    text: "text-blue-300",
    icon: "⟳",
    className: "node-running",
  },
  done: {
    bg: "bg-green-950/40",
    border: "border-green-500",
    text: "text-green-300",
    icon: "✓",
    className: "node-done",
  },
  error: {
    bg: "bg-red-950/40",
    border: "border-red-500",
    text: "text-red-300",
    icon: "✕",
    className: "node-error",
  },
  skipped: {
    bg: "bg-yellow-950/30",
    border: "border-yellow-600",
    text: "text-yellow-300",
    icon: "⏭",
    className: "",
  },
};

export default function StatusBadge({
  status,
  size = "md",
}: {
  status: NodeStatus;
  size?: "sm" | "md" | "lg";
}) {
  const config = statusConfig[status];
  const sizeClasses = {
    sm: "text-xs px-2 py-0.5",
    md: "text-sm px-3 py-1",
    lg: "text-base px-4 py-1.5",
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-medium ${config.bg} ${config.border} ${config.text} ${config.className} ${sizeClasses[size]}`}
    >
      <span className="text-xs">{config.icon}</span>
      {status}
    </span>
  );
}
