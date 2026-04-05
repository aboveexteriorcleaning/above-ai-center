"use client";

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from "recharts";

interface ServiceRow {
  service_type: string;
  revenue: number;
  job_count: number;
}

export function ServiceBarChart({ data }: { data: ServiceRow[] }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 4 }} barSize={32}>
        <CartesianGrid strokeDasharray="3 3" stroke="#2e3048" vertical={false} />
        <XAxis
          dataKey="service_type"
          tick={{ fill: "#6b6f8a", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => v.replace(/_/g, " ")}
        />
        <YAxis
          tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
          tick={{ fill: "#6b6f8a", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={44}
        />
        <Tooltip
          contentStyle={{
            background: "#242638",
            border: "1px solid #2e3048",
            borderRadius: 12,
            boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
          }}
          labelStyle={{ color: "#a0a3b8", fontSize: 12 }}
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          formatter={(v: any, name: any) => [
            name === "revenue" ? `$${Number(v).toLocaleString()}` : v,
            name === "revenue" ? "Revenue" : "Jobs",
          ] as any}
        />
        <Bar dataKey="revenue" radius={[6, 6, 0, 0]}>
          {data.map((_, i) => (
            <Cell
              key={i}
              fill={i === 0 ? "#41bfec" : `rgba(65,191,236,${0.7 - i * 0.12})`}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
