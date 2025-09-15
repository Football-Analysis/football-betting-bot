from dataclasses import dataclass


@dataclass
class Match:
    date: str
    fixture_id: int
    home_team: int
    away_team: int
    score: dict
    game_week: int
    season: int
    league: dict
    result: str

    @staticmethod
    def from_mongo_doc(mongo_doc: dict) -> "Match":
        if "_id" in mongo_doc:
            del mongo_doc["_id"]
            return Match(**mongo_doc)