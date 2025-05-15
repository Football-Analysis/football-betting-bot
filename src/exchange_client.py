import os
from betfairlightweight import APIClient, filters
from betfairlightweight.resources.bettingresources import EventResult, MarketBook, RunnerBook, MarketCatalogue
from typing import List
from .mongo_client import MongoFootballClient
from jaro import jaro_winkler_metric
from datetime import datetime, timedelta
from .data_models.event import Event
from .data_models.runner import Runner
from .data_models.market import Market
from .data_models.prediction import Prediction
from .config import Config as conf

class BetfairClient:
    def __init__(self):
        self.mfc = MongoFootballClient(conf.MOGNO_URL)

        self.API_KEY = os.getenv("BETFAIR_API_KEY", None)
        if self.API_KEY is None:
            raise RuntimeError("BETFAIR_API_KEY environment variable must be set")

        self.username = os.getenv("BETFAIR_USERNAME", None)
        if self.username is None:
            raise RuntimeError("BETFAIR_USERNAME environment variable must be set")

        self.password = os.getenv("BETFAIR_PASSWORD", None)
        if self.password is None:
            raise RuntimeError("BETFAIR_PASSWORD environment variable must be set")
        
        self.trading = APIClient(self.username,
                                 self.password,
                                 app_key=self.API_KEY,
                                 certs=conf.CERT_LOCATION)
        
        self.trading.login()

        self.bankroll = 100

    def get_funds(self):
        funds = self.trading.account.get_account_funds(lightweight=True)
        print(funds)

    def list_market_book(self, market: Market):
        try:
            market_book: List[MarketBook] = self.trading.betting.list_market_book([market.market_id], order_projection="EXECUTABLE", price_projection={"priceData": ["EX_ALL_OFFERS"]})
        except Exception as e:
            print(e)
            self.trading.login()
            return None
        try:
            runners: List[RunnerBook] = market_book[0].runners
        except:
            return None
        for runner in runners:
            for market_runner in market.runners:
                if runner.selection_id == market_runner.selection_id:
                    try:
                        market_runner.back_price = runner.ex.available_to_back[0].price
                        market_runner.back_size = runner.ex.available_to_back[0].size
                        market_runner.lay_price = runner.ex.available_to_lay[0].price
                        market_runner.lay_size = runner.ex.available_to_lay[0].size
                    except:
                        return None
        return market

    def get_events(self) -> List[Event]:
        now = datetime.now()
        next_week = now + timedelta(days=7)
        time_filter = next_week.strftime("%Y-%m-%d")
        event_filter = filters.market_filter(event_type_ids=["1"], in_play_only=False, market_start_time={"to": time_filter})
        try:
            events: List[EventResult]  = self.trading.betting.list_events(filter=event_filter)
        except Exception as e:
            print(e)
            self.trading.login()
            return None, None
        processed_events = []
        for event in events:
            if event.event.open_date > datetime.now():
                processed_events.append(Event(event.event.id, 
                                            event.event.name, 
                                            event.event.open_date))
        return processed_events

    def get_market_catalogue(self, event: Event):
        now = datetime.now()
        next_week = now + timedelta(days=7)
        time_filter = next_week.strftime("%Y-%m-%d")
        market_filter = filters.market_filter(event_ids=[event.id], market_type_codes=["MATCH_ODDS"], market_start_time={"to": time_filter})
        try:
            markets: List[MarketCatalogue] = self.trading.betting.list_market_catalogue(filter=market_filter, market_projection=["RUNNER_METADATA"], sort="FIRST_TO_START")
        except Exception as e:
            print(e)
            self.trading.login()
            return None, None
        home_team = None
        away_team = None
        runners = []
        if len(markets) == 0:
            return None, None
        try:
            for runner in markets[0].runners:
                runner_name: str = runner.runner_name
                runner_id: int = runner.selection_id
                date = datetime.strftime(event.date,"%Y-%m-%dT%H:%M:%S+00:00")
                db_id: int = self.mfc.get_team_id_from_name(runner_name)
                if len(db_id) == 0:
                    db_id = 0
                else:
                    db_id = db_id[0]
                home_away = event.name.split(" v ")
                home = home_away[0]
                away = home_away[-1]
                if home.lower() in runner_name.lower() or jaro_winkler_metric(home.lower(), runner_name.lower()) > 0.8:
                    is_home = True
                    is_away = False
                    is_draw = False
                    home_team = runner_name
                elif away.lower() in runner_name.lower() or jaro_winkler_metric(away.lower(), runner_name.lower()) > 0.8:
                    is_away = True
                    is_home = False
                    is_draw = False
                    away_team = runner_name
                elif runner_name == "The Draw":
                    is_draw = True
                    is_home = False
                    is_away = False
                else:
                    print(f"Cannot assign {runner_name} to the home or away team")
                    return None, None
                runners.append(Runner(runner_id,
                                  runner_name,
                                  db_id,
                                  is_home,
                                  is_away,
                                  is_draw,
                                  0.0,
                                  0.0,
                                  0.0,
                                  0.0))
        except Exception as e:
            print(e)
            return None, None
        
        
        home_ids = self.mfc.get_team_id_from_name(home_team)
        away_ids = self.mfc.get_team_id_from_name(away_team)

        if len(home_ids) == 0 or len(away_ids) == 0:
            return None, "no id"
        else:
            for home_id in home_ids:
                prediction = self.mfc.get_pred(date, home_id)
                if prediction is not None:
                    break

        if prediction is not None:
            return Market(markets[0].market_id,
                          event.id,
                          event.name,
                          date,
                          runners), None
        else:
            return None, (home_ids[0], away_ids[0], date)
        
    def compare_predictions(self, market: Market):
        home_team = 0
        try:
            for runner in market.runners:
                if runner.home:
                    home_team = runner.db_id
                elif runner.away:
                    away_team = runner.db_id
                elif runner.draw:
                    draw = runner.db_id
                else:
                    raise RuntimeError(f"Team {runner.name} isnt home, away or draw, they must be one of these")
        except Exception as e:
            print(e)
            return None

        if home_team !=0:
            prediction = self.mfc.get_pred(market.event_date, home_team)
        else:
            prediction = None
        
        if prediction is None:
            print(f"Cannot find prediction for {market.event_name}")
        else:
            price = 0
            team = ""
            back_bet, back_diff, back_team_id, back_team_name, back_price = self.check_odds(market.runners, prediction, home_team, away_team, draw, "back")
            lay_bet, lay_diff, lay_team_id, lay_team_name, lay_price = self.check_odds(market.runners, prediction, home_team, away_team, draw, "lay")

            if back_bet and lay_bet:
                bet = True
                if back_diff > abs(lay_diff):
                    max_diff = back_diff
                    team_id = back_team_id
                    team_name = back_team_name
                    price = back_price
                    back = True
                else:
                    max_diff = lay_diff
                    team_id = lay_team_id
                    team_name = lay_team_name
                    price = lay_price
                    back = False
            elif back_bet:
                bet=True
                max_diff = back_diff
                team_id = back_team_id
                team_name = back_team_name
                price = back_price
                back = True
            elif lay_bet:
                bet = True
                max_diff = lay_diff
                team_id = lay_team_id
                team_name = lay_team_name
                price = lay_price
                back = False
            else:
                bet = False

            if bet:
                if back:
                    print(f"Found bet opportunity for {market.event_name} with diff {max_diff} - backing {team_name} at {price}")
                else:
                    print(f"Found bet opportunity for {market.event_name} with diff {max_diff} - laying {team_name} at {price}, back odds equivalent: {1+(1/(price-1))}")
                    price = 1+(1/(price-1))
                self.bet_on_game(market.event_date, home_team, team_id, price, 1.0, team, back)
            else:
                pass

    def check_odds(self, runners: List[Runner], prediction: Prediction, home_team, away_team, draw, method):
        diffs = []
        max_diff = 0
        for runner in runners:
            if method == "back":
                runner_price = runner.back_price
                back = True
            elif method == "lay":
                runner_price = runner.lay_price
                back = False
            else:
                raise RuntimeError(f"You must be finding back or lay odds, {method} is not supported")

            try:
                if runner.db_id == home_team:
                    diff = prediction.home_win - (1/runner_price)
                    diffs.append(diff)
                    if back:
                        if diff > max_diff:
                            max_diff = diff
                            if 0.3 < diff:
                                price = runner_price
                                team = runner.name
                                team_id = runner.db_id
                    else:
                        if diff < max_diff:
                            max_diff = diff
                            if -0.3 > diff:
                                price = runner_price
                                team = runner.name
                                team_id = runner.db_id
                elif runner.db_id == away_team:
                    diff = prediction.away_win - (1/runner_price)
                    diffs.append(diff)
                    if back:
                        if diff > max_diff:
                            max_diff = diff
                            if 0.3 < diff:
                                price = runner_price
                                team = runner.name
                                team_id = runner.db_id
                    else:
                        if diff < max_diff:
                            max_diff = diff
                            if -0.3 > diff:
                                price = runner_price
                                team = runner.name
                                team_id = runner.db_id
                elif runner.db_id == draw:
                    diff = prediction.draw - (1/runner_price)
                    diffs.append(diff)
                    if back:
                        if diff > max_diff:
                            max_diff = diff
                            if 0.3 < diff:
                                price = runner_price
                                team = runner.name
                                team_id = runner.db_id
                    else:
                        if diff < max_diff:
                            max_diff = diff
                            if -0.3 > diff:
                                price = runner_price
                                team = runner.name
                                team_id = runner.db_id
                else:
                    raise RuntimeError(f"Team {runner.name} isnt home, away or draw, they must be one of these")
            except:
                raise RuntimeError("uh oh")

            if back:
                if max_diff > 0.3:
                    return True, max_diff, team_id, team, price
                else:
                    return False, None, None, None, None
            else:
                if max_diff < -0.3:
                    return True, max_diff, team_id, team, price
                else:
                    return False, None, None, None, None

    def bet_on_game(self, date, home_team, team_to_bet, price, size, team_name, back):
        self.mfc.make_bet(date, home_team, team_to_bet, price, size, team_name, back)

    def get_and_check_odds(self):
        events = self.get_events()
        for event in events:
            runner_info = self.get_market_catalogue(event)


