// Shared dark two-column auth shell for Audible AI.
// LEFT: a centered glass card that wraps the auth form (`children`).
// RIGHT (lg+ only): a liquid-glass brand panel with Audible identity, acoustic motifs, and architecture highlights.

import type { ReactNode } from "react";
import { BrandLogo } from "@/components/BrandLogo";

const HIGHLIGHTS = [
  "Speech-to-Speech",
  "Sub-300ms Barge-in",
  "MCP Tool Protocol",
  "Zero-Lockin BYOK",
];

export function AuthShell({
  children,
  enterpriseSlot,
}: {
  children: ReactNode;
  enterpriseSlot?: ReactNode;
}) {
  return (
    <div className="grid min-h-screen w-full bg-background lg:grid-cols-[55%_45%]">
      {/* Form column (LEFT) */}
      <main className="auth-imprint flex min-h-screen flex-col overflow-y-auto">
        <div className="flex min-h-full items-center justify-center p-6 sm:p-10">
          <div className="w-full max-w-md space-y-6 rounded-2xl border border-white/10 bg-card/80 backdrop-blur-xl p-6 shadow-2xl sm:p-8">
            {/* Mobile-only wordmark */}
            <div className="lg:hidden flex justify-center pb-2">
              <BrandLogo className="h-7" />
            </div>
            {children}
          </div>
        </div>
      </main>

      {/* Brand / value panel (RIGHT) — hidden on mobile */}
      <aside className="relative hidden flex-col justify-between overflow-hidden border-l border-white/10 bg-zinc-950 p-10 lg:flex xl:p-14">
        {/* Ambient liquid depth: soft radial glow behind the content */}
        <div
          aria-hidden
          className="pointer-events-none absolute -right-24 top-1/3 size-[32rem] rounded-full opacity-25 blur-3xl"
          style={{ background: "radial-gradient(circle, #38bdf8, #818cf8, transparent 70%)" }}
        />

        <div className="relative">
          <BrandLogo inverse className="h-8" />
        </div>

        <div className="relative max-w-md space-y-5">
          <div className="inline-flex items-center gap-2 rounded-full border border-sky-400/20 bg-sky-500/10 px-3 py-1 text-xs font-semibold text-sky-400">
            <span className="size-2 rounded-full bg-sky-400 animate-pulse" />
            AUDIBLE NEXT-GEN VOICE RUNTIME
          </div>
          <h1 className="text-3xl font-semibold leading-tight tracking-tight text-zinc-50 xl:text-4xl">
            Sovereign voice intelligence for autonomous agents.
          </h1>
          <p className="text-sm text-zinc-400 leading-relaxed">
            Ultra-low latency conversational agents powered by real-time speech-to-speech, bi-directional interruption, and adaptive tool calling.
          </p>
          <ul className="flex flex-wrap gap-2 pt-2">
            {HIGHLIGHTS.map((point) => (
              <li
                key={point}
                className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-medium text-zinc-300 backdrop-blur-md"
              >
                {point}
              </li>
            ))}
          </ul>
        </div>

        {/* Enterprise CTA block */}
        <div className="relative mb-12 max-w-md space-y-3 rounded-2xl border border-white/10 bg-white/[0.03] p-5 xl:mb-16 backdrop-blur-xl">
          <h2 className="text-sm font-semibold text-zinc-100">
            Enterprise &amp; On-Premise Deployments
          </h2>
          <p className="text-sm text-zinc-400">
            Deploy Audible securely inside your private cloud or isolated VPC with full data perimeter compliance.
          </p>
          {enterpriseSlot}
        </div>
      </aside>
    </div>
  );
}
