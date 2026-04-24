"use client";

import { type Incident } from "@/lib/api";
import StatusBadge from "./StatusBadge";
import { type NodeStatus } from "@/lib/sse";
import { motion } from "framer-motion";

function timeAgo(dateStr: string): string {
  const now = new Date();
  const then = new Date(dateStr + "Z"); // SQLite dates are UTC
  const diffMs = now.getTime() - then.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function mapStatus(status: string): NodeStatus {
  switch (status) {
    case "completed":
      return "done";
    case "running":
      return "running";
    case "error":
      return "error";
    case "skipped":
      return "skipped";
    default:
      return "idle";
  }
}

export default function IncidentCard({
  incident,
  onClick,
}: {
  incident: Incident;
  onClick?: () => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      whileHover={{ scale: 1.01 }}
      onClick={onClick}
      className="flex items-center gap-4 p-4 rounded-lg border border-card-border bg-card hover:bg-gray-800/80 cursor-pointer transition-colors"
    >
      <div className="text-muted font-mono text-sm w-10 text-right">
        #{incident.id}
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="font-medium text-sm text-white truncate">
            {incident.fault_type || "pending"}
            {incident.http_status ? `/${incident.http_status}` : ""}
          </span>
          {incident.confidence !== null && (
            <span className="text-xs text-muted">
              {(incident.confidence * 100).toFixed(0)}%
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <p className="text-xs text-muted truncate flex-1">
            {incident.summary || "Processing..."}
          </p>
          {incident.pipeline_status && (
            <span className="text-[10px] font-medium text-blue-300 bg-blue-900/40 px-1.5 py-0.5 rounded-full whitespace-nowrap">
              {incident.pipeline_status}
            </span>
          )}
        </div>
      </div>

      <StatusBadge status={mapStatus(incident.status)} size="sm" />

      <div className="text-xs text-muted w-20 text-right">
        {timeAgo(incident.created_at)}
      </div>
    </motion.div>
  );
}
