"use client";

import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { KpiCard } from "./KpiCard";

interface Props {
  chartHint: "line_chart" | "bar_chart" | "kpi_cards" | "table" | "none";
  data: Record<string, unknown>[];
}

function formatValue(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "number") return v.toLocaleString();
  return String(v);
}

function isNumeric(v: unknown): boolean {
  return typeof v === "number";
}

export function ChartRenderer({ chartHint, data }: Props) {
  if (!data || data.length === 0) return null;

  const keys = Object.keys(data[0]);

  // ── KPI cards ──────────────────────────────────────────────────────────────
  if (chartHint === "kpi_cards") {
    const row = data[0];
    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mt-3">
        {keys.map((k) => (
          <KpiCard
            key={k}
            label={k.replace(/_/g, " ")}
            value={formatValue(row[k])}
          />
        ))}
      </div>
    );
  }

  // ── Line chart ─────────────────────────────────────────────────────────────
  if (chartHint === "line_chart") {
    const dateKey = keys.find((k) =>
      ["date", "month", "week", "day", "period"].some((w) => k.toLowerCase().includes(w))
    ) || keys[0];
    const numericKeys = keys.filter((k) => k !== dateKey && isNumeric(data[0][k]));

    return (
      <div className="mt-3 rounded-lg bg-zinc-900/50 border border-zinc-800 p-4">
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={data} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
            <XAxis dataKey={dateKey} tick={{ fill: "#71717a", fontSize: 10 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: "#71717a", fontSize: 10 }} axisLine={false} tickLine={false} width={48} />
            <Tooltip
              contentStyle={{ background: "#18181b", border: "1px solid #27272a", borderRadius: 6 }}
              labelStyle={{ color: "#a1a1aa" }}
            />
            {numericKeys.map((k, i) => (
              <Line
                key={k}
                type="monotone"
                dataKey={k}
                stroke={i === 0 ? "#3b82f6" : "#10b981"}
                strokeWidth={2}
                dot={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  }

  // ── Bar chart ──────────────────────────────────────────────────────────────
  if (chartHint === "bar_chart") {
    const catKey = keys.find((k) => !isNumeric(data[0][k])) || keys[0];
    const numericKeys = keys.filter((k) => k !== catKey && isNumeric(data[0][k]));

    return (
      <div className="mt-3 rounded-lg bg-zinc-900/50 border border-zinc-800 p-4">
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
            <XAxis dataKey={catKey} tick={{ fill: "#71717a", fontSize: 10 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: "#71717a", fontSize: 10 }} axisLine={false} tickLine={false} width={48} />
            <Tooltip
              contentStyle={{ background: "#18181b", border: "1px solid #27272a", borderRadius: 6 }}
              labelStyle={{ color: "#a1a1aa" }}
            />
            {numericKeys.slice(0, 2).map((k, i) => (
              <Bar key={k} dataKey={k} fill={i === 0 ? "#3b82f6" : "#10b981"} radius={[3, 3, 0, 0]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  // ── Table ──────────────────────────────────────────────────────────────────
  return (
    <div className="mt-3 rounded-lg border border-zinc-800 overflow-auto max-h-64">
      <Table>
        <TableHeader>
          <TableRow className="border-zinc-800">
            {keys.map((k) => (
              <TableHead key={k} className="text-zinc-400 text-xs py-2">
                {k.replace(/_/g, " ")}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.slice(0, 50).map((row, i) => (
            <TableRow key={i} className="border-zinc-800">
              {keys.map((k) => (
                <TableCell key={k} className="text-zinc-300 text-sm py-2">
                  {formatValue(row[k])}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
