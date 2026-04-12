"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Projections" },
  { href: "/rankings", label: "Rankings" },
  { href: "/draft", label: "Draft Assistant" },
];

export default function Nav() {
  const pathname = usePathname();

  return (
    <nav className="border-b border-card-border bg-card">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-14 items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-lg font-bold text-accent">FF</span>
            <span className="text-lg font-semibold">Projections</span>
          </div>
          <div className="flex gap-1">
            {links.map((link) => {
              const isActive =
                link.href === "/"
                  ? pathname === "/"
                  : pathname.startsWith(link.href);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-accent/15 text-accent"
                      : "text-muted hover:bg-card-border/50 hover:text-foreground"
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
          </div>
        </div>
      </div>
    </nav>
  );
}
