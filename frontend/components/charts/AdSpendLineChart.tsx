"use client";

import {
  ComposedChart, Line, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";

interface DailyRow {
  date: string;
  spend: number;
  leads: number;
  cpl: number | null;
}

export function AdSpendLineChart({ data }: { data: DailyRow[] }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#2e3048" vertical={false} />
        <XAxis dataKey="date" tick={{ fill: "#6b6f8a", fontSize: 10 }} axisLine={false} tickLine={false} />
        <YAxis yAxisId="left" tick={{ fill: "#6b6f8a", fontSize: 10 }} axisLine={false} tickLine={false} width={44} />
        <YAxis yAxisId="right" orientation="right" tick={{ fill: "#6b6f8a", fontSize: 10 }} axisLine={false} tickLine={false} width={44} />
        <Tooltip
          contentStyle={{ background: "#242638", border: "1px solid #2e3048", borderRadius: 12, boxShadow: "0 8px 24px rgba(0,0,0,0.4)" }}
          labelStyle={{ color: "#a0a3b8", fontSize: 12 }}
          formatter={(v: unknown, name: unknown) => {
            const label = name === "spend" ? "Spend" : name === "cpl" ? "CPL" : "Leads";
            const val = name === "spend" ? `$${Number(v).toLocaleString()}` : name === "cpl" ? `$${v}` : String(v);
            return [val, label] as [string, string];
          }}
        />
        <Legend wrapperStyle={{ fontSize: 11, color: "#6b6f8a" }} />
        <Bar yAxisId="left" dataKey="spend" fill="rgba(65,191,236,0.2)" radius={[4, 4, 0, 0]} name="spend" />
        <Line yAxisId="right" type="monotone" dataKey="cpl" stroke="#41bfec" strokeWidth={2} dot={false} name="cpl" activeDot={{ r: 4, fill: "#41bfec" }} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
