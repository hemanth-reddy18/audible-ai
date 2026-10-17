"""Asterisk frame serializer for Audible AI Asterisk ARI transport."""

from typing import Any, Optional
from pydantic import BaseModel
from pipecat.frames.frames import AudioRawFrame, Frame
from pipecat.serializers.base_serializer import FrameSerializer


class AsteriskInputParams(BaseModel):
    asterisk_sample_rate: int = 8000
    sample_rate: int = 16000
    ignore_rtvi_messages: bool = True
    resampler_clear_after_secs: Optional[float] = None


class AsteriskFrameSerializer(FrameSerializer):
    """Serializes and deserializes Asterisk ARI binary audio websocket frames."""

    InputParams = AsteriskInputParams

    def __init__(
        self,
        channel_id: str = "",
        ari_endpoint: str = "",
        app_name: str = "",
        app_password: str = "",
        transfer_strategy: Any = None,
        hangup_strategy: Any = None,
        params: Optional[AsteriskInputParams] = None,
        **kwargs,
    ):
        super().__init__(params=params, **kwargs)
        self.channel_id = channel_id
        self.ari_endpoint = ari_endpoint
        self.app_name = app_name
        self.app_password = app_password
        self.transfer_strategy = transfer_strategy
        self.hangup_strategy = hangup_strategy
        self.params = params or AsteriskInputParams()

    async def serialize(self, frame: Frame) -> str | bytes | None:
        if isinstance(frame, AudioRawFrame):
            return frame.audio
        return None

    async def deserialize(self, data: str | bytes) -> Frame | None:
        if isinstance(data, bytes):
            return AudioRawFrame(
                audio=data,
                sample_rate=self.params.asterisk_sample_rate,
                num_channels=1,
            )
        return None


__all__ = ["AsteriskFrameSerializer"]
