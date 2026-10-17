# Audible AI — Upstream Attribution & Provenance Notice

Audible (`audible-ai`) is an independently branded, production-grade AI voice-agent platform designed for high-performance voice agents, real-time speech processing, and enterprise telephony.

## Upstream Provenance & Notice

Audible incorporates software originally developed under the Dograh project:
- **Upstream Repository**: [https://github.com/dograh-hq/dograh](https://github.com/dograh-hq/dograh)
- **Original Copyright**: Copyright (c) 2025, Zansat Technologies Private Limited.
- **Original License**: BSD 2-Clause License.

In compliance with Clause 1 and Clause 2 of the BSD 2-Clause License, the original copyright notice and conditions of license are retained in the `LICENSE` file and reproduced in this document.

## Audible Differentiators & Enhancements

Audible re-architects and extends this codebase with:
1. **Audible Sovereign Branding**: Complete replacement of all upstream brand elements with an Apple-inspired liquid-glass design system, translucent surfaces, subtle depth blurs, and original design tokens.
2. **Modular Architecture**: Reorganized into a clean monorepo topology:
   - `apps/web`: Audible Next.js 15 App Router Frontend.
   - `apps/api`: Audible FastAPI Core Engine.
   - `packages/ui`: Liquid-glass design system and components.
   - `packages/types`: Shared cross-language contracts.
   - `packages/sdk`: Client SDKs for TypeScript and Python.
   - `services/`: Dedicated decoupled service engines for voice runtime, speech recognition, synthesis, agent orchestration, and telephony.
3. **Decoupled Voice Runtime**: Provider adapters for STT, LLM, TTS, and Speech-to-Speech (S2S) with dynamic failover and sub-second barge-in interruption.
4. **Telemetry Privacy**: All upstream proprietary analytics, remote telemetry trackers, and hardcoded external reporting endpoints have been replaced with configurable self-hosted telemetry controls.
5. **Windows 11 Native & Docker Support**: Optimized startup orchestrators (`scripts/start_audible_dev.ps1`) supporting Intel Core i5 hybrid CPU architectures and local development environments.
