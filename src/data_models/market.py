from dataclasses import dataclass
from .runner import Runner
from typing import List


@dataclass
class Market:
    market_id: int
    event_id: int
    event_name: str
    event_date: str
    runners: List[Runner]

    @staticmethod
    def from_mongo_doc(mongo_doc: dict) -> "Market":
        if "_id" in mongo_doc:
            del mongo_doc["_id"]
            return Market(**mongo_doc)