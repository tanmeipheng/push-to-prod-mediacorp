"use client";

import { useEffect, useState, useCallback } from "react";
import { fetchStats, fetchIncidents, fetchTimeline, type Incident } from "@/lib/api";
import { usePipelineState } from "@/lib/sse";
import StatsBar from "@/components/StatsBar";
import PipelineGraph from "@/components/PipelineGraph";
import TriggerPanel from "@/components/TriggerPanel";
import IncidentCard from "@/components/IncidentCard";
import TimelineChart from "@/components/TimelineChart";
import IncidentDetail from "@/components/IncidentDetail";
import { fetchIncident } from "@/lib/api";
import Link from "next/link";

interface Stats {
  total: number;
  fixed: number;
  skipped: number;
  errored: number;
  running: number;
  prs_opened: number;
}

interface TimelineDay {
  day: string;
  total: number;
  fixed: number;
  skipped: number;
  errored: number;
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats>({
    total: 0, fixed: 0, skipped: 0, errored: 0, running: 0, prs_opened: 0,
  });
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [timeline, setTimeline] = useState<TimelineDay[]>([]);
  const [selectedIncident, setSelectedIncident] = useState<(Incident & { events?: Array<{ node: string; event_type: string; data: string | null; created_at: string }> }) | null>(null);
  const [timelineCollapsed, setTimelineCollapsed] = useState(false);
  const { nodes, slackStages, lastEvent } = usePipelineState();

  const loadData = useCallback(async () => {
    try {
      const [s, inc, tl] = await Promise.all([
        fetchStats(),
        fetchIncidents({ limit: 10 }),
        fetchTimeline(7),
      ]);
      setStats(s);
      setIncidents(inc);

      // Aggregate timeline by day
      const byDay: Record<string, TimelineDay> = {};
      tl.forEach((row) => {
        if (!byDay[row.day]) {
          byDay[row.day] = { day: row.day, total: 0, fixed: 0, skipped: 0, errored: 0 };
        }
        byDay[row.day].total += row.count;
        if (row.status === "completed") byDay[row.day].fixed += row.count;
        if (row.status === "skipped") byDay[row.day].skipped += row.count;
        if (row.status === "error") byDay[row.day].errored += row.count;
      });
      setTimeline(Object.values(byDay).sort((a, b) => a.day.localeCompare(b.day)));
    } catch {
      // Backend not available yet
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Refresh data when pipeline events fire
  useEffect(() => {
    if (lastEvent?.event === "pipeline_done" || lastEvent?.event === "pipeline_error") {
      loadData();
    }
  }, [lastEvent, loadData]);

  const handleIncidentClick = async (id: number) => {
    try {
      const detail = await fetchIncident(id);
      setSelectedIncident(detail);
    } catch {
      // ignore
    }
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Nav */}
      <header className="border-b border-card-border bg-card/50 backdrop-blur-sm sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-xl font-bold text-white">🚨 TFAH</span>
            <span className="text-sm text-muted">Command Center</span>
          </div>
          <nav className="flex items-center gap-6">
            <Link href="/" className="text-sm text-white font-medium">Dashboard</Link>
            <Link href="/incidents" className="text-sm text-muted hover:text-white transition-colors">Incidents</Link>
            <div className="flex items-center gap-2 text-xs">
              <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              <span className="text-muted">System OK</span>
            </div>
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 space-y-8">
        {/* Stats */}
        <StatsBar
          stats={[
            { label: "Total Incidents", value: stats.total, icon: "📊", color: "text-white" },
            { label: "Auto-Fixed", value: stats.fixed, icon: "✅", color: "text-accent-green" },
            { label: "Skipped", value: stats.skipped, icon: "⏭", color: "text-accent-yellow" },
            { label: "PRs Opened", value: stats.prs_opened, icon: "📦", color: "text-accent-purple" },
          ]}
        />

        {/* Timeline + Pipeline in a flexible layout */}
        <div className="flex gap-6">
          <div className={`transition-all duration-300 ease-in-out ${
            timelineCollapsed ? "w-10 flex-shrink-0" : "w-1/2 flex-shrink-0"
          }`}>
            <TimelineChart data={timeline} collapsed={timelineCollapsed} onToggle={() => setTimelineCollapsed(c => !c)} />
          </div>
          <div className="flex-1 min-w-0 space-y-4">
            <h3 className="text-sm font-semibold text-muted uppercase tracking-wider">
              Pipeline Status
            </h3>
            <PipelineGraph nodeStates={nodes} slackStages={slackStages} />
          </div>
        </div>

        {/* Trigger Panel */}
        <TriggerPanel onPipelineStarted={loadData} />

        {/* Recent Incidents */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-muted uppercase tracking-wider">
              Recent Incidents
            </h3>
            <Link
              href="/incidents"
              className="text-xs text-accent-blue hover:text-blue-400 transition-colors"
            >
              View All →
            </Link>
          </div>
          <div className="space-y-2">
            {incidents.length === 0 ? (
              <div className="text-center py-12 text-muted text-sm">
                No incidents yet. Run the pipeline to get started.
              </div>
            ) : (
              incidents.map((inc) => (
                <IncidentCard
                  key={inc.id}
                  incident={inc}
                  onClick={() => handleIncidentClick(inc.id)}
                />
              ))
            )}
          </div>
        </div>
      </main>

      {/* Incident Detail Drawer */}
      {selectedIncident && (
        <>
          <div
            className="fixed inset-0 bg-black/50 z-40"
            onClick={() => setSelectedIncident(null)}
          />
          <IncidentDetail
            incident={selectedIncident}
            onClose={() => setSelectedIncident(null)}
          />
        </>
      )}
    </div>
  );
}
