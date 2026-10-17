"""Cloudonix frame serializer for Audible AI."""

from typing import Any, Optional
from pydantic import BaseModel
from pipecat.frames.frames import AudioRawFrame, Frame
from pipecat.serializers.base_serializer import FrameSerializer


class CloudonixInputParams(BaseModel):
    sample_rate: int = 16000
    ignore_rtvi_messages: bool = True


class CloudonixFrameSerializer(FrameSerializer):
    """Serializes and deserializes Cloudonix telephony media frames."""

    InputParams = CloudonixInputParams

    def __init__(
        self,
        call_id: str = "",
        stream_sid: str = "",
        domain_id: str = "",
        bearer_token: str = "",
        hangup_strategy: Any = None,
        transfer_strategy: Any = None,
        params: Optional[CloudonixInputParams] = None,
        **kwargs,
    ):
        super().__init__(params=params, **kwargs)
        self.call_id = call_id
        self.stream_sid = stream_sid
        self.domain_id = domain_id
        self.bearer_token = bearer_token
        self.hangup_strategy = hangup_strategy
        self.transfer_strategy = transfer_strategy

    async def serialize(self, frame: Frame) -> str | bytes | None:
        if isinstance(frame, AudioRawFrame):
            return frame.audio
        return None

    async def deserialize(self, data: str | bytes) -> Frame | None:
        if isinstance(data, bytes):
            return AudioRawFrame(audio=data, sample_rate=16000, num_channels=1)
        return None


__all__ = ["CloudonixFrameSerializer"]
