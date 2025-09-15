from pymongo import MongoClient, DESCENDING
from typing import List
from .data_models.prediction import Prediction
from .data_models.bet import Bet
from .data_models.bankroll import Bankroll
from .data_models.match import Match
from datetime import datetime


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
        self.bankroll_collection = self.football_db["bankroll"]

    def get_team_id_from_name(self, name: str):
        teams = self.team_collection.find({"name": name})
        teams_to_return: set = set()

        for team in teams:
            team_id = team["id"]
            teams_to_return.add(team_id)

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
    
    def bet_exists(self, date: str, home_team) -> bool:
        bet_already_placed = self.bet_collection.find_one({"date": date, "home_team": home_team})

        if bet_already_placed is not None:
            return True
        return False

    def make_bet(self, date, home_team, team_to_bet, price, size, team_name, back):
        bet = Bet(date=date,
                      home_team=home_team,
                      bet_on=team_to_bet,
                      odds=price,
                      back=back,
                      amount=size)
        self.bet_collection.insert_one(bet.__dict__)

    def check_bankroll(self):
        current_bankroll = self.bankroll_collection.find().sort("date", DESCENDING).limit(1)
        bankroll_to_return = next(current_bankroll, None)
        if bankroll_to_return is not None:
            try:
                return Bankroll.from_mongo_doc(bankroll_to_return)
            except:
                raise RuntimeError(f"{bankroll_to_return} could not be cast to a bankroll type")
        return Bankroll(date=datetime.now(),
                        bankroll=1000.00,
                        amount_in_play=0,
                        total_bet=0)

    def update_amount_in_play(self, bankroll):
        self.bankroll_collection.insert_one(bankroll.__dict__)

    def get_match(self, date, home_team) -> Match:
        match = self.match_collection.find_one({
            "date": date,
            "home_team": home_team
        })
        if match is None:
            return None
        return Match.from_mongo_doc(match)
