"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase";

const NAV = [
  { href: "/dashboard", label: "Overview", exact: true },
  { href: "/dashboard/ads", label: "Ads" },
  { href: "/dashboard/jobs", label: "Jobs" },
  { href: "/dashboard/leads", label: "Leads" },
  { href: "/dashboard/chat", label: "Chat" },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  async function handleLogout() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
    router.refresh();
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ background: "#1a1c2e" }}>
      {/* Top nav */}
      <header
        className="sticky top-0 z-50 border-b px-6 py-0 flex items-center justify-between"
        style={{
          background: "rgba(26,28,46,0.85)",
          backdropFilter: "blur(12px)",
          borderColor: "#2e3048",
          height: "56px",
        }}
      >
        <div className="flex items-center gap-8">
          {/* Logo */}
          <div className="flex items-center gap-2">
            <div
              className="w-7 h-7 rounded-lg flex items-center justify-center"
              style={{ background: "linear-gradient(135deg, #41bfec, #2a9fd6)" }}
            >
              <span className="text-xs font-bold" style={{ color: "#1a1c2e" }}>A</span>
            </div>
            <span className="font-semibold text-sm tracking-tight" style={{ color: "#f0f1f6" }}>
              Above AI Center
            </span>
          </div>

          {/* Nav links */}
          <nav className="flex gap-1">
            {NAV.map(({ href, label, exact }) => {
              const active = exact ? pathname === href : pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className="px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-150"
                  style={
                    active
                      ? {
                          background: "rgba(65,191,236,0.12)",
                          color: "#41bfec",
                        }
                      : {
                          color: "#6b6f8a",
                        }
                  }
                  onMouseEnter={(e) => {
                    if (!active) {
                      (e.target as HTMLElement).style.color = "#a0a3b8";
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!active) {
                      (e.target as HTMLElement).style.color = "#6b6f8a";
                    }
                  }}
                >
                  {label}
                </Link>
              );
            })}
          </nav>
        </div>

        <button
          onClick={handleLogout}
          className="text-xs transition-colors px-3 py-1.5 rounded-lg"
          style={{ color: "#6b6f8a" }}
          onMouseEnter={(e) => ((e.target as HTMLElement).style.color = "#a0a3b8")}
          onMouseLeave={(e) => ((e.target as HTMLElement).style.color = "#6b6f8a")}
        >
          Sign out
        </button>
      </header>

      {/* Page content */}
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
