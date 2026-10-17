"""Vobiz frame serializer for Audible AI telephony integration."""

import base64
import json
from typing import Optional

from loguru import logger
from pipecat.audio.utils import create_stream_resampler, pcm_to_ulaw, ulaw_to_pcm
from pipecat.frames.frames import (
    AudioRawFrame,
    CancelFrame,
    EndFrame,
    Frame,
    InputAudioRawFrame,
    InputDTMFFrame,
    InterruptionFrame,
    KeypadEntry,
    OutputTransportMessageFrame,
    OutputTransportMessageUrgentFrame,
)
from pipecat.processors.frame_processor import FrameProcessorSetup
from pipecat.serializers.base_serializer import FrameSerializer


class VobizFrameSerializer(FrameSerializer):
    """Serializer for Vobiz Audio Streaming WebSocket protocol."""

    class InputParams(FrameSerializer.InputParams):
        """Configuration parameters for VobizFrameSerializer."""

        vobiz_sample_rate: int = 8000
        sample_rate: int | None = None
        auto_hang_up: bool = True

    def __init__(
        self,
        stream_id: str,
        call_id: Optional[str] = None,
        auth_id: Optional[str] = None,
        auth_token: Optional[str] = None,
        params: Optional[InputParams] = None,
    ):
        params = params or VobizFrameSerializer.InputParams()
        super().__init__(params)
        self._params: VobizFrameSerializer.InputParams = params

        self._stream_id = stream_id
        self._call_id = call_id
        self._auth_id = auth_id
        self._auth_token = auth_token

        self._vobiz_sample_rate = getattr(self._params, "vobiz_sample_rate", 8000)
        self._sample_rate = 0

        self._input_resampler = create_stream_resampler(
            clear_after_secs=getattr(self._params, "resampler_clear_after_secs", 0.5)
        )
        self._output_resampler = create_stream_resampler(
            clear_after_secs=getattr(self._params, "resampler_clear_after_secs", 0.5)
        )
        self._hangup_attempted = False

    async def setup(self, setup: FrameProcessorSetup):
        self._sample_rate = self._params.sample_rate or setup.audio_in_sample_rate

    async def serialize(self, frame: Frame) -> str | bytes | None:
        if (
            self._params.auto_hang_up
            and not self._hangup_attempted
            and isinstance(frame, (EndFrame, CancelFrame))
        ):
            self._hangup_attempted = True
            await self._hang_up_call()
            return None
        elif isinstance(frame, InterruptionFrame):
            answer = {"event": "clearAudio", "streamId": self._stream_id}
            return json.dumps(answer)
        elif isinstance(frame, AudioRawFrame):
            data = frame.audio
            serialized_data = await pcm_to_ulaw(
                data, frame.sample_rate, self._vobiz_sample_rate, self._output_resampler
            )
            if serialized_data is None or len(serialized_data) == 0:
                return None

            payload = base64.b64encode(serialized_data).decode("utf-8")
            answer = {
                "event": "playAudio",
                "media": {
                    "contentType": "audio/x-mulaw",
                    "sampleRate": self._vobiz_sample_rate,
                    "payload": payload,
                },
                "streamId": self._stream_id,
            }
            return json.dumps(answer)
        elif isinstance(frame, (OutputTransportMessageFrame, OutputTransportMessageUrgentFrame)):
            if self.should_ignore_frame(frame):
                return None
            return json.dumps(frame.message)

        return None

    async def _hang_up_call(self):
        """Terminate call using Vobiz REST API if credentials available."""
        if not self._call_id or not self._auth_id or not self._auth_token:
            return
        try:
            import aiohttp

            endpoint = f"https://api.vobiz.ai/v1/Account/{self._auth_id}/Call/{self._call_id}/"
            auth = aiohttp.BasicAuth(self._auth_id, self._auth_token)
            async with aiohttp.ClientSession() as session:
                async with session.delete(endpoint, auth=auth) as response:
                    logger.debug(f"Vobiz call hangup returned status: {response.status}")
        except Exception as e:
            logger.warning(f"Failed to hang up Vobiz call: {e}")

    async def deserialize(self, data: str | bytes) -> Frame | None:
        try:
            message = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return None

        event = message.get("event")
        if event == "media":
            media = message.get("media", {})
            payload_base64 = media.get("payload")
            if not payload_base64:
                return None
            payload = base64.b64decode(payload_base64)
            deserialized_data = await ulaw_to_pcm(
                payload, self._vobiz_sample_rate, self._sample_rate, self._input_resampler
            )
            if deserialized_data is None or len(deserialized_data) == 0:
                return None
            return InputAudioRawFrame(
                audio=deserialized_data, num_channels=1, sample_rate=self._sample_rate
            )
        elif event == "dtmf":
            dtmf_data = message.get("dtmf", {})
            digit = dtmf_data.get("digit")
            if digit:
                try:
                    return InputDTMFFrame(KeypadEntry(digit))
                except ValueError:
                    return None
        return None


__all__ = ["VobizFrameSerializer"]
