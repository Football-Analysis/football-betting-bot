from dataclasses import dataclass
from datetime import datetime


@dataclass
class Event:
    id: int
    name: str
    date: datetime

    @staticmethod
    def from_mongo_doc(mongo_doc: dict) -> "Event":
        if "_id" in mongo_doc:
            del mongo_doc["_id"]
            return Event(**mongo_doc)