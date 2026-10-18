"use client";

import { Loader2, Sparkles } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { loginApiV1AuthLoginPost } from "@/client/sdk.gen";
import { AuthEnterpriseCTA } from "@/components/auth/AuthEnterpriseCTA";
import { AuthShell } from "@/components/auth/AuthShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function LoginForm({ signupEnabled }: { signupEnabled: boolean }) {
  const searchParams = useSearchParams();
  const isManual = searchParams.get("manual") === "true";

  // Pre-fill default dev administrator credentials
  const [email, setEmail] = useState("ceo@audible.ai");
  const [password, setPassword] = useState("Audible2026!");
  const [loading, setLoading] = useState(false);
  const autoLoginTriggeredRef = useRef(false);

  const performLogin = async (loginEmail: string, loginPass: string) => {
    setLoading(true);
    try {
      const res = await loginApiV1AuthLoginPost({
        body: { email: loginEmail, password: loginPass },
      });

      if (res.error || !res.data) {
        const detail = (res.error as { detail?: string })?.detail;
        toast.error(detail || "Login failed");
        return;
      }

      // Set httpOnly cookies via server route
      await fetch("/api/auth/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: res.data.token, user: res.data.user }),
      });

      toast.success("Welcome to Audible AI");
      window.location.href = "/";
    } catch {
      toast.error("An error occurred during authentication. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await performLogin(email, password);
  };

  const handleQuickAutoLogin = async () => {
    setEmail("ceo@audible.ai");
    setPassword("Audible2026!");
    await performLogin("ceo@audible.ai", "Audible2026!");
  };

  // Trigger auto-login on mount unless ?manual=true is specified
  useEffect(() => {
    if (!isManual && !autoLoginTriggeredRef.current) {
      autoLoginTriggeredRef.current = true;
      void performLogin("ceo@audible.ai", "Audible2026!");
    }
  }, [isManual]);

  return (
    <AuthShell enterpriseSlot={<AuthEnterpriseCTA />}>
      <div className="space-y-1.5 text-center">
        <h1 className="text-2xl font-semibold tracking-tight">Sign in to Audible AI</h1>
        <p className="text-sm text-muted-foreground">
          Local autonomous voice agent development platform
        </p>
      </div>

      <div className="p-3 bg-indigo-950/30 border border-indigo-500/20 rounded-lg text-xs text-indigo-300 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Sparkles className="h-4 w-4 text-indigo-400 shrink-0" />
          <span>Local dev credentials pre-filled</span>
        </div>
        <Button
          type="button"
          size="sm"
          variant="secondary"
          onClick={handleQuickAutoLogin}
          disabled={loading}
          className="h-7 text-xs bg-indigo-600 hover:bg-indigo-500 text-white border-0 shadow-sm"
        >
          {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : "⚡ One-Click Login"}
        </Button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="font-mono text-sm"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            placeholder="Enter your password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="font-mono text-sm"
          />
        </div>
        <Button type="submit" className="w-full bg-slate-100 text-slate-900 hover:bg-white" disabled={loading}>
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Signing in...
            </>
          ) : (
            "Sign In"
          )}
        </Button>
      </form>

      {signupEnabled && (
        <p className="text-center text-sm text-muted-foreground">
          Don&apos;t have an account?{" "}
          <Link href="/auth/signup" className="text-primary underline-offset-4 hover:underline">
            Sign up
          </Link>
        </p>
      )}
    </AuthShell>
  );
}
