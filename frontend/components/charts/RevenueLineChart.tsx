"use client";

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart,
} from "recharts";

interface RevenuePoint {
  month: string;
  cash_revenue: number;
}

export function RevenueLineChart({ data }: { data: RevenuePoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
        <defs>
          <linearGradient id="revenueGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#41bfec" stopOpacity={0.2} />
            <stop offset="100%" stopColor="#41bfec" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#2e3048" vertical={false} />
        <XAxis
          dataKey="month"
          tick={{ fill: "#6b6f8a", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
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
          formatter={(v: any) => [`$${Number(v).toLocaleString()}`, "Cash Revenue"] as any}
        />
        <Area
          type="monotone"
          dataKey="cash_revenue"
          stroke="#41bfec"
          strokeWidth={2}
          fill="url(#revenueGradient)"
          dot={false}
          activeDot={{ r: 5, fill: "#41bfec", strokeWidth: 0 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
