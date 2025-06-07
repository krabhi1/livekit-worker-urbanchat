from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.api import update_call


class CallStatus(str, Enum):
    REGISTERED = "registered"
    ONGOING = "ongoing"
    ENDED = "ended"
    ERROR = "error"


class CallDisconnectReason(str, Enum):
    USER_HANGUP = "user_hangup"
    AGENT_HANGUP = "agent_hangup"
    CALL_TRANSFER = "call_transfer"
    INACTIVITY = "inactivity"
    MAX_DURATION_REACHED = "max_duration_reached"
    CONCURRENT_CALL_LIMIT_REACHED = "concurrent_call_limit_reached"
    DIAL_BUSY = "dial_busy"
    DIAL_NO_ANSWER = "dial_no_answer"
    ERROR_UNKNOWN = "error_unknown"
    UNKNOWN = "unknown"


@dataclass
class CallInfo:
    id: str
    user_id: str
    call_status: CallStatus
    cost: float
    call_disconnect_reason: Optional[CallDisconnectReason] = None
    call_start_time: Optional[int] = None
    call_end_time: Optional[int] = None
    transcript: Optional[str] = None
    latency: Optional[str] = None

    @staticmethod
    def from_json(data):
        return CallInfo(
            id=data["id"],
            user_id=data["userId"],
            call_status=CallStatus(data["callStatus"]),
            cost=data.get("cost", 0.0),
            call_disconnect_reason=(
                CallDisconnectReason(reason)
                if (reason := data.get("callDisconnectReason"))
                else None
            ),
            call_start_time=data.get("callStartTime", None),
            call_end_time=data.get("callEndTime", None),
            transcript=data.get("transcript", None),
            latency=data.get("latency", None),
        )

    async def update(self):
        body = {
            "callStatus": self.call_status.value,
            "cost": self.cost,
            "callDisconnectReason": (
                self.call_disconnect_reason.value if self.call_disconnect_reason else None
            ),
            "callStartTime": self.call_start_time,
            "callEndTime": self.call_end_time,
            "transcript": self.transcript,
            "latency": self.latency,
        }
        new_call = CallInfo.from_json(await update_call(self.id, self.user_id, body))
        self.call_status = new_call.call_status
        self.cost = new_call.cost
        self.call_disconnect_reason = new_call.call_disconnect_reason
        self.call_start_time = new_call.call_start_time
        self.call_end_time = new_call.call_end_time
        self.transcript = new_call.transcript
        self.latency = new_call.latency
