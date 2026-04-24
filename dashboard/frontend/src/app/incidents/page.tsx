"use client";

import { useEffect, useState, useCallback } from "react";
import { fetchIncidents, fetchIncident, type Incident } from "@/lib/api";
import IncidentCard from "@/components/IncidentCard";
import IncidentDetail from "@/components/IncidentDetail";
import Link from "next/link";

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedIncident, setSelectedIncident] = useState<(Incident & { events?: Array<{ node: string; event_type: string; data: string | null; created_at: string }> }) | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [faultFilter, setFaultFilter] = useState<string>("");

  const loadIncidents = useCallback(async () => {
    try {
      const data = await fetchIncidents({
        limit: 100,
        status: statusFilter || undefined,
        fault_type: faultFilter || undefined,
      });
      setIncidents(data);
    } catch {
      // Backend not available
    }
  }, [statusFilter, faultFilter]);

  useEffect(() => {
    loadIncidents();
  }, [loadIncidents]);

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
            <span className="text-xl font-bold text-white">🚨 TFAH (Transient Fault Auto-healer)</span>
            <span className="text-sm text-muted">Incident History</span>
          </div>
          <nav className="flex items-center gap-6">
            <Link href="/" className="text-sm text-muted hover:text-white transition-colors">Dashboard</Link>
            <Link href="/incidents" className="text-sm text-white font-medium">Incidents</Link>
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 space-y-6">
        {/* Filters */}
        <div className="flex gap-4 flex-wrap">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-card border border-card-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
          >
            <option value="">All Statuses</option>
            <option value="completed">Completed</option>
            <option value="skipped">Skipped</option>
            <option value="error">Error</option>
            <option value="running">Running</option>
          </select>

          <select
            value={faultFilter}
            onChange={(e) => setFaultFilter(e.target.value)}
            className="bg-card border border-card-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
          >
            <option value="">All Fault Types</option>
            <option value="rate_limit_429">rate_limit_429</option>
            <option value="service_unavailable_503">service_unavailable_503</option>
            <option value="gateway_timeout_504">gateway_timeout_504</option>
            <option value="connection_timeout">connection_timeout</option>
            <option value="database_deadlock">database_deadlock</option>
            <option value="unknown">unknown</option>
          </select>

          <button
            onClick={loadIncidents}
            className="px-4 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium transition-colors"
          >
            🔄 Refresh
          </button>
        </div>

        {/* Incident List */}
        <div className="space-y-2">
          {incidents.length === 0 ? (
            <div className="text-center py-20 text-muted text-sm">
              No incidents found matching the filters.
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
