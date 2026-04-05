interface KpiCardProps {
  label: string;
  value: string | number | null | undefined;
  prefix?: string;
  suffix?: string;
  sublabel?: string;
  accent?: boolean;
}

export function KpiCard({ label, value, prefix = "", suffix = "", sublabel, accent }: KpiCardProps) {
  const display = value == null ? "—" : `${prefix}${value}${suffix}`;

  return (
    <div
      className="rounded-2xl p-5 border transition-all duration-200 group cursor-default"
      style={{
        background: accent ? "linear-gradient(135deg, rgba(65,191,236,0.12), rgba(65,191,236,0.05))" : "#242638",
        borderColor: accent ? "rgba(65,191,236,0.3)" : "#2e3048",
        boxShadow: accent ? "0 4px 24px rgba(65,191,236,0.08)" : "none",
      }}
    >
      <p
        className="text-xs font-medium uppercase tracking-widest mb-3"
        style={{ color: "#6b6f8a", letterSpacing: "0.08em" }}
      >
        {label}
      </p>
      <p
        className="text-2xl font-semibold tracking-tight"
        style={{ color: accent ? "#41bfec" : "#f0f1f6" }}
      >
        {display}
      </p>
      {sublabel && (
        <p className="text-xs mt-1.5" style={{ color: "#6b6f8a" }}>
          {sublabel}
        </p>
      )}
    </div>
  );
}
