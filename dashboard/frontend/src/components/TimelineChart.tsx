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
}: {
  data: TimelineDataPoint[];
}) {
  if (data.length === 0) {
    return (
      <div className="rounded-xl border border-card-border bg-card p-8 text-center text-muted text-sm">
        No incident data yet. Run the pipeline to see activity here.
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-card-border bg-card p-4">
      <h3 className="text-sm font-semibold text-muted uppercase tracking-wider mb-4">
        Incident Timeline (7 days)
      </h3>
      <ResponsiveContainer width="100%" height={180}>
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
            tickFormatter={(v: string) => v.slice(5)} // MM-DD
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
  );
}
