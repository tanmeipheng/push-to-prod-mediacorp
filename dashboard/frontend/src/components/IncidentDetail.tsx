"use client";

import { motion } from "framer-motion";
import { type Incident, triggerReplay, triggerPR, triggerNotify } from "@/lib/api";
import LogViewer from "./LogViewer";
import CodeDiff from "./CodeDiff";
import StatusBadge from "./StatusBadge";
import { type NodeStatus } from "@/lib/sse";
import { useState } from "react";

function mapStatus(status: string): NodeStatus {
  switch (status) {
    case "completed": return "done";
    case "running": return "running";
    case "error": return "error";
    case "skipped": return "skipped";
    default: return "idle";
  }
}

export default function IncidentDetail({
  incident,
  onClose,
}: {
  incident: Incident & { events?: Array<{ node: string; event_type: string; data: string | null; created_at: string }> };
  onClose: () => void;
}) {
  const [actionMsg, setActionMsg] = useState<{ text: string; type: "success" | "error" } | null>(null);
  const [prLoading, setPrLoading] = useState(false);

  const showMessage = (text: string, type: "success" | "error") => {
    setActionMsg({ text, type });
    setTimeout(() => setActionMsg(null), 8000);
  };

  const handleReplay = async () => {
    try {
      await triggerReplay(incident.id);
      showMessage("Replay started!", "success");
    } catch (e) {
      showMessage(`Replay failed: ${e instanceof Error ? e.message : e}`, "error");
    }
  };

  const handlePR = async () => {
    setPrLoading(true);
    try {
      const result = await triggerPR(incident.id);
      showMessage(`PR created: ${result.pr_url || "branch pushed"}`, "success");
    } catch (e) {
      showMessage(`PR creation failed: ${e instanceof Error ? e.message : e}`, "error");
    } finally {
      setPrLoading(false);
    }
  };

  const handleNotify = async () => {
    try {
      await triggerNotify(incident.id);
      showMessage("Notification sent!", "success");
    } catch (e) {
      showMessage(`Notification failed: ${e instanceof Error ? e.message : e}`, "error");
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: 40 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 40 }}
      className="fixed inset-y-0 right-0 w-full max-w-3xl bg-background border-l border-card-border z-50 overflow-y-auto shadow-2xl"
    >
      {/* Header */}
      <div className="sticky top-0 bg-background/80 backdrop-blur-sm border-b border-card-border px-6 py-4 flex items-center justify-between z-10">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-bold">Incident #{incident.id}</h2>
          <StatusBadge status={mapStatus(incident.status)} />
        </div>
        <button
          onClick={onClose}
          className="text-muted hover:text-white text-xl transition-colors"
        >
          ✕
        </button>
      </div>

      <div className="p-6 space-y-6">
        {/* Actions */}
        <div className="flex gap-3 flex-wrap">
          <button onClick={handleReplay} className="px-3 py-1.5 rounded-lg bg-blue-700 hover:bg-blue-600 text-white text-xs font-medium transition-colors">
            🔄 Replay
          </button>
          {incident.fixed_code && (
            <button
              onClick={handlePR}
              disabled={prLoading}
              className="px-3 py-1.5 rounded-lg bg-purple-700 hover:bg-purple-600 text-white text-xs font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
            >
              {prLoading ? <span className="animate-spin">⟳</span> : "📦"}{" "}
              {incident.pr_url?.startsWith("http") ? "Re-create PR" : "Open PR"}
            </button>
          )}
          <button onClick={handleNotify} className="px-3 py-1.5 rounded-lg bg-yellow-700 hover:bg-yellow-600 text-white text-xs font-medium transition-colors">
            📢 Notify
          </button>
          {incident.pr_url && incident.pr_url.startsWith("http") && (
            <a
              href={incident.pr_url}
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-1.5 rounded-lg bg-gray-700 hover:bg-gray-600 text-white text-xs font-medium transition-colors"
            >
              🔗 View PR
            </a>
          )}
          {incident.jira_issue_url && (
            <a
              href={incident.jira_issue_url}
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-1.5 rounded-lg bg-blue-800 hover:bg-blue-700 text-white text-xs font-medium transition-colors"
            >
              🎫 {incident.jira_issue_key || "View Jira"}
            </a>
          )}
        </div>

        {actionMsg && (
          <div className={`px-4 py-2 rounded-lg text-sm font-medium ${
            actionMsg.type === "success"
              ? "bg-green-900/40 text-green-300 border border-green-700"
              : "bg-red-900/40 text-red-300 border border-red-700"
          }`}>
            {actionMsg.text}
          </div>
        )}

        {/* Classification */}
        {incident.fault_type && (
          <div className="rounded-xl border border-card-border bg-card p-5">
            <h3 className="text-sm font-semibold text-muted uppercase tracking-wider mb-3">
              Classification
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-xs text-muted mb-1">Fault Type</div>
                <div className="font-mono text-sm text-white">{incident.fault_type}</div>
              </div>
              <div>
                <div className="text-xs text-muted mb-1">HTTP Status</div>
                <div className="font-mono text-sm text-white">{incident.http_status ?? "N/A"}</div>
              </div>
              <div>
                <div className="text-xs text-muted mb-1">Action</div>
                <div className="font-mono text-sm text-white">{incident.action}</div>
              </div>
              <div>
                <div className="text-xs text-muted mb-1">Confidence</div>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-green-500 rounded-full transition-all"
                      style={{ width: `${(incident.confidence ?? 0) * 100}%` }}
                    />
                  </div>
                  <span className="font-mono text-sm text-white">
                    {((incident.confidence ?? 0) * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            </div>
            {incident.summary && (
              <p className="mt-3 text-sm text-gray-300">{incident.summary}</p>
            )}
            {incident.pipeline_status && (
              <div className="mt-3 flex items-center gap-2">
                <span className="text-xs text-muted">Pipeline Status:</span>
                <span className="text-xs font-medium text-blue-300 bg-blue-900/40 px-2 py-0.5 rounded-full">
                  {incident.pipeline_status}
                </span>
              </div>
            )}
            {incident.jira_issue_key && (
              <div className="mt-2 flex items-center gap-2">
                <span className="text-xs text-muted">Jira:</span>
                {incident.jira_issue_url ? (
                  <a
                    href={incident.jira_issue_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs font-medium text-blue-300 hover:text-blue-200 bg-blue-900/40 px-2 py-0.5 rounded-full transition-colors"
                  >
                    🎫 {incident.jira_issue_key}
                  </a>
                ) : (
                  <span className="text-xs font-medium text-blue-300 bg-blue-900/40 px-2 py-0.5 rounded-full">
                    🎫 {incident.jira_issue_key}
                  </span>
                )}
                {incident.jira_status && (
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                    incident.jira_status.toUpperCase() === "DONE"
                      ? "text-green-300 bg-green-900/40"
                      : incident.jira_status.toUpperCase() === "IN REVIEW"
                      ? "text-purple-300 bg-purple-900/40"
                      : incident.jira_status.toUpperCase() === "IN PROGRESS"
                      ? "text-yellow-300 bg-yellow-900/40"
                      : "text-blue-300 bg-blue-900/40"
                  }`}>
                    {incident.jira_status}
                  </span>
                )}
              </div>
            )}
          </div>
        )}

        {/* Slack Notification Stages */}
        {incident.notifications_sent && (() => {
          try {
            const stages: string[] = JSON.parse(incident.notifications_sent);
            if (stages.length === 0) return null;
            const stageConfig: Record<string, { label: string; icon: string; color: string }> = {
              detected: { label: "Detection Alert", icon: "🚨", color: "text-red-300 bg-red-900/40 border-red-700" },
              triaged: { label: "Triage Complete", icon: "🧭", color: "text-yellow-300 bg-yellow-900/40 border-yellow-700" },
              review_ready: { label: "Review Ready", icon: "📦", color: "text-purple-300 bg-purple-900/40 border-purple-700" },
              incident_report: { label: "Incident Report", icon: "✅", color: "text-green-300 bg-green-900/40 border-green-700" },
            };
            return (
              <div className="rounded-xl border border-card-border bg-card p-5">
                <h3 className="text-sm font-semibold text-muted uppercase tracking-wider mb-3">
                  Slack Notifications
                </h3>
                <div className="flex flex-wrap gap-2">
                  {stages.map((stage) => {
                    const cfg = stageConfig[stage] || { label: stage, icon: "📢", color: "text-gray-300 bg-gray-900/40 border-gray-700" };
                    return (
                      <span
                        key={stage}
                        className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border ${cfg.color}`}
                      >
                        <span>{cfg.icon}</span>
                        {cfg.label}
                      </span>
                    );
                  })}
                </div>
              </div>
            );
          } catch {
            return null;
          }
        })()}

        {/* Crash Log */}
        {incident.crash_log && (
          <LogViewer content={incident.crash_log} title="Crash Log" />
        )}

        {/* Code Diff */}
        {incident.source_code && incident.fixed_code && (
          <CodeDiff original={incident.source_code} fixed={incident.fixed_code} />
        )}

        {/* Test Code */}
        {incident.test_code && (
          <LogViewer content={incident.test_code} title="Generated Test" maxHeight="250px" />
        )}

        {/* Changes Summary */}
        {incident.changes_summary && (
          <div className="rounded-xl border border-card-border bg-card p-5">
            <h3 className="text-sm font-semibold text-muted uppercase tracking-wider mb-3">
              Changes Summary
            </h3>
            <div className="text-sm text-gray-300 whitespace-pre-wrap">
              {incident.changes_summary}
            </div>
          </div>
        )}

        {/* Pipeline Events */}
        {incident.events && incident.events.length > 0 && (
          <div className="rounded-xl border border-card-border bg-card p-5">
            <h3 className="text-sm font-semibold text-muted uppercase tracking-wider mb-3">
              Pipeline Events
            </h3>
            <div className="space-y-2">
              {incident.events.map((evt, i) => (
                <div key={i} className="flex items-center gap-3 text-xs">
                  <span className="text-muted w-36 font-mono">{evt.created_at}</span>
                  <span className={`w-16 font-semibold ${
                    evt.event_type === "done" ? "text-green-400" :
                    evt.event_type === "error" ? "text-red-400" :
                    evt.event_type === "start" ? "text-blue-400" :
                    "text-yellow-400"
                  }`}>
                    {evt.event_type}
                  </span>
                  <span className="text-white font-medium">{evt.node}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Error */}
        {incident.error_message && (
          <LogViewer content={incident.error_message} title="Error" maxHeight="200px" />
        )}
      </div>
    </motion.div>
  );
}
