from dataclasses import dataclass
from typing import Optional
import json


@dataclass
class WorkerPayload:
    agentId: Optional[str] = None
    phoneNumber: Optional[str] = None


def get_worker_payload(data: str):
    json_data = json.loads(data)
    agentId = json_data.get("agentId")
    phoneNumber = json_data.get("phoneNumber")
    if not agentId and not phoneNumber:
        # raise ValueError(
        #     "One of 'agentId' or 'phoneNumber' must be provided in the payload."
        # )
        return None
    return WorkerPayload(agentId=agentId, phoneNumber=phoneNumber)
