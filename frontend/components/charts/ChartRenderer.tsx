"use client";

import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, AreaChart, Area,
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

const TOOLTIP_STYLE = {
  contentStyle: {
    background: "#242638",
    border: "1px solid #2e3048",
    borderRadius: 12,
    boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
  },
  labelStyle: { color: "#a0a3b8", fontSize: 12 },
};

export function ChartRenderer({ chartHint, data }: Props) {
  if (!data || data.length === 0) return null;

  const keys = Object.keys(data[0]);

  // ── KPI cards ──────────────────────────────────────────────────────────────
  if (chartHint === "kpi_cards") {
    const row = data[0];
    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mt-3">
        {keys.map((k) => (
          <KpiCard key={k} label={k.replace(/_/g, " ")} value={formatValue(row[k])} />
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
      <div className="mt-3 rounded-xl border p-4" style={{ background: "#1a1c2e", borderColor: "#2e3048" }}>
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
            <defs>
              {numericKeys.map((k, i) => (
                <linearGradient key={k} id={`grad-${i}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={i === 0 ? "#41bfec" : "#7dd3f0"} stopOpacity={0.2} />
                  <stop offset="100%" stopColor={i === 0 ? "#41bfec" : "#7dd3f0"} stopOpacity={0} />
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#2e3048" vertical={false} />
            <XAxis dataKey={dateKey} tick={{ fill: "#6b6f8a", fontSize: 10 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: "#6b6f8a", fontSize: 10 }} axisLine={false} tickLine={false} width={44} />
            <Tooltip {...TOOLTIP_STYLE} />
            {numericKeys.map((k, i) => (
              <Area
                key={k}
                type="monotone"
                dataKey={k}
                stroke={i === 0 ? "#41bfec" : "#7dd3f0"}
                strokeWidth={2}
                fill={`url(#grad-${i})`}
                dot={false}
                activeDot={{ r: 4, fill: i === 0 ? "#41bfec" : "#7dd3f0" }}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    );
  }

  // ── Bar chart ──────────────────────────────────────────────────────────────
  if (chartHint === "bar_chart") {
    const catKey = keys.find((k) => !isNumeric(data[0][k])) || keys[0];
    const numericKeys = keys.filter((k) => k !== catKey && isNumeric(data[0][k]));

    return (
      <div className="mt-3 rounded-xl border p-4" style={{ background: "#1a1c2e", borderColor: "#2e3048" }}>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 4 }} barSize={28}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2e3048" vertical={false} />
            <XAxis dataKey={catKey} tick={{ fill: "#6b6f8a", fontSize: 10 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: "#6b6f8a", fontSize: 10 }} axisLine={false} tickLine={false} width={44} />
            <Tooltip {...TOOLTIP_STYLE} />
            {numericKeys.slice(0, 2).map((k, i) => (
              <Bar key={k} dataKey={k} radius={[4, 4, 0, 0]}>
                {data.map((_, j) => (
                  <Cell key={j} fill={i === 0 ? `rgba(65,191,236,${1 - j * 0.08})` : `rgba(125,211,240,${1 - j * 0.08})`} />
                ))}
              </Bar>
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  // ── Table ──────────────────────────────────────────────────────────────────
  return (
    <div className="mt-3 rounded-xl border overflow-auto max-h-64" style={{ borderColor: "#2e3048" }}>
      <Table>
        <TableHeader>
          <TableRow style={{ borderColor: "#2e3048" }}>
            {keys.map((k) => (
              <TableHead key={k} className="text-xs py-2" style={{ color: "#6b6f8a" }}>
                {k.replace(/_/g, " ")}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.slice(0, 50).map((row, i) => (
            <TableRow key={i} style={{ borderColor: "#2e3048" }}>
              {keys.map((k) => (
                <TableCell key={k} className="text-sm py-2" style={{ color: "#a0a3b8" }}>
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
