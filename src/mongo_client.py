from pymongo import MongoClient, ASCENDING
from typing import List
from .data_models.prediction import Prediction
from .data_models.bet import Bet


class MongoFootballClient:
    def __init__(self, url: str):
        self.url = url
        self.mc = MongoClient(self.url)
        self.football_db = self.mc["football"]
        self.match_collection = self.football_db["matches"]
        self.league_collection = self.football_db["leagues"]
        self.observation_collection = self.football_db["observations"]
        self.next_observation_collection = self.football_db["next_observations"]
        self.prediction_collection = self.football_db["predictions"]
        self.next_prediction_collection = self.football_db["next_predictions"]
        self.odds_collection = self.football_db["odds"]
        self.team_collection = self.football_db["teams"]
        self.bet_collection = self.football_db["bets"]

    def get_team_id_from_name(self, name: str):
        teams = self.team_collection.find({"name": name})
        teams_to_return: set = set()

        for team in teams:
            team_id = team["id"]
            teams_to_return.add(team_id)

        # if len(teams_to_return) == 0:
        #     print(name)

        return list(teams_to_return)
        
    def get_pred(self, date, home_team):
        pred = self.next_prediction_collection.find_one({
            "match_id": f"{date}-{home_team}"
            })
        if pred is not None:
            prediction = Prediction.from_mongo_doc(pred)
        else:
            return None
        return prediction

    def make_bet(self, date, home_team, team_to_bet, price, size, team_name):
        bet_already_placed = self.bet_collection.find_one({"date": date, "home_team": home_team})

        if bet_already_placed is not None:
            print(f"Cant place another bet on {team_name}, bet already placed")
        else:
            bet = Bet(date=date,
                      home_team=home_team,
                      bet_on=team_to_bet,
                      odds=price,
                      amount=size)
            self.bet_collection.insert_one(bet.__dict__)
