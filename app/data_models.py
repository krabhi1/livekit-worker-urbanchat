from attr import dataclass


@dataclass
class AgentInfo:
    id: str
    name: str
    language: str
    endCallAfterSilenceInSec: int
    maximumCallDurationInSec: int
    ttsProvider: str
    ttsModel: str
