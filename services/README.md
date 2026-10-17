# Audible AI — Core Service Modules

This directory contains Audible's decoupled service engines:

1. `voice-runtime/`: The real-time streaming audio pipeline orchestrator, SmallWebRTC signaling handlers, Silero/WebRTC VAD, and barge-in interruption controller.
2. `speech-recognition/`: Adapters for streaming and batch STT engines (Deepgram Nova-2/3, Cartesia, Whisper Large v3, Soniox, Speechmatics, Sarvam).
3. `speech-synthesis/`: Adapters for low-latency TTS engines (Cartesia Sonic, ElevenLabs Flash, OpenAI TTS, Deepgram Aura, Minimax, Speechify, Smallest).
4. `agent-orchestrator/`: Conversational state machines, tool-calling dispatchers, MCP bridges, and dynamic prompt template engines.
5. `telephony/`: Carrier connectors for SIP Trunks, Twilio, Telnyx, Plivo, Vonage, Cloudonix, Exotel, and Asterisk (ARI).
6. `integrations/`: FastMCP servers, custom REST tools, CRM webhooks, and analytics exporters.
