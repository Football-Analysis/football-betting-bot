from dataclasses import dataclass
from typing import Optional


@dataclass
class Runner:
    selection_id: int
    name: str
    db_id: int
    home: bool
    away: bool
    draw: bool
    back_price: Optional[float]
    back_size: Optional[float]
    lay_price: Optional[float]
    lay_size: Optional[float]

    @staticmethod
    def from_mongo_doc(mongo_doc: dict) -> "Runner":
        if "_id" in mongo_doc:
            del mongo_doc["_id"]
            return Runner(**mongo_doc)