"use client";

import React from "react";

export interface AcousticWaveformProps {
  active?: boolean;
  intensity?: number; // 0.0 to 1.0
  barsCount?: number;
  className?: string;
}

export function AcousticWaveform({
  active = false,
  intensity = 0.5,
  barsCount = 16,
  className = "",
}: AcousticWaveformProps) {
  const bars = Array.from({ length: barsCount });

  return (
    <div
      className={`flex items-center justify-center gap-1 h-12 px-4 rounded-xl liquid-glass ${className}`}
      role="status"
      aria-label={active ? "Agent audio active" : "Audio idle"}
    >
      {bars.map((_, i) => {
        const heightMultiplier = Math.sin((i / (barsCount - 1)) * Math.PI);
        const dynamicHeight = active
          ? Math.max(15, Math.min(100, (heightMultiplier * intensity * 85) + 15))
          : 15;
        const delay = (i * 0.07).toFixed(2);

        return (
          <span
            key={i}
            className="w-1 rounded-full transition-all duration-150"
            style={{
              height: `${dynamicHeight}%`,
              background: active
                ? "linear-gradient(to top, #38bdf8, #818cf8)"
                : "rgba(148, 163, 184, 0.3)",
              animation: active ? `acoustic-pulse 1.1s ease-in-out infinite` : "none",
              animationDelay: `${delay}s`,
            }}
          />
        );
      })}
    </div>
  );
}
