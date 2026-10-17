"use client";

import React from "react";
import { cn } from "@/lib/utils";

export interface BrandLogoProps {
  className?: string;
  inverse?: boolean;
  mark?: boolean;
}

/**
 * Audible Brand Logo — Apple-inspired vector acoustics icon & typography.
 * Supports theme switching, mark-only mode (sidebar collapsed), and full wordmark.
 */
export function BrandLogo({
  className,
  inverse = false,
  mark = false,
}: BrandLogoProps) {
  if (mark) {
    return (
      <div className={cn("flex items-center justify-center select-none", className)}>
        <svg
          viewBox="0 0 100 100"
          className="h-full w-auto aspect-square"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            <linearGradient id="audibleMarkGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#38bdf8" />
              <stop offset="50%" stopColor="#818cf8" />
              <stop offset="100%" stopColor="#c084fc" />
            </linearGradient>
            <filter id="audibleMarkGlow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>
          <circle
            cx="50"
            cy="50"
            r="44"
            stroke="url(#audibleMarkGrad)"
            strokeWidth="3"
            opacity="0.35"
            strokeDasharray="8 6"
          />
          <g filter="url(#audibleMarkGlow)" stroke="url(#audibleMarkGrad)" strokeWidth="4.5" strokeLinecap="round">
            <line x1="26" y1="42" x2="26" y2="58" opacity="0.8" />
            <line x1="38" y1="31" x2="38" y2="69" opacity="0.95" />
            <line x1="50" y1="18" x2="50" y2="82" opacity="1" />
            <line x1="62" y1="31" x2="62" y2="69" opacity="0.95" />
            <line x1="74" y1="42" x2="74" y2="58" opacity="0.8" />
          </g>
        </svg>
      </div>
    );
  }

  return (
    <div className={cn("inline-flex items-center gap-2.5 select-none", className)}>
      {/* Waveform Icon */}
      <svg
        viewBox="0 0 100 100"
        className="h-full max-h-8 w-auto aspect-square flex-shrink-0"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <linearGradient id="audibleIconGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#38bdf8" />
            <stop offset="50%" stopColor="#818cf8" />
            <stop offset="100%" stopColor="#c084fc" />
          </linearGradient>
        </defs>
        <circle
          cx="50"
          cy="50"
          r="44"
          stroke="url(#audibleIconGrad)"
          strokeWidth="3"
          opacity="0.4"
          strokeDasharray="8 6"
        />
        <g stroke="url(#audibleIconGrad)" strokeWidth="5" strokeLinecap="round">
          <line x1="26" y1="42" x2="26" y2="58" opacity="0.8" />
          <line x1="38" y1="31" x2="38" y2="69" opacity="0.95" />
          <line x1="50" y1="18" x2="50" y2="82" opacity="1" />
          <line x1="62" y1="31" x2="62" y2="69" opacity="0.95" />
          <line x1="74" y1="42" x2="74" y2="58" opacity="0.8" />
        </g>
      </svg>

      {/* Typography */}
      <div className="flex items-center gap-1.5 leading-none">
        <span
          className={cn(
            "font-extrabold tracking-wider text-lg uppercase transition-colors",
            inverse
              ? "text-zinc-50"
              : "text-zinc-900 dark:text-zinc-50"
          )}
          style={{ letterSpacing: "0.09em" }}
        >
          Audible
        </span>
        <span className="rounded bg-sky-500/15 border border-sky-500/30 px-1.5 py-0.5 text-[9px] font-bold text-sky-400 tracking-wider">
          AI
        </span>
      </div>
    </div>
  );
}
