"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { triggerFullPipeline, triggerCrash, startMockServer, stopMockServer } from "@/lib/api";

const SCENARIOS = [
  {
    key: "429",
    label: "429 Rate Limit",
    icon: "🚦",
    color: "from-orange-600 to-amber-700",
    border: "border-orange-700",
    bg: "bg-orange-900/30",
    desc: "Too Many Requests — partner API rate limit",
    worker: "Data Sync Worker",
  },
  {
    key: "503",
    label: "503 Service Down",
    icon: "🔌",
    color: "from-red-600 to-rose-700",
    border: "border-red-700",
    bg: "bg-red-900/30",
    desc: "Service Unavailable — catalog service offline",
    worker: "Inventory Sync Worker",
  },
  {
    key: "504",
    label: "504 Gateway Timeout",
    icon: "⏱️",
    color: "from-purple-600 to-violet-700",
    border: "border-purple-700",
    bg: "bg-purple-900/30",
    desc: "Gateway Timeout — upstream unresponsive",
    worker: "Payment Gateway Worker",
  },
  {
    key: "timeout",
    label: "Connection Timeout",
    icon: "🔗",
    color: "from-yellow-600 to-amber-600",
    border: "border-yellow-700",
    bg: "bg-yellow-900/30",
    desc: "ReadTimeout — endpoint too slow to respond",
    worker: "Metrics Collector",
  },
  {
    key: "deadlock",
    label: "DB Deadlock",
    icon: "🗄️",
    color: "from-teal-600 to-cyan-700",
    border: "border-teal-700",
    bg: "bg-teal-900/30",
    desc: "database is locked — concurrent write contention",
    worker: "Report Generator",
  },
] as const;

