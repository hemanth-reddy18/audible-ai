"use client";

import React, { ReactNode } from "react";

export interface LiquidGlassCardProps {
  children: ReactNode;
  title?: string;
  subtitle?: string;
  badge?: string;
  className?: string;
  onClick?: () => void;
}

export function LiquidGlassCard({
  children,
  title,
  subtitle,
  badge,
  className = "",
  onClick,
}: LiquidGlassCardProps) {
  return (
    <div
      onClick={onClick}
      className={`liquid-glass-card p-6 border border-white/10 transition-all duration-300 ${
        onClick ? "cursor-pointer" : ""
      } ${className}`}
    >
      {(title || badge) && (
        <div className="flex items-center justify-between pb-3 mb-4 border-b border-white/5">
          <div>
            {title && (
              <h3 className="text-base font-semibold text-zinc-100 tracking-tight">
                {title}
              </h3>
            )}
            {subtitle && (
              <p className="text-xs text-zinc-400 mt-0.5">{subtitle}</p>
            )}
          </div>
          {badge && (
            <span className="text-[10px] font-medium tracking-wide uppercase px-2 py-0.5 rounded-full border border-sky-400/30 bg-sky-500/10 text-sky-400">
              {badge}
            </span>
          )}
        </div>
      )}
      {children}
    </div>
  );
}
