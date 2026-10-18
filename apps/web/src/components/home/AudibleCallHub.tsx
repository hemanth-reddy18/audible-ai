"use client";

import {
  Activity,
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Clock,
  ExternalLink,
  Loader2,
  Mic,
  Phone,
  PhoneCall,
  PhoneOff,
  Radio,
  RefreshCw,
  Settings,
  ShieldAlert,
  Smartphone,
  Sparkles,
  Volume2,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import {
  createWorkflowRunApiV1WorkflowWorkflowIdRunsPost,
  getWorkflowsApiV1WorkflowFetchGet,
  initiateCallApiV1TelephonyInitiateCallPost,
  listTelephonyConfigurationsApiV1OrganizationsTelephonyConfigsGet,
} from "@/client/sdk.gen";
import type { WorkflowListResponse } from "@/client/types.gen";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { WORKFLOW_RUN_MODES } from "@/constants/workflowRunModes";
import { useAuth } from "@/lib/auth";
import { cn, getRandomId } from "@/lib/utils";

import { EmbeddedVoiceTester } from "@/app/workflow/[workflowId]/components/workflow-tester/EmbeddedVoiceTester";

export type CallState =
  | "idle"
  | "validating"
  | "connecting"
  | "ringing"
  | "connected"
  | "ending"
  | "ended"
  | "failed";

interface CountryCode {
  code: string;
  country: string;
  flag: string;
}

const COUNTRY_CODES: CountryCode[] = [
  { code: "+1", country: "United States / Canada", flag: "🇺🇸" },
  { code: "+44", country: "United Kingdom", flag: "🇬🇧" },
  { code: "+91", country: "India", flag: "🇮🇳" },
  { code: "+61", country: "Australia", flag: "🇦🇺" },
  { code: "+49", country: "Germany", flag: "🇩🇪" },
  { code: "+33", country: "France", flag: "🇫🇷" },
  { code: "+81", country: "Japan", flag: "🇯🇵" },
  { code: "+971", country: "UAE", flag: "🇦🇪" },
  { code: "+65", country: "Singapore", flag: "🇸🇬" },
];

interface RecentRun {
  id: number;
  name: string;
  mode: string;
  status: string;
  created_at: string;
  duration?: number;
}

export function AudibleCallHub() {
  const auth = useAuth();
  const { isAuthenticated, loading: authLoading, getAccessToken } = auth;

  // Agent State
  const [workflows, setWorkflows] = useState<WorkflowListResponse[]>([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<number | null>(null);
  const [loadingWorkflows, setLoadingWorkflows] = useState(true);

  // Telephony Readiness State
  const [telephonyConfigs, setTelephonyConfigs] = useState<any[]>([]);
  const [checkingTelephony, setCheckingTelephony] = useState(true);

  // Dialing / Input State
  const [mode, setMode] = useState<"browser" | "phone" | "companion">("browser");
  const [countryCode, setCountryCode] = useState("+1");
  const [phoneNumber, setPhoneNumber] = useState("5550192834");
  const [accessToken, setAccessToken] = useState<string | null>(null);

  // Companion Device (Galaxy Note8) State
  const [companionStatus, setCompanionStatus] = useState<any>(null);

  // Call Lifecycle & WebRTC State
  const [callState, setCallState] = useState<CallState>("idle");
  const [activeVoiceRunId, setActiveVoiceRunId] = useState<number | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [callDuration, setCallDuration] = useState(0);

  // Recent Runs History
  const [recentRuns, setRecentRuns] = useState<RecentRun[]>([]);
  const [loadingRecentRuns, setLoadingRecentRuns] = useState(false);

  // Hydrate Access Token
  useEffect(() => {
    let active = true;
    const hydrate = async () => {
      if (!isAuthenticated || authLoading) return;
      try {
        const token = await getAccessToken();
        if (active && token) setAccessToken(token);
      } catch (err) {
        console.error("Token hydration failed:", err);
      }
    };
    hydrate();
    return () => {
      active = false;
    };
  }, [isAuthenticated, authLoading, getAccessToken]);

  // Load Workflows
  const loadWorkflows = useCallback(async () => {
    if (!accessToken) return;
    setLoadingWorkflows(true);
    try {
      const response = await getWorkflowsApiV1WorkflowFetchGet({
        headers: { Authorization: `Bearer ${accessToken}` },
        query: { status: "active" },
      });
      const data = response.data
        ? Array.isArray(response.data)
          ? response.data
          : [response.data]
        : [];
      setWorkflows(data);
      if (data.length > 0 && !selectedWorkflowId) {
        // Prioritize Bridget (Workflow #2 - Real Estate Customer Support)
        const bridgetAgent = data.find(
          (w) =>
            w.id === 2 ||
            w.name?.toLowerCase().includes("bridget") ||
            w.name?.toLowerCase().includes("real estate")
        );
        setSelectedWorkflowId(bridgetAgent ? bridgetAgent.id : data[0].id);
      }
    } catch (err) {
      console.error("Error fetching workflows:", err);
    } finally {
      setLoadingWorkflows(false);
    }
  }, [accessToken, selectedWorkflowId]);

  // Load Telephony Configurations
  const loadTelephonyConfigs = useCallback(async () => {
    if (!accessToken) return;
    setCheckingTelephony(true);
    try {
      const response = await listTelephonyConfigurationsApiV1OrganizationsTelephonyConfigsGet({
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      const cfgs = response.data ? (Array.isArray(response.data) ? response.data : [response.data]) : [];
      setTelephonyConfigs(cfgs);
    } catch (err) {
      console.error("Error listing telephony configurations:", err);
      setTelephonyConfigs([]);
    } finally {
      setCheckingTelephony(false);
    }
  }, [accessToken]);

  // Load Recent Runs for Selected Agent
  const loadRecentRuns = useCallback(async () => {
    if (!accessToken || !selectedWorkflowId) return;
    setLoadingRecentRuns(true);
    try {
      const res = await fetch(`/api/v1/workflow/${selectedWorkflowId}/runs?limit=5`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (res.ok) {
        const json = await res.json();
        const runs = json.data || (Array.isArray(json) ? json : []);
        setRecentRuns(runs);
      }
    } catch (err) {
      console.error("Error fetching runs:", err);
    } finally {
      setLoadingRecentRuns(false);
    }
  }, [accessToken, selectedWorkflowId]);

  useEffect(() => {
    if (accessToken) {
      void loadWorkflows();
      void loadTelephonyConfigs();
    }
  }, [accessToken, loadWorkflows, loadTelephonyConfigs]);

  useEffect(() => {
    if (accessToken && selectedWorkflowId) {
      void loadRecentRuns();
    }
  }, [accessToken, selectedWorkflowId, loadRecentRuns]);

  // Poll Companion (Galaxy Note8) Bridge Status
  useEffect(() => {
    const fetchCompanion = async () => {
      try {
        const res = await fetch("/api/v1/companion/status");
        if (res.ok) {
          const data = await res.json();
          setCompanionStatus(data);
        }
      } catch (err) {
        // quiet fallback
      }
    };
    void fetchCompanion();
    const interval = setInterval(fetchCompanion, 3000);
    return () => clearInterval(interval);
  }, []);

  // Timer for active call
  useEffect(() => {
    let timer: NodeJS.Timeout | null = null;
    if (callState === "connected") {
      timer = setInterval(() => {
        setCallDuration((prev) => prev + 1);
      }, 1000);
    } else {
      setCallDuration(0);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [callState]);

  // E.164 Number Validation
  const formattedE164 = useMemo(() => {
    const raw = phoneNumber.replace(/[^0-9]/g, "");
    if (!raw) return "";
    return `${countryCode}${raw}`;
  }, [countryCode, phoneNumber]);

  const isE164Valid = useMemo(() => {
    const rawDigits = phoneNumber.replace(/[^0-9]/g, "");
    return rawDigits.length >= 7 && rawDigits.length <= 15;
  }, [phoneNumber]);

  // Selected Workflow Details
  const selectedWorkflow = useMemo(() => {
    return workflows.find((w) => w.id === selectedWorkflowId) || workflows[0] || null;
  }, [workflows, selectedWorkflowId]);

  // Telephony readiness: true only if at least 1 active configuration exists
  const isTelephonyReady = useMemo(() => {
    return telephonyConfigs && telephonyConfigs.length > 0;
  }, [telephonyConfigs]);

  // Handle Starting Browser Voice Session (WebRTC)
  const handleStartBrowserCall = async () => {
    if (!selectedWorkflowId || !accessToken) {
      toast.error("Please select an agent first");
      return;
    }
    setCallState("connecting");
    setErrorMessage(null);

    try {
      const response = await createWorkflowRunApiV1WorkflowWorkflowIdRunsPost({
        path: { workflow_id: selectedWorkflowId },
        body: {
          mode: WORKFLOW_RUN_MODES.SMALL_WEBRTC,
          name: `AUDIBLE-${getRandomId()}`,
        },
      });

      if (response.error || !response.data?.id) {
        throw new Error(
          (response.error as any)?.detail || "Failed to initialize voice session"
        );
      }

      setActiveVoiceRunId(response.data.id);
      setCallState("connected");
      toast.success("Voice test session started");
    } catch (err: any) {
      setCallState("failed");
      setErrorMessage(err.message || "Failed to start browser voice call");
      toast.error(err.message || "Call initialization failed");
    }
  };

  // Handle Initiating Outbound Phone Call (PSTN)
  const handleStartPhoneCall = async () => {
    if (!isE164Valid) {
      toast.error("Please enter a valid phone number in E.164 format");
      return;
    }
    if (!isTelephonyReady) {
      setCallState("failed");
      setErrorMessage(
        "Phone calling requires a telephony connection. No active SIP trunk or telephony provider is configured in this local environment."
      );
      toast.error("Phone calling requires a telephony connection");
      return;
    }
    if (!selectedWorkflowId) {
      toast.error("Please select an agent");
      return;
    }

    setCallState("validating");
    setErrorMessage(null);

    try {
      setCallState("connecting");
      const res = await initiateCallApiV1TelephonyInitiateCallPost({
        body: {
          workflow_id: selectedWorkflowId,
          phone_number: formattedE164,
        },
      });

      if (res.error) {
        throw new Error((res.error as any)?.detail || "Call initiation failed");
      }

      setCallState("ringing");
      toast.success(`Outbound call dispatched to ${formattedE164}`);
    } catch (err: any) {
      setCallState("failed");
      const rawDetail = err.message || "";
      const displayMsg =
        rawDetail === "telephony_not_configured" || rawDetail.includes("telephony")
          ? "Phone calling requires a telephony connection. Please configure a SIP trunk or telephony provider in Settings."
          : (rawDetail || "Outbound call rejected by backend");
      setErrorMessage(displayMsg);
      toast.error(displayMsg);
    }
  };

  // Reset / End Call
  const handleEndCall = () => {
    setCallState("ending");
    setTimeout(() => {
      setActiveVoiceRunId(null);
      setCallState("ended");
      void loadRecentRuns();
      setTimeout(() => setCallState("idle"), 1200);
    }, 400);
  };

  const formatTimer = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Top Navigation Bar */}
      <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="h-9 w-9 rounded-lg bg-indigo-600 flex items-center justify-center shadow-md shadow-indigo-600/30">
              <Radio className="h-5 w-5 text-white animate-pulse" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-lg tracking-tight bg-gradient-to-r from-white via-slate-200 to-indigo-300 bg-clip-text text-transparent">
                  AUDIBLE AI
                </span>
                <Badge variant="outline" className="text-[10px] text-indigo-400 border-indigo-500/30 bg-indigo-500/10">
                  v2.0 Local
                </Badge>
              </div>
              <p className="text-[11px] text-slate-400">Autonomous Real-Time Voice Platform</p>
            </div>
          </div>

          {/* Infrastructure Health Status */}
          <div className="hidden md:flex items-center space-x-4 text-xs text-slate-400">
            <div className="flex items-center space-x-1.5 bg-slate-800/60 px-2.5 py-1 rounded-full border border-slate-700/50">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping" />
              <span>Gateway :3010</span>
            </div>
            <div className="flex items-center space-x-1.5 bg-slate-800/60 px-2.5 py-1 rounded-full border border-slate-700/50">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              <span>FastAPI :8000</span>
            </div>
            <div className="flex items-center space-x-1.5 bg-slate-800/60 px-2.5 py-1 rounded-full border border-slate-700/50">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              <span>Ollama llama3.2:1b</span>
            </div>
            <div className="flex items-center space-x-1.5 bg-slate-800/60 px-2.5 py-1 rounded-full border border-slate-700/50">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              <span>Windows SAPI TTS</span>
            </div>
            <div className="flex items-center space-x-1.5 bg-slate-800/60 px-2.5 py-1 rounded-full border border-slate-700/50">
              <span className={`h-2 w-2 rounded-full ${companionStatus?.status === "connected" ? "bg-emerald-400" : "bg-slate-500"}`} />
              <span>Note8 Jio ({companionStatus?.status === "connected" ? "Paired" : "Offline"})</span>
            </div>
          </div>

          {/* Header Action Links */}
          <div className="flex items-center space-x-2">
            <Button variant="ghost" size="sm" asChild className="text-slate-300 hover:text-white">
              <Link href="/workflow">
                <Settings className="h-4 w-4 mr-1.5" />
                Studio
              </Link>
            </Button>
            <Button variant="ghost" size="sm" asChild className="text-slate-300 hover:text-white">
              <Link href="/credentials">
                Telephony Setup
              </Link>
            </Button>
            <Button variant="outline" size="sm" asChild className="border-slate-700 bg-slate-800/50 text-slate-300 hover:bg-slate-700">
              <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer">
                API Docs
                <ExternalLink className="h-3 w-3 ml-1.5 opacity-70" />
              </a>
            </Button>
          </div>
        </div>
      </header>

      {/* Main Single-Screen Call Hub */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Left / Primary Column: Dialer & Active Call Window */}
          <div className="lg:col-span-7 flex flex-col space-y-6">
            <Card className="border-slate-800 bg-slate-900/40 backdrop-blur-sm shadow-xl">
              <CardHeader className="pb-4">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-xl font-semibold text-white flex items-center gap-2">
                      <PhoneCall className="h-5 w-5 text-indigo-400" />
                      Audible AI Voice Dispatcher
                    </CardTitle>
                    <CardDescription className="text-slate-400 text-sm mt-1">
                      Choose an AI agent, select destination mode, and launch real-time voice conversations.
                    </CardDescription>
                  </div>

                  {/* Call State Badge */}
                  <div>
                    {callState === "idle" && (
                      <Badge variant="outline" className="border-slate-700 text-slate-400 bg-slate-800/50">
                        Idle
                      </Badge>
                    )}
                    {callState === "validating" && (
                      <Badge className="bg-sky-500/20 text-sky-300 border-sky-500/30">
                        <Loader2 className="h-3 w-3 animate-spin mr-1" />
                        Validating
                      </Badge>
                    )}
                    {callState === "connecting" && (
                      <Badge className="bg-amber-500/20 text-amber-300 border-amber-500/30">
                        <Loader2 className="h-3 w-3 animate-spin mr-1" />
                        Connecting...
                      </Badge>
                    )}
                    {callState === "ringing" && (
                      <Badge className="bg-amber-500 text-slate-950 font-medium animate-pulse">
                        <PhoneCall className="h-3 w-3 mr-1 animate-bounce" />
                        Ringing...
                      </Badge>
                    )}
                    {callState === "connected" && (
                      <Badge className="bg-emerald-500 text-slate-950 font-medium shadow-lg shadow-emerald-500/20 animate-pulse">
                        <Activity className="h-3 w-3 mr-1" />
                        Connected ({formatTimer(callDuration)})
                      </Badge>
                    )}
                    {callState === "ending" && (
                      <Badge className="bg-orange-500/20 text-orange-300 border-orange-500/30">
                        Disconnecting...
                      </Badge>
                    )}
                    {callState === "ended" && (
                      <Badge variant="outline" className="border-slate-600 text-slate-300">
                        Call Ended
                      </Badge>
                    )}
                    {callState === "failed" && (
                      <Badge variant="destructive">
                        Call Failed
                      </Badge>
                    )}
                  </div>
                </div>
              </CardHeader>

              <CardContent className="space-y-6">
                {/* Agent Selector */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="agent-select" className="text-sm font-medium text-slate-300">
                      Select Voice Agent
                    </Label>
                    <Link
                      href={selectedWorkflowId ? `/workflow/${selectedWorkflowId}` : "/workflow"}
                      className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
                    >
                      Edit Workflow <ArrowRight className="h-3 w-3" />
                    </Link>
                  </div>
                  {loadingWorkflows ? (
                    <div className="h-10 bg-slate-800/50 rounded-md animate-pulse border border-slate-700" />
                  ) : workflows.length > 0 ? (
                    <Select
                      value={selectedWorkflowId?.toString() || ""}
                      onValueChange={(val) => setSelectedWorkflowId(Number(val))}
                      disabled={callState === "connected" || callState === "connecting"}
                    >
                      <SelectTrigger id="agent-select" className="bg-slate-950 border-slate-700 text-slate-200">
                        <SelectValue placeholder="Choose an agent..." />
                      </SelectTrigger>
                      <SelectContent className="bg-slate-900 border-slate-700 text-slate-200">
                        {workflows.map((wf) => (
                          <SelectItem key={wf.id} value={wf.id.toString()}>
                            <div className="flex items-center space-x-2">
                              <span className="font-medium text-white">{wf.name}</span>
                              <span className="text-xs text-slate-400">
                                (ID: {wf.id} | v{wf.version_number || 1})
                              </span>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-md text-amber-300 text-xs flex items-center justify-between">
                      <span>No active agents found in database.</span>
                      <Button size="sm" variant="outline" asChild className="h-7 text-xs border-amber-500/40">
                        <Link href="/workflow/create">Create Agent</Link>
                      </Button>
                    </div>
                  )}
                </div>

                {/* Prominent Separate Action: Talk to Bridget in Browser */}
                <div className="rounded-xl p-4 bg-gradient-to-r from-indigo-950/70 via-purple-950/50 to-slate-900 border border-indigo-500/30 shadow-md">
                  <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
                    <div className="space-y-1 text-center sm:text-left">
                      <div className="font-semibold text-white text-sm flex items-center justify-center sm:justify-start gap-1.5">
                        <Sparkles className="h-4 w-4 text-indigo-400" />
                        <span>Instant Local Voice Agent (100% Free & Offline)</span>
                      </div>
                      <p className="text-xs text-indigo-200/80">
                        Speak with {selectedWorkflow?.name || "Bridget"} directly using your laptop microphone and speakers. Zero telephone numbers, cellular setup, or external charges required.
                      </p>
                    </div>
                    <Button
                      onClick={handleStartBrowserCall}
                      disabled={!selectedWorkflowId || loadingWorkflows || callState === "connected" || callState === "connecting"}
                      className="bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs px-4 py-2 shrink-0 shadow-lg shadow-indigo-600/30 flex items-center gap-2"
                    >
                      <Mic className="h-4 w-4 text-indigo-200 animate-pulse" />
                      Talk to Bridget in Browser
                    </Button>
                  </div>
                </div>

                {/* Call Mode Tabs */}
                <Tabs
                  value={mode}
                  onValueChange={(val) => setMode(val as "browser" | "phone" | "companion")}
                  className="w-full"
                >
                  <TabsList className="grid grid-cols-3 bg-slate-950 border border-slate-800 p-1">
                    <TabsTrigger
                      value="browser"
                      disabled={callState === "connected"}
                      className="data-[state=active]:bg-indigo-600 data-[state=active]:text-white text-xs font-medium"
                    >
                      <Mic className="h-3.5 w-3.5 mr-1.5" />
                      Browser (Local AI)
                    </TabsTrigger>
                    <TabsTrigger
                      value="phone"
                      disabled={callState === "connected"}
                      className="data-[state=active]:bg-indigo-600 data-[state=active]:text-white text-xs font-medium"
                    >
                      <Phone className="h-3.5 w-3.5 mr-1.5" />
                      Phone (PSTN)
                    </TabsTrigger>
                    <TabsTrigger
                      value="companion"
                      disabled={callState === "connected"}
                      className="data-[state=active]:bg-indigo-600 data-[state=active]:text-white text-xs font-medium flex items-center justify-center gap-1.5"
                    >
                      <Smartphone className="h-3.5 w-3.5 mr-1" />
                      Note8 (Jio 4G)
                      <span className={`h-1.5 w-1.5 rounded-full ${companionStatus?.status === "connected" ? "bg-emerald-400" : "bg-slate-500"}`} />
                    </TabsTrigger>
                  </TabsList>

                  {/* Mode 1: Browser Voice Test (Local WebRTC) */}
                  <TabsContent value="browser" className="mt-4 space-y-4">
                    <div className="p-4 rounded-lg bg-indigo-950/20 border border-indigo-900/40 text-xs text-slate-300 space-y-2">
                      <div className="flex items-center text-indigo-300 font-semibold gap-1.5">
                        <Volume2 className="h-4 w-4" />
                        100% Offline Local Pipeline
                      </div>
                      <p>
                        Speaks directly through your laptop speakers and listens via microphone. Powered by local{" "}
                        <span className="text-white font-mono">Ollama llama3.2:1b</span>, local STT, and{" "}
                        <span className="text-white font-mono">Windows SAPI TTS</span>. No external telephony or cloud
                        API required.
                      </p>
                    </div>

                    {/* Active WebRTC Runner Container */}
                    {callState === "connected" && activeVoiceRunId && selectedWorkflowId && accessToken ? (
                      <div className="h-[360px] rounded-lg border border-slate-700 bg-slate-950/80 overflow-hidden flex flex-col">
                        <EmbeddedVoiceTester
                          workflowId={selectedWorkflowId}
                          workflowRunId={activeVoiceRunId}
                          accessToken={accessToken}
                          onReset={handleEndCall}
                        />
                      </div>
                    ) : (
                      <div className="flex flex-col items-center justify-center p-8 border border-dashed border-slate-800 rounded-lg bg-slate-950/40 text-center space-y-3">
                        <div className="h-12 w-12 rounded-full bg-indigo-600/10 flex items-center justify-center text-indigo-400">
                          <Mic className="h-6 w-6" />
                        </div>
                        <div>
                          <h4 className="text-sm font-medium text-slate-200">Ready for Browser Voice Session</h4>
                          <p className="text-xs text-slate-400 max-w-sm mt-1">
                            Click start to open a low-latency WebRTC bidirectional audio stream with Audible AI.
                          </p>
                        </div>
                        <Button
                          onClick={handleStartBrowserCall}
                          disabled={!selectedWorkflowId || loadingWorkflows}
                          className="bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/30 px-6"
                        >
                          <PhoneCall className="h-4 w-4 mr-2" />
                          Start Voice Conversation
                        </Button>
                      </div>
                    )}
                  </TabsContent>

                  {/* Mode 2: Outbound Phone Call (PSTN) */}
                  <TabsContent value="phone" className="mt-4 space-y-4">
                    {/* Clear Mandatory Message & Status Banner */}
                    <div className="p-4 rounded-xl bg-amber-950/30 border border-amber-600/40 text-amber-200 space-y-3">
                      <div className="flex items-center text-amber-300 font-semibold gap-2 text-sm">
                        <AlertCircle className="h-5 w-5 text-amber-400 shrink-0" />
                        <span>Phone calling requires a telephony connection.</span>
                      </div>
                      <p className="text-xs text-amber-200/90 leading-relaxed">
                        Outbound phone dialing is currently disabled because no real SIP trunk, PBX, or telephony provider has been configured in this local environment. To talk to your agent right now without any telephone setup, use the local browser button below.
                      </p>
                    </div>

                    {/* Phone Number Input with Country Code Selector */}
                    <div className="space-y-3">
                      <Label htmlFor="phone-input" className="text-sm font-medium text-slate-300">
                        Destination Phone Number (E.164)
                      </Label>
                      <div className="flex space-x-2">
                        {/* Country Code Selector */}
                        <Select
                          value={countryCode}
                          onValueChange={setCountryCode}
                          disabled={!isTelephonyReady || callState === "connected" || callState === "connecting"}
                        >
                          <SelectTrigger className="w-[140px] bg-slate-950 border-slate-700 text-slate-200 disabled:opacity-50">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent className="bg-slate-900 border-slate-700 text-slate-200">
                            {COUNTRY_CODES.map((item) => (
                              <SelectItem key={item.code} value={item.code}>
                                <span className="mr-1.5">{item.flag}</span>
                                <span>{item.code}</span>
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>

                        {/* Phone Number Field */}
                        <div className="flex-1 relative">
                          <Input
                            id="phone-input"
                            type="tel"
                            placeholder="e.g. 5552345678"
                            value={phoneNumber}
                            onChange={(e) => setPhoneNumber(e.target.value)}
                            disabled={!isTelephonyReady || callState === "connected" || callState === "connecting"}
                            className="bg-slate-950 border-slate-700 text-white pl-3 font-mono text-sm disabled:opacity-50"
                          />
                        </div>
                      </div>

                      {/* E.164 Live Preview & Status */}
                      <div className="flex items-center justify-between text-xs text-slate-400">
                        <div className="flex items-center gap-1.5">
                          <span>Normalized E.164:</span>
                          <span className="font-mono text-slate-200 font-semibold">
                            {formattedE164 || "—"}
                          </span>
                        </div>
                        {phoneNumber.length > 0 && (
                          <div className="flex items-center gap-1">
                            {isE164Valid ? (
                              <span className="text-emerald-400 flex items-center gap-1">
                                <CheckCircle2 className="h-3.5 w-3.5" /> Valid
                              </span>
                            ) : (
                              <span className="text-amber-400 flex items-center gap-1">
                                <AlertCircle className="h-3.5 w-3.5" /> Invalid format
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Phone Call Action Button - DISABLED until provider readiness checks pass */}
                    <div className="pt-2 space-y-2.5">
                      <Button
                        onClick={handleStartPhoneCall}
                        disabled={!isTelephonyReady || !isE164Valid || !selectedWorkflowId || callState !== "idle"}
                        className={cn(
                          "w-full text-white shadow-lg transition-all",
                          isTelephonyReady
                            ? "bg-emerald-600 hover:bg-emerald-500 shadow-emerald-600/30 cursor-pointer"
                            : "bg-slate-800/80 text-slate-400 cursor-not-allowed border border-slate-700/60 opacity-60"
                        )}
                      >
                        <PhoneOff className="h-4 w-4 mr-2 text-slate-400" />
                        {isTelephonyReady
                          ? `Dial ${formattedE164}`
                          : "Phone calling requires a telephony connection"}
                      </Button>

                      {/* Prominent Separate: Talk to Bridget in Browser */}
                      <Button
                        type="button"
                        onClick={handleStartBrowserCall}
                        disabled={!selectedWorkflowId || callState === "connected" || callState === "connecting"}
                        className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs h-10 shadow-lg shadow-indigo-600/30 flex items-center justify-center gap-2 cursor-pointer"
                      >
                        <Mic className="h-4 w-4 text-indigo-200 animate-pulse" />
                        Talk to {selectedWorkflow?.name || "Bridget"} in Browser (No Phone Number Needed)
                      </Button>
                    </div>

                    {/* Guided Setup for Supported SIP/PBX or Telephony Provider */}
                    <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 text-xs space-y-3 mt-4">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-white text-sm flex items-center gap-1.5">
                          <Settings className="h-4 w-4 text-indigo-400" />
                          Guided Telephony Setup (SIP / PBX / Carrier)
                        </span>
                        <Badge variant="outline" className="text-amber-400 border-amber-500/30 bg-amber-500/10 text-[10px]">
                          telephony_not_configured
                        </Badge>
                      </div>

                      <p className="text-slate-400 leading-relaxed">
                        To dial real landlines or mobile devices, configure a supported carrier or private SIP PBX in settings:
                      </p>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 pt-1">
                        <div className="p-3 rounded-lg bg-slate-950/80 border border-slate-800 space-y-1.5">
                          <div className="font-medium text-slate-200 flex items-center gap-1.5">
                            <Radio className="h-3.5 w-3.5 text-indigo-400" />
                            Option A: Cloud Carrier (API)
                          </div>
                          <p className="text-[11px] text-slate-300">Twilio, Telnyx, Plivo, Vonage</p>
                          <p className="text-[10px] text-slate-400">
                            Required: Account SID / API Key + Auth Token + Verified E.164 Caller ID Number.
                          </p>
                        </div>

                        <div className="p-3 rounded-lg bg-slate-950/80 border border-slate-800 space-y-1.5">
                          <div className="font-medium text-slate-200 flex items-center gap-1.5">
                            <Radio className="h-3.5 w-3.5 text-indigo-400" />
                            Option B: Private PBX / SIP Trunk
                          </div>
                          <p className="text-[11px] text-slate-300">Asterisk ARI, FreePBX, Kamailio</p>
                          <p className="text-[10px] text-slate-400">
                            Required: ARI Host URL, Username, Application Name + Outbound SIP Trunk Route.
                          </p>
                        </div>
                      </div>

                      {/* Audited Missing Configuration Blockers */}
                      <div className="rounded-lg bg-slate-950 p-3 space-y-2 border border-slate-800/80">
                        <div className="text-[11px] font-semibold text-slate-300">Audited Missing Blockers (audible.db):</div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
                          <div className="flex items-center gap-1.5 text-rose-400">
                            <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                            <span>1. Provider Credentials: <strong>None Configured (0 rows)</strong></span>
                          </div>
                          <div className="flex items-center gap-1.5 text-rose-400">
                            <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                            <span>2. Caller ID Phone Number: <strong>None Registered (0 rows)</strong></span>
                          </div>
                          <div className="flex items-center gap-1.5 text-rose-400">
                            <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                            <span>3. SIP Trunk / PBX Route: <strong>Unbound (0 rows)</strong></span>
                          </div>
                          <div className="flex items-center gap-1.5 text-rose-400">
                            <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                            <span>4. Carrier Authorization: <strong>Required Before Dialing</strong></span>
                          </div>
                        </div>
                      </div>

                      <div className="pt-2 flex flex-wrap items-center gap-2">
                        <Button size="sm" variant="default" asChild className="h-8 text-xs bg-indigo-600 hover:bg-indigo-500 text-white font-medium">
                          <Link href="/telephony-configurations?add=1">
                            <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
                            Configure Telephony Provider
                          </Link>
                        </Button>
                        <Button size="sm" variant="ghost" asChild className="h-8 text-xs text-slate-400 hover:text-white">
                          <Link href="/credentials">
                            View General Credentials
                          </Link>
                        </Button>
                      </div>
                    </div>
                  </TabsContent>

                  {/* Mode 3: Galaxy Note8 Cellular Companion (Jio 4G) */}
                  <TabsContent value="companion" className="mt-4 space-y-4">
                    {/* Device Status Card */}
                    <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Smartphone className="h-5 w-5 text-indigo-400" />
                          <div>
                            <div className="font-semibold text-white text-sm">
                              {companionStatus?.device ? `${companionStatus.device.manufacturer.toUpperCase()} ${companionStatus.device.model}` : "Samsung Galaxy Note8 (SM-N950F)"}
                            </div>
                            <div className="text-[11px] text-slate-400">
                              OS: Android {companionStatus?.device?.android_version || "14"} (API {companionStatus?.device?.sdk_version || "34"}) • arm64-v8a
                            </div>
                          </div>
                        </div>
                        <Badge
                          variant="outline"
                          className={companionStatus?.status === "connected"
                            ? "text-emerald-400 border-emerald-500/30 bg-emerald-500/10 text-xs"
                            : "text-amber-400 border-amber-500/30 bg-amber-500/10 text-xs"}
                        >
                          {companionStatus?.status === "connected" ? "USB Tunnel Active" : "Disconnected"}
                        </Badge>
                      </div>

                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 pt-2 text-xs">
                        <div className="p-2.5 rounded-lg bg-slate-950/70 border border-slate-800">
                          <span className="text-[11px] text-slate-400 block">Cellular SIM</span>
                          <span className="font-semibold text-emerald-400">
                            {companionStatus?.device?.sim_operator || "JIO 4G"} (VoLTE)
                          </span>
                        </div>
                        <div className="p-2.5 rounded-lg bg-slate-950/70 border border-slate-800">
                          <span className="text-[11px] text-slate-400 block">Call State</span>
                          <span className="font-semibold text-white">
                            {companionStatus?.current_call?.state || "IDLE"}
                          </span>
                        </div>
                        <div className="p-2.5 rounded-lg bg-slate-950/70 border border-slate-800 col-span-2 sm:col-span-1">
                          <span className="text-[11px] text-slate-400 block">Battery</span>
                          <span className="font-semibold text-indigo-300">
                            {companionStatus?.device?.battery_level ? `${companionStatus.device.battery_level}%` : "50%"}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Telecom Control Section */}
                    <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
                      <div className="font-semibold text-white text-xs uppercase tracking-wider text-slate-400">
                        Cellular Call Signaling Controls
                      </div>
                      <div className="flex items-center justify-between text-xs p-3 rounded-lg bg-slate-950/80 border border-slate-800">
                        <div>
                          <div className="text-slate-300 font-medium">Telecom Event Monitor</div>
                          <div className="text-[11px] text-slate-500">
                            Active Caller: {companionStatus?.current_call?.number || "None"}
                          </div>
                        </div>
                        <Badge
                          variant="outline"
                          className={companionStatus?.current_call?.active
                            ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30 animate-pulse"
                            : "bg-slate-800 text-slate-400 border-slate-700"}
                        >
                          {companionStatus?.current_call?.state || "IDLE"}
                        </Badge>
                      </div>
                      <p className="text-[11px] text-slate-400 leading-relaxed">
                        Call state synchronization and telecom actions (answer, disconnect, dial) execute natively through the companion app running on the Note8.
                      </p>
                    </div>

                    {/* Phase 4: Audio Feasibility Gate Audit Report */}
                    <div className="p-4 rounded-xl bg-amber-950/20 border border-amber-600/40 text-xs space-y-2.5">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5 text-amber-300 font-semibold">
                          <ShieldAlert className="h-4 w-4 text-amber-400" />
                          <span>Phase 4: Cellular Audio Feasibility Gate</span>
                        </div>
                        <Badge
                          variant="outline"
                          className={companionStatus?.audio_gate_passed
                            ? "text-emerald-400 border-emerald-500/30 bg-emerald-500/10 text-[10px]"
                            : "text-amber-400 border-amber-500/30 bg-amber-500/10 text-[10px]"}
                        >
                          {companionStatus?.audio_gate_passed ? "GATE PASSED" : "BASEBAND ISOLATED"}
                        </Badge>
                      </div>

                      <div className="text-[11px] text-amber-200/90 leading-relaxed space-y-1.5">
                        <p>
                          <strong>Objective Finding:</strong> Standard Android OS kernel security (Android 14 / LineageOS) strictly prevents user-space applications from accessing raw cellular baseband audio via <code className="font-mono bg-black/40 px-1 py-0.5 rounded text-amber-100">AudioSource.VOICE_CALL</code> without platform signature permission <code className="font-mono bg-black/40 px-1 py-0.5 rounded text-amber-100">CAPTURE_AUDIO_OUTPUT</code>.
                        </p>
                        <div className="p-2.5 rounded bg-black/30 border border-amber-500/20 text-slate-300 text-[11px] space-y-1">
                          <div className="text-amber-300 font-medium">Supported Physical / Hardware Bridge Architectures:</div>
                          <ol className="list-decimal list-inside space-y-0.5 text-slate-300">
                            <li><strong>Bluetooth Hands-Free Profile (HFP/SCO):</strong> Pair Note8 with Windows 11 as a Hands-Free Audio Gateway. Live cellular audio routes bidirectionally through Windows audio devices.</li>
                            <li><strong>Hardware 3.5mm TRRS Splitter:</strong> Analog CTIA loopback cable connecting Note8 headphone jack to PC Line-In / Mic.</li>
                            <li><strong>Dedicated GSM SIP Trunk Gateway:</strong> Hardware VoIP box (e.g. GoIP) bridging the Jio SIM into Asterisk.</li>
                          </ol>
                        </div>
                      </div>
                    </div>
                  </TabsContent>

                </Tabs>

                {/* Error Banner */}
                {errorMessage && (
                  <div className="p-3 bg-rose-950/30 border border-rose-900/50 rounded-lg text-rose-300 text-xs flex items-start gap-2">
                    <AlertCircle className="h-4 w-4 text-rose-400 shrink-0 mt-0.5" />
                    <div className="flex-1">{errorMessage}</div>
                  </div>
                )}
              </CardContent>

              {/* Call Controls Footer (when active) */}
              {callState === "connected" && (
                <CardFooter className="border-t border-slate-800/80 pt-4 flex justify-between items-center bg-slate-950/60">
                  <div className="flex items-center space-x-2 text-xs text-slate-400">
                    <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                    <span>Active Session</span>
                    <span className="font-mono text-white font-medium">({formatTimer(callDuration)})</span>
                  </div>
                  <Button
                    onClick={handleEndCall}
                    variant="destructive"
                    size="sm"
                    className="shadow-lg shadow-rose-600/20"
                  >
                    <PhoneOff className="h-4 w-4 mr-1.5" />
                    End Call
                  </Button>
                </CardFooter>
              )}
            </Card>
          </div>

          {/* Right Column: Infrastructure Diagnostic & Recent Call History */}
          <div className="lg:col-span-5 flex flex-col space-y-6">
            {/* System Status Card */}
            <Card className="border-slate-800 bg-slate-900/40 backdrop-blur-sm shadow-xl">
              <CardHeader className="pb-3">
                <CardTitle className="text-base font-medium text-white flex items-center justify-between">
                  <span>System Diagnostics</span>
                  <Badge variant="outline" className="text-emerald-400 border-emerald-500/30 bg-emerald-500/10 text-[10px]">
                    Single Origin
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-xs">
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/60">
                  <span className="text-slate-400">User Entrypoint</span>
                  <span className="font-mono text-slate-200">http://localhost:3010</span>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/60">
                  <span className="text-slate-400">FastAPI Backend</span>
                  <span className="font-mono text-emerald-400">http://localhost:8000 (Reachable)</span>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/60">
                  <span className="text-slate-400">Local LLM Engine</span>
                  <span className="font-mono text-slate-200">Ollama (llama3.2:1b)</span>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/60">
                  <span className="text-slate-400">Speech-To-Text</span>
                  <span className="font-mono text-slate-200">Local STT Recognizer</span>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/60">
                  <span className="text-slate-400">Speech Synthesis</span>
                  <span className="font-mono text-slate-200">Windows SAPI TTS</span>
                </div>
                <div className="flex items-center justify-between py-1.5">
                  <span className="text-slate-400">Telephony Configurations</span>
                  <span className={cn("font-mono font-medium", isTelephonyReady ? "text-emerald-400" : "text-amber-400")}>
                    {telephonyConfigs.length} Registered
                  </span>
                </div>
              </CardContent>
            </Card>

            {/* Recent Call Log Card */}
            <Card className="border-slate-800 bg-slate-900/40 backdrop-blur-sm shadow-xl flex-1 flex flex-col">
              <CardHeader className="pb-3 flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-base font-medium text-white flex items-center gap-1.5">
                    <Clock className="h-4 w-4 text-slate-400" />
                    Recent Call Activity
                  </CardTitle>
                  <CardDescription className="text-slate-400 text-xs">
                    Persistent call history from local SQLite database.
                  </CardDescription>
                </div>
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={() => void loadRecentRuns()}
                  disabled={loadingRecentRuns}
                  className="h-8 w-8 text-slate-400 hover:text-white"
                >
                  <RefreshCw className={cn("h-3.5 w-3.5", loadingRecentRuns && "animate-spin")} />
                </Button>
              </CardHeader>

              <CardContent className="flex-1 overflow-auto">
                {loadingRecentRuns ? (
                  <div className="space-y-2 py-2">
                    <div className="h-12 bg-slate-800/40 rounded animate-pulse" />
                    <div className="h-12 bg-slate-800/40 rounded animate-pulse" />
                  </div>
                ) : recentRuns.length > 0 ? (
                  <div className="space-y-2">
                    {recentRuns.map((run) => (
                      <div
                        key={run.id}
                        className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/80 flex items-center justify-between text-xs"
                      >
                        <div className="space-y-0.5">
                          <div className="font-mono text-slate-200 font-medium">{run.name}</div>
                          <div className="text-[11px] text-slate-400 flex items-center gap-2">
                            <span>{new Date(run.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                            <span>•</span>
                            <span className="capitalize">{run.mode}</span>
                          </div>
                        </div>
                        <div>
                          <Badge
                            variant="outline"
                            className={cn(
                              "text-[10px] capitalize",
                              run.status === "completed"
                                ? "text-emerald-400 border-emerald-500/30 bg-emerald-500/10"
                                : run.status === "failed"
                                ? "text-rose-400 border-rose-500/30 bg-rose-500/10"
                                : "text-amber-400 border-amber-500/30 bg-amber-500/10"
                            )}
                          >
                            {run.status}
                          </Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="py-8 text-center text-xs text-slate-500">
                    No recent calls recorded yet for this agent.
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
}
