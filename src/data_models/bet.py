from dataclasses import dataclass
from datetime import datetime


@dataclass
class Bet:
    date: datetime
    home_team: int
    bet_on: int
    odds: float
    back: bool
    amount: float

    @staticmethod
    def from_mongo_doc(mongo_doc: dict) -> "Bet":
        if "_id" in mongo_doc:
            del mongo_doc["_id"]
            return Bet(**mongo_doc)