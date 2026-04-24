"use client";

export default function LogViewer({
  content,
  title = "Crash Log",
  maxHeight = "300px",
}: {
  content: string;
  title?: string;
  maxHeight?: string;
}) {
  return (
    <div className="rounded-xl border border-card-border bg-card overflow-hidden">
      <div className="px-4 py-2 bg-gray-800 border-b border-card-border flex items-center justify-between">
        <span className="text-xs font-semibold text-muted uppercase tracking-wider">
          {title}
        </span>
        <button
          onClick={() => navigator.clipboard.writeText(content)}
          className="text-xs text-muted hover:text-white transition-colors"
        >
          📋 Copy
        </button>
      </div>
      <pre
        className="p-4 text-xs font-mono text-gray-300 overflow-auto whitespace-pre-wrap"
        style={{ maxHeight }}
      >
        {content}
      </pre>
    </div>
  );
}
