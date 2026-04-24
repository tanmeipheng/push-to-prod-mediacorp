"use client";

export default function CodeDiff({
  original,
  fixed,
}: {
  original: string;
  fixed: string;
}) {
  return (
    <div className="rounded-xl border border-card-border bg-card overflow-hidden">
      <div className="grid grid-cols-2 divide-x divide-card-border">
        {/* Original */}
        <div>
          <div className="px-4 py-2 bg-red-950/30 border-b border-card-border">
            <span className="text-xs font-semibold text-red-400 uppercase tracking-wider">
              Original Code
            </span>
          </div>
          <pre className="p-4 text-xs font-mono text-gray-300 overflow-auto max-h-[400px] whitespace-pre-wrap">
            {original}
          </pre>
        </div>

        {/* Fixed */}
        <div>
          <div className="px-4 py-2 bg-green-950/30 border-b border-card-border">
            <span className="text-xs font-semibold text-green-400 uppercase tracking-wider">
              Fixed Code
            </span>
          </div>
          <pre className="p-4 text-xs font-mono text-gray-300 overflow-auto max-h-[400px] whitespace-pre-wrap">
            {fixed}
          </pre>
        </div>
      </div>
    </div>
  );
}
