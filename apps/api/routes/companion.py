"""
Audible AI — Samsung Galaxy Note8 Companion Bridge Router
Handles real-time communication between the Android companion app and Windows Audible AI backend,
including the FreshMart Supermarket AI Receptionist scenario, SQLite Persistent Order Management,
Two-Way SMS Integration, Kokoro-82M Offline Neural TTS, and Cellular Audio Diagnostics.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Request, Response, Query
from pydantic import BaseModel
from loguru import logger

from api.services.supermarket import (
    SupermarketEngine,
    SupermarketSessionManager,
    ConversationState,
    ConfirmationStatus
)
from api.services.supermarket.db import OrderDatabase, OrderRecord
from api.services.supermarket.sms_handler import SMSProcessor
from api.services.tts.kokoro_engine import KokoroTTSEngine

router = APIRouter(prefix="/companion", tags=["companion"])

engine = SupermarketEngine()
session_manager = SupermarketSessionManager.get_instance()
order_db = OrderDatabase.get_instance()
sms_processor = SMSProcessor(order_db, engine)
tts_engine = KokoroTTSEngine.get_instance()


class CompanionDevice(BaseModel):
    device_id: str
    model: str
    manufacturer: str
    android_version: str
    sdk_version: int
    sim_operator: str
    battery_level: Optional[int] = None
    paired_at: str


class CallEvent(BaseModel):
    call_id: Optional[str] = None
    state: str  # IDLE, RINGING, OFFHOOK, OFFHOOK_AUTO_ANSWERED
    incoming_number: Optional[str] = None
    duration_seconds: Optional[int] = 0
    timestamp: str


class InboundSMS(BaseModel):
    sender: str
    message: str
    timestamp: Optional[str] = None


class CommandAck(BaseModel):
    command_id: str
    session_id: Optional[str] = None
    status: str = "COMPLETED"
    error: Optional[str] = None


class SupermarketChatRequest(BaseModel):
    session_id: Optional[str] = None
    caller_speech: str
    language: Optional[str] = "en"


class AudioRouteDiagnostic(BaseModel):
    audio_mode: str
    speakerphone_on: bool
    communication_device: Optional[str] = None
    stream_voice_call_volume: int
    stream_music_volume: int
    sample_rate: int = 16000
    timestamp: str


# In-memory companion bridge state
_bridge_state = {
    "device": None,
    "current_call": {
        "state": "IDLE",
        "number": None,
        "active": False,
        "last_updated": None
    },
    "history": [],
    "audio_diagnostics": None,
    "audio_gate_passed": False,
    "audio_blocker_report": (
        "Stock Android & LineageOS kernel security restricts AudioSource.VOICE_CALL and AudioSource.VOICE_DOWNLINK "
        "to signature|privileged system apps (CAPTURE_AUDIO_OUTPUT). On Exynos 8895 baseband bus (Shannon 355 CP_I2S), "
        "hardware Acoustic Echo Cancellation (AEC) subtracts loudspeaker audio from cellular uplink mic input. "
        "Direct user-space audio injection is BLOCKED; legitimate verified bridges are: "
        "Option A: Bluetooth HFP Hands-Free Audio Gateway, "
        "Option B: Physical 3.5mm TRRS Line Interface, "
        "Option C: Carrier Call Forwarding to SIP trunk."
    ),
    "scenario": "supermarket_receptionist"
}


@router.get("/status")
async def get_companion_status():
    """Get the current pairing, call state, supermarket order, and audio gate status."""
    active_order = session_manager.get_active_session()
    recent_db_orders = order_db.list_orders(limit=5)
    return {
        "status": "connected" if _bridge_state["device"] else "unpaired",
        "device": _bridge_state["device"],
        "current_call": _bridge_state["current_call"],
        "audio_gate_passed": _bridge_state["audio_gate_passed"],
        "audio_blocker_report": _bridge_state["audio_blocker_report"],
        "audio_diagnostics": _bridge_state["audio_diagnostics"],
        "history_count": len(_bridge_state["history"]),
        "agent": "FreshMart Supermarket AI Receptionist (Scenario: supermarket_receptionist)",
        "active_order": active_order.model_dump() if active_order else None,
        "recent_orders_count": len(recent_db_orders),
        "tts_engine": "Kokoro-82M Neural ONNX (Self-Hosted Offline)"
    }


@router.post("/pair")
async def pair_companion_device(device: CompanionDevice):
    """Register or update paired Android companion device."""
    _bridge_state["device"] = device.model_dump()
    logger.info(f"[Companion Bridge] Paired Android Device: {device.manufacturer} {device.model} (Android {device.android_version}, SIM: {device.sim_operator})")
    return {
        "paired": True,
        "message": f"Successfully paired {device.model} with Audible AI Windows Backend",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/call-event")
async def report_call_event(event: CallEvent):
    """Receive call state change events from the Android Telecom receiver."""
    is_active = event.state in ["RINGING", "OFFHOOK", "OFFHOOK_AUTO_ANSWERED"]
    _bridge_state["current_call"] = {
        "state": event.state,
        "number": event.incoming_number,
        "active": is_active,
        "last_updated": event.timestamp
    }
    _bridge_state["history"].append(event.model_dump())
    if len(_bridge_state["history"]) > 50:
        _bridge_state["history"].pop(0)

    logger.info(f"[Companion Call Event] State: {event.state} | Caller: {event.incoming_number} | CallId: {event.call_id}")

    # Handle incoming call connection
    if event.state in ["OFFHOOK", "OFFHOOK_AUTO_ANSWERED"]:
        session_id = event.call_id or f"call_{int(datetime.utcnow().timestamp())}"
        
        # ENFORCE EXACTLY ONE GREETING PER CALL SESSION AT MANAGER LEVEL
        if not session_manager.should_greet(session_id):
            logger.info(f"[Supermarket Session] Call session {session_id} already greeted. Skipping duplicate greeting.")
            return {"status": "already_greeted", "session_id": session_id}

        session_manager.mark_greeted(session_id)
        caller_num = event.incoming_number or "Cellular Caller"
        order = session_manager.get_or_create_session(session_id, caller_num)
        order.state = ConversationState.ANSWERED

        # Check for repeat customer with recent order
        recent_order = order_db.get_recent_order_for_caller(caller_num)
        if recent_order and recent_order.status != "CANCELLED":
            greeting_text = (
                f"Welcome back to FreshMart! I see your recent order {recent_order.order_id} "
                f"with {recent_order.summary_text}. Would you like to modify it, or place a new order today?"
            )
        else:
            greeting_text = engine.get_initial_greeting()

        order.state = ConversationState.GREETING
        order.transcript.append({"role": "assistant", "text": greeting_text})
        cmd_id = session_manager.queue_command(session_id, "SPEAK", {"text": greeting_text, "state": "GREETING"})
        logger.info(f"[Supermarket Session] Call Connected ({session_id}). Queued initial greeting #{cmd_id}: '{greeting_text}'")

    elif event.state == "IDLE":
        active_order = session_manager.get_active_session()
        if active_order:
            active_order.state = ConversationState.COMPLETED
            logger.info(f"[Supermarket Session] Call Finished. Order summary: {active_order.get_order_summary()}")
        
        # Cancel any in-flight commands and clean up stale sessions
        if event.call_id:
            session_manager.cancel_session_commands(event.call_id)
        session_manager.cleanup_stale_sessions()

    return {"status": "recorded", "state": event.state}


# ==================== SUPERMARKET RECEPTIONIST ROUTES ====================

@router.post("/supermarket/chat")
async def supermarket_chat_turn(req: SupermarketChatRequest):
    """Process an utterance from the caller through the dynamic conversation engine."""
    order = session_manager.get_active_session()
    if not order:
        session_id = req.session_id or f"session_{int(datetime.utcnow().timestamp())}"
        order = session_manager.get_or_create_session(session_id)

    response = engine.process_turn(order, req.caller_speech)
    logger.info(f"[Supermarket Turn] Caller: '{req.caller_speech}' -> AI: '{response.ai_text}' (State: {response.state})")

    # Queue SPEAK command with unique ID
    session_manager.queue_command(order.session_id, "SPEAK", {
        "text": response.ai_text,
        "state": response.state.value,
        "should_hangup": response.should_hangup
    })

    # If order confirmed or farewell reached, persist to SQLite and queue SMS confirmation
    if response.should_hangup or response.state in [ConversationState.CONFIRMED, ConversationState.FAREWELL]:
        if order.items:
            saved_record = order_db.save_order(
                session_id=order.session_id,
                caller_number=order.caller_id,
                items=order.items,
                status="CONFIRMED"
            )
            # Queue SMS transmission on companion device
            if order.caller_id and order.caller_id != "Unknown" and saved_record.sms_text:
                session_manager.queue_command(order.session_id, "SEND_SMS", {
                    "phone_number": order.caller_id,
                    "order_id": saved_record.order_id,
                    "message": saved_record.sms_text
                })
                logger.info(f"[Supermarket Order] Queued SMS confirmation to {order.caller_id} for order {saved_record.order_id}")

        if response.should_hangup:
            session_manager.queue_command(order.session_id, "HANGUP", {
                "reason": "ORDER_CONFIRMED_AND_FAREWELL_DELIVERED"
            })
            logger.info(f"[Supermarket Order] Order complete! Queued automatic HANGUP.")

    return {
        "ai_text": response.ai_text,
        "state": response.state.value,
        "should_hangup": response.should_hangup,
        "order": order.model_dump(),
        "language_detected": response.language_detected
    }


@router.get("/supermarket/pending-commands")
async def get_pending_commands(session_id: Optional[str] = None):
    """Poll for pending commands (SPEAK, HANGUP, SEND_SMS) by the companion app using atomic claiming."""
    target_id = session_id
    if not target_id:
        active = session_manager.get_active_session()
        if active:
            target_id = active.session_id

    if not target_id:
        return {"commands": []}

    commands = session_manager.claim_commands(target_id)
    return {"session_id": target_id, "commands": commands}


@router.post("/commands/ack")
async def acknowledge_command(ack: CommandAck):
    """Acknowledge execution of a command from companion app after real completion."""
    session_manager.ack_command(ack.command_id, status=ack.status, error=ack.error)
    return {"status": "acknowledged", "command_id": ack.command_id}


@router.post("/supermarket/speak-test")
async def trigger_speak_test_phrase(session_id: Optional[str] = None):
    """Queue the specific Phase 3 connection test phrase."""
    test_phrase = "Hello, this is Audible AI. Your voice connection test is successful."
    target_id = session_id
    if not target_id:
        active = session_manager.get_active_session()
        target_id = active.session_id if active else "test_session"

    cmd_id = session_manager.queue_command(target_id, "SPEAK", {
        "text": test_phrase,
        "state": "TEST",
        "should_hangup": False
    })
    logger.info(f"[Supermarket Test] Queued Test Phrase (cmd={cmd_id}): '{test_phrase}'")
    return {"status": "queued", "command_id": cmd_id, "phrase": test_phrase}


@router.get("/supermarket/order")
async def get_current_supermarket_order():
    """Retrieve active supermarket order details."""
    order = session_manager.get_active_session()
    if not order:
        return {"active": False, "order": None}
    return {"active": True, "order": order.model_dump(), "summary": order.get_order_summary(order.language)}


@router.post("/supermarket/reset")
async def reset_supermarket_session():
    """Reset the current supermarket order session."""
    active = session_manager.get_active_session()
    if active:
        session_manager.reset_session(active.session_id)
    return {"status": "reset"}


# ==================== PERSISTENT ORDERS & TWO-WAY SMS ====================

@router.get("/orders")
async def list_orders(limit: int = 50):
    """List recent persistent grocery orders stored in SQLite DB."""
    records = order_db.list_orders(limit=limit)
    return {"count": len(records), "orders": [r.model_dump() for r in records]}


@router.get("/orders/{order_id}")
async def get_order_details(order_id: str):
    """Retrieve specific order details and revision status from SQLite DB."""
    order = order_db.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    return order.model_dump()


@router.post("/sms/inbound")
async def handle_inbound_sms(sms: InboundSMS):
    """
    Handle inbound customer SMS for two-way modifications (e.g. 'CHANGE FM-1042: add 1L milk').
    Parses modifications, updates SQLite order, increments revision, and returns reply SMS.
    """
    result = sms_processor.process_inbound_sms(sms.sender, sms.message)
    logger.info(f"[Inbound SMS] Processed {sms.sender}: {result['action']} -> Reply: '{result['reply_sms']}'")

    # Queue reply SMS command for the companion app to send via SIM
    active_session = session_manager.get_active_session()
    sess_id = active_session.session_id if active_session else "sms_session"
    session_manager.queue_command(sess_id, "SEND_SMS", {
        "phone_number": sms.sender,
        "message": result["reply_sms"]
    })

    return result


@router.post("/sms/sent-callback")
async def handle_sms_sent_callback(order_id: str, success: bool = True):
    """Companion device reports SMS delivery success."""
    order_db.mark_sms_sent(order_id, success)
    return {"status": "updated", "order_id": order_id, "sms_sent": success}


# ==================== KOKORO-82M NEURAL TTS ENDPOINT ====================

@router.get("/tts/synthesize")
async def synthesize_speech(
    text: str = Query(..., description="Text to synthesize with Kokoro-82M neural engine"),
    voice: Optional[str] = Query("af", description="Voice name: af, am_adam, bf_emma, etc."),
    speed: float = Query(1.0, ge=0.5, le=2.0)
):
    """Generate high-fidelity 24kHz neural WAV audio using Kokoro-82M ONNX."""
    try:
        wav_bytes, sr = tts_engine.synthesize(text, voice=voice, speed=speed)
        return Response(content=wav_bytes, media_type="audio/wav")
    except Exception as e:
        logger.error(f"TTS Synthesis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== AUDIO ROUTING DIAGNOSTICS ====================

@router.post("/diagnostics/audio-route")
async def record_audio_route_diagnostic(diag: AudioRouteDiagnostic):
    """Record live audio routing diagnostics from the Android device."""
    _bridge_state["audio_diagnostics"] = diag.model_dump()
    logger.info(f"[Audio Route Diagnostic] Mode: {diag.audio_mode} | Speaker: {diag.speakerphone_on} | Dev: {diag.communication_device} | Vol Voice: {diag.stream_voice_call_volume}")
    return {"status": "recorded"}
