"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

interface TimelineDataPoint {
  day: string;
  total: number;
  fixed: number;
  skipped: number;
  errored: number;
}

export default function TimelineChart({
  data,
  collapsed = false,
  onToggle,
}: {
  data: TimelineDataPoint[];
  collapsed?: boolean;
  onToggle?: () => void;
}) {
  if (collapsed) {
    return (
      <button
        onClick={onToggle}
        className="rounded-xl border border-card-border bg-card flex items-center justify-center py-4 px-2 h-full group hover:border-gray-500 transition-colors"
      >
        <span className="text-xs font-semibold text-muted uppercase tracking-widest [writing-mode:vertical-lr] rotate-180 group-hover:text-white transition-colors">
          ◀ Incident Timeline
        </span>
      </button>
    );
  }

  return (
    <div className="rounded-xl border border-card-border bg-card p-4 h-full flex flex-col">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between text-left group mb-4 flex-shrink-0"
      >
        <h3 className="text-sm font-semibold text-muted uppercase tracking-wider">
          Incident Timeline (7 days)
        </h3>
        <span className="text-muted group-hover:text-white transition-colors text-xs" title="Collapse">
          ▶
        </span>
      </button>
      {data.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-muted text-sm">
          No incident data yet. Run the pipeline to see activity here.
        </div>
      ) : (
        <div className="flex-1 min-h-0">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data}>
              <defs>
                <linearGradient id="colorFixed" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorTotal" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis
                dataKey="day"
                tick={{ fill: "#64748b", fontSize: 11 }}
                tickFormatter={(v: string) => v.slice(5)}
                axisLine={false}
              />
              <YAxis
                tick={{ fill: "#64748b", fontSize: 11 }}
                axisLine={false}
                allowDecimals={false}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#111827",
                  border: "1px solid #1e293b",
                  borderRadius: "8px",
                  fontSize: "12px",
                }}
                labelStyle={{ color: "#94a3b8" }}
              />
              <Area
                type="monotone"
                dataKey="total"
                stroke="#3b82f6"
                fillOpacity={1}
                fill="url(#colorTotal)"
                name="Total"
              />
              <Area
                type="monotone"
                dataKey="fixed"
                stroke="#22c55e"
                fillOpacity={1}
                fill="url(#colorFixed)"
                name="Fixed"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
