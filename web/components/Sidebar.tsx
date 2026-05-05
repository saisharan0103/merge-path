"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV: { href: string; label: string }[] = [
  { href: "/", label: "Dashboard" },
  { href: "/repos", label: "Repos" },
  { href: "/scores", label: "Scores" },
  { href: "/issues", label: "Issues" },
  { href: "/prs", label: "PRs" },
  { href: "/strategy", label: "Strategy" },
  { href: "/activity", label: "Activity" },
  { href: "/settings", label: "Settings" },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-56 bg-cream border-r border-edge px-4 py-6 sticky top-0 h-screen">
      <div className="mb-8">
        <h2 className="font-serif text-xl text-ink">PatchPilot</h2>
        <p className="text-xs text-gray-600 mt-1">Autonomous OSS agent</p>
      </div>
      <nav className="flex flex-col gap-1 text-sm">
        {NAV.map((n) => {
          const active = n.href === "/" ? pathname === "/" : pathname?.startsWith(n.href);
          return (
            <Link
              key={n.href}
              href={n.href}
              className={`px-3 py-2 rounded-sm border ${
                active ? "border-ink bg-ink text-cream" : "border-transparent hover:bg-edge/40"
              }`}
            >
              {n.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