export default function TriggerPanel({
  onPipelineStarted,
}: {
  onPipelineStarted?: () => void;
}) {
  const [loading, setLoading] = useState<string | null>(null);
  const [crashLog, setCrashLog] = useState("");
  const [showPasteLog, setShowPasteLog] = useState(false);
  const [selectedScenario, setSelectedScenario] = useState<string>("429");
  const [message, setMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  const showMessage = (text: string, type: "success" | "error") => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 4000);
  };

  const handleRunPipeline = async () => {
    setLoading("pipeline");
    try {
      await triggerFullPipeline(crashLog || undefined, selectedScenario);
      showMessage(`Pipeline started for scenario: ${selectedScenario}`, "success");
      onPipelineStarted?.();
      setCrashLog("");
      setShowPasteLog(false);
    } catch (e) {
      showMessage(`Failed: ${e}`, "error");
    } finally {
      setLoading(null);
    }
  };

  const handleCrashWorker = async () => {
    setLoading("crash");
    try {
      const result = await triggerCrash(selectedScenario);
      setCrashLog(result.crash_log);
      setShowPasteLog(true);
      showMessage(`Crash log captured for ${selectedScenario}!`, "success");
    } catch (e) {
      showMessage(`Failed: ${e}`, "error");
    } finally {
      setLoading(null);
    }
  };

  const handleMockStart = async () => {
    setLoading("mock-start");
    try {
      const result = await startMockServer();
      showMessage(`Mock server: ${result.status}`, "success");
    } catch (e) {
      showMessage(`Failed: ${e}`, "error");
    } finally {
      setLoading(null);
    }
  };

  const handleMockStop = async () => {
    setLoading("mock-stop");
    try {
      const result = await stopMockServer();
      showMessage(`Mock server: ${result.status}`, "success");
    } catch (e) {
      showMessage(`Failed: ${e}`, "error");
    } finally {
      setLoading(null);
    }
  };

  const activeScenario = SCENARIOS.find((s) => s.key === selectedScenario)!;

  return (
    <div className="rounded-xl border border-card-border bg-card p-5">
      <h3 className="text-sm font-semibold text-muted uppercase tracking-wider mb-4">
        Failure Scenarios
      </h3>

      {message && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          className={`mb-4 px-4 py-2 rounded-lg text-sm font-medium ${
            message.type === "success"
              ? "bg-green-900/40 text-green-300 border border-green-700"
              : "bg-red-900/40 text-red-300 border border-red-700"
          }`}
        >
          {message.text}
        </motion.div>
      )}

      {/* Scenario cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-5">
        {SCENARIOS.map((s) => (
          <button
            key={s.key}
            onClick={() => setSelectedScenario(s.key)}
            className={`relative rounded-lg border p-3 text-left transition-all duration-200 cursor-pointer ${
              selectedScenario === s.key
                ? `${s.border} ${s.bg} ring-1 ring-offset-0 ring-white/20 scale-[1.02]`
                : "border-gray-700/50 bg-gray-800/40 hover:bg-gray-800/70 hover:border-gray-600"
            }`}
          >
            <div className="text-xl mb-1.5">{s.icon}</div>
            <div className="text-xs font-semibold text-white leading-tight">{s.label}</div>
            <div className="text-[10px] text-gray-400 mt-1 leading-snug">{s.worker}</div>
            {selectedScenario === s.key && (
              <motion.div
                layoutId="scenario-indicator"
                className={`absolute inset-x-0 bottom-0 h-0.5 rounded-b-lg bg-gradient-to-r ${s.color}`}
              />
            )}
          </button>
        ))}
      </div>

      {/* Selected scenario detail */}
      <div className={`rounded-lg border ${activeScenario.border} ${activeScenario.bg} px-4 py-3 mb-4`}>
        <div className="flex items-center gap-2 mb-1">
          <span className="text-lg">{activeScenario.icon}</span>
          <span className="text-sm font-semibold text-white">{activeScenario.label}</span>
          <span className="ml-auto text-[10px] font-mono text-gray-400 bg-gray-800/60 px-2 py-0.5 rounded">
            --scenario {activeScenario.key}
          </span>
        </div>
        <p className="text-xs text-gray-300">{activeScenario.desc}</p>
      </div>

      {/* Action buttons */}
      <div className="flex flex-wrap gap-3 mb-4">
        <button
          onClick={handleRunPipeline}
          disabled={loading !== null}
          className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          {loading === "pipeline" ? (
            <span className="animate-spin">⟳</span>
          ) : (
            "▶"
          )}
          Run Full Pipeline
        </button>

        <button
          onClick={handleCrashWorker}
          disabled={loading !== null}
          className="px-4 py-2 rounded-lg bg-red-700 hover:bg-red-600 text-white text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          {loading === "crash" ? (
            <span className="animate-spin">⟳</span>
          ) : (
            "💥"
          )}
          Crash Worker
        </button>

        <button
          onClick={() => setShowPasteLog(!showPasteLog)}
          className="px-4 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium transition-colors flex items-center gap-2"
        >
          📋 Paste Log
        </button>

        <div className="flex gap-2 ml-auto">
          <button
            onClick={handleMockStart}
            disabled={loading !== null}
            className="px-3 py-2 rounded-lg bg-green-800 hover:bg-green-700 text-white text-xs font-medium transition-colors disabled:opacity-50"
          >
            {loading === "mock-start" ? "..." : "🟢 Start Mock"}
          </button>
          <button
            onClick={handleMockStop}
            disabled={loading !== null}
            className="px-3 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-white text-xs font-medium transition-colors disabled:opacity-50"
          >
            {loading === "mock-stop" ? "..." : "🔴 Stop Mock"}
          </button>
        </div>
      </div>

      {showPasteLog && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          className="overflow-hidden"
        >
          <textarea
            value={crashLog}
            onChange={(e) => setCrashLog(e.target.value)}
            placeholder="Paste a crash log here, then click Run Full Pipeline..."
            className="w-full h-32 bg-gray-900 border border-gray-700 rounded-lg p-3 text-sm font-mono text-gray-300 placeholder-gray-600 resize-y focus:outline-none focus:border-blue-500"
          />
        </motion.div>
      )}
    </div>
  );
}
