from dataclasses import dataclass
from datetime import datetime


@dataclass
class Bankroll:
    date: datetime
    bankroll: float
    amount_in_play: float

    @staticmethod
    def from_mongo_doc(mongo_doc: dict) -> "Bankroll":
        if "_id" in mongo_doc:
            del mongo_doc["_id"]
            return Bankroll(**mongo_doc)