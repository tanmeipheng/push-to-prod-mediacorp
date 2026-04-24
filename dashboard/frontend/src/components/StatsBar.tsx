"use client";

import { motion } from "framer-motion";

interface StatCardProps {
  label: string;
  value: number;
  icon: string;
  color: string;
}

export default function StatsBar({ stats }: { stats: StatCardProps[] }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {stats.map((stat, i) => (
        <motion.div
          key={stat.label}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.1 }}
          className="rounded-xl border border-card-border bg-card p-5"
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-muted text-sm font-medium">{stat.label}</span>
            <span className="text-2xl">{stat.icon}</span>
          </div>
          <p className={`text-3xl font-bold ${stat.color}`}>{stat.value}</p>
        </motion.div>
      ))}
    </div>
  );
}
