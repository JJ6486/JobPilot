"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { ThemeToggle } from "@/components/theme-toggle";
import { cn } from "@/lib/utils";

const links = [
  { href: "/", label: "Dashboard" },
  { href: "/analyze", label: "Analyze" },
  { href: "/applications", label: "Applications" },
  { href: "/analytics", label: "Analytics" },
  { href: "/truth-bank", label: "Truth bank" },
  { href: "/settings", label: "Settings" },
];

export function SiteNav() {
  const pathname = usePathname();

  return (
    <header className="border-b">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4">
        <Link href="/" className="font-semibold">
          JobPilot
        </Link>
        <nav className="flex flex-1 gap-1 overflow-x-auto text-sm">
          {links.map((link) => {
            const active = link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  "rounded-md px-3 py-1.5 whitespace-nowrap text-muted-foreground hover:text-foreground",
                  active && "bg-muted text-foreground",
                )}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>
        <ThemeToggle />
      </div>
    </header>
  );
}
