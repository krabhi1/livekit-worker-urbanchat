from attr import dataclass


@dataclass
class Call:
    id: str
    user_id: str

    @staticmethod
    def from_json(data):
        return Call(
            id=data["id"],
            user_id=data["userId"],
        )
