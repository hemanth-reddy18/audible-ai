/**
 * Audible AI — Universal Typed Contracts
 */

export type ModelProvider =
  | "openai"
  | "anthropic"
  | "gemini"
  | "groq"
  | "together"
  | "cerebras"
  | "fireworks"
  | "openrouter"
  | "deepseek";

export type STTProvider =
  | "deepgram"
  | "cartesia"
  | "whisper"
  | "soniox"
  | "speechmatics"
  | "sarvam"
  | "speaches";

export type TTSProvider =
  | "cartesia"
  | "elevenlabs"
  | "openai"
  | "deepgram"
  | "rime"
  | "playht"
  | "lmnt"
  | "minimax"
  | "speechify"
  | "smallest"
  | "sarvam";

export type S2SProvider =
  | "openai_realtime"
  | "gemini_multimodal_live"
  | "ultravox";

export interface VoicePipelineConfig {
  sttProvider: STTProvider;
  sttModel?: string;
  sttLanguage?: string;
  llmProvider: ModelProvider;
  llmModel: string;
  llmTemperature?: number;
  ttsProvider: TTSProvider;
  ttsVoiceId: string;
  ttsModel?: string;
  enableBargeIn?: boolean;
  vadSensitivity?: "low" | "medium" | "high";
  vadStopSecs?: number;
}

export interface WebRTCSignalingMessage {
  type: "offer" | "answer" | "candidate" | "ping" | "pong" | "error" | "hangup";
  sdp?: string;
  candidate?: {
    candidate: string;
    sdpMid?: string | null;
    sdpMLineIndex?: number | null;
  };
  error?: string;
  timestamp?: number;
}

export interface CallMetrics {
  durationSeconds: number;
  timeToFirstByteMs?: number;
  averageLatencyMs?: number;
  userSpeechDurationSecs?: number;
  agentSpeechDurationSecs?: number;
  interruptionsCount?: number;
}
