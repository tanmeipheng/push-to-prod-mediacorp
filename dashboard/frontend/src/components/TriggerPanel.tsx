"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { triggerFullPipeline, triggerCrash, startMockServer, stopMockServer } from "@/lib/api";

export default function TriggerPanel({
  onPipelineStarted,
}: {
  onPipelineStarted?: () => void;
}) {
  const [loading, setLoading] = useState<string | null>(null);
  const [crashLog, setCrashLog] = useState("");
  const [showPasteLog, setShowPasteLog] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  const showMessage = (text: string, type: "success" | "error") => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 4000);
  };

  const handleRunPipeline = async () => {
    setLoading("pipeline");
    try {
      await triggerFullPipeline(crashLog || undefined);
      showMessage("Pipeline started!", "success");
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
      const result = await triggerCrash();
      setCrashLog(result.crash_log);
      setShowPasteLog(true);
      showMessage("Crash log captured!", "success");
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

  return (
    <div className="rounded-xl border border-card-border bg-card p-5">
      <h3 className="text-sm font-semibold text-muted uppercase tracking-wider mb-4">
        Quick Actions
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
