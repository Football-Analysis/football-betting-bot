import os
from .logging_setup import get_logger
from betfairlightweight import APIClient, filters
from betfairlightweight.resources.bettingresources import EventResult, MarketBook, RunnerBook, MarketCatalogue, PlaceOrders
from typing import List
from .mongo_client import MongoFootballClient
from jaro import jaro_winkler_metric
from datetime import datetime, timedelta
from .data_models.event import Event
from .data_models.runner import Runner
from .data_models.market import Market
from .data_models.prediction import Prediction
from .config import Config as conf
from requests import get
from .mail_client import MailClient


log = get_logger("exchange_client")

class BetfairClient:
    def __init__(self):
        self.mfc = MongoFootballClient(conf.MONGO_URL)

        self.API_KEY = conf.BETFAIR_API_KEY
        if self.API_KEY is None:
            raise RuntimeError("BETFAIR_API_KEY environment variable must be set")

        self.username = conf.BETFAIR_USERNAME
        if self.username is None:
            raise RuntimeError("BETFAIR_USERNAME environment variable must be set")

        self.password = conf.BETFAIR_PASSWORD
        if self.password is None:
            raise RuntimeError("BETFAIR_PASSWORD environment variable must be set")
        
        self.trading = APIClient(self.username,
                                 self.password,
                                 app_key=self.API_KEY,
                                 certs=conf.CERT_LOCATION)
        
        self.trading.login()
        self.bankroll = 100
        self.mail_client = MailClient(conf.EMAIL_USERNAME, conf.EMAIL_PASSWORD)
        self.vetoed_leaguse = [39, 197, 135, 204, 186, 94, 203, 62, 281, 169, 71, 134, 172, 328]

    def get_funds(self):
        funds = self.trading.account.get_account_funds(lightweight=True)
        log.debug(funds)

    def list_market_book(self, market: Market):
        try:
            market_book: List[MarketBook] = self.trading.betting.list_market_book([market.market_id], order_projection="EXECUTABLE", price_projection={"priceData": ["EX_ALL_OFFERS"]})
        except Exception as e:
            log.debug(e)
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
        next_week = now + timedelta(days=conf.DAY_LIMIT)
        time_filter = next_week.strftime("%Y-%m-%d")
        log.debug(f"Getting events that start before {time_filter}")
        event_filter = filters.market_filter(event_type_ids=["1"], in_play_only=False, market_start_time={"to": time_filter})
        try:
            events: List[EventResult]  = self.trading.betting.list_events(filter=event_filter)
        except Exception as e:
            log.debug(e)
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
        next_week = now + timedelta(days=conf.DAY_LIMIT)
        time_filter = next_week.strftime("%Y-%m-%d")
        market_filter = filters.market_filter(event_ids=[event.id], market_type_codes=["MATCH_ODDS"], market_start_time={"to": time_filter})
        try:
            markets: List[MarketCatalogue] = self.trading.betting.list_market_catalogue(filter=market_filter, market_projection=["RUNNER_METADATA"], sort="FIRST_TO_START")
        except Exception as e:
            log.debug(e)
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
                    log.debug(f"Cannot assign {runner_name} to the home or away team")
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
            log.debug(e)
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
                          markets[0].total_matched,
                          runners), None
        else:
            return None, (home_ids, away_ids[0], date)
        
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
            log.debug(e)
            return None

        if home_team !=0:
            league = self.mfc.get_match(market.event_date, home_team)
            if league is not None:
                league = league.league["id"]
            prediction = self.mfc.get_pred(market.event_date, home_team)
        else:
            prediction = None
        
        if prediction is None:
            pass
            log.debug(f"Not checking odds for {market.event_name}")
        else:
            price = 0
            back_bet, back_diff, back_team_id, back_team_name, back_price = self.check_odds(market.runners, prediction, home_team, away_team, draw, "back")
            lay_bet, lay_diff, lay_team_id, lay_team_name, lay_price = self.check_odds(market.runners, prediction, home_team, away_team, draw, "lay")
            log.debug(f"Biggest diffs for back and lay for {market.event_name} are {back_diff} and {lay_diff}")

            if back_bet and lay_bet:
                bet = True
                if back_diff > lay_diff:
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
                vetoed = False
                if back:
                    log.info(f"Found bet opportunity for {market.event_name} with diff of {round(max_diff*100, 2)}% - backing {team_name} at {price}")
                    if league in self.vetoed_leaguse:
                        vetoed = True
                        log.info(f"Cannot bet on {team_name} as they are in a vetoes league (Proven negative ROI when betting)")
                else:
                    log.info(f"Found bet opportunity for {market.event_name} with diff of {round(max_diff*100, 2)}% - laying {team_name} at {price}, back odds equivalent: {1+(1/(price-1))}")
                    if league in self.vetoed_leaguse:
                        vetoed=True
                        log.info(f"Cannot bet on {team_name} as they are in a vetoes league (Proven negative ROI when betting)")
                if not vetoed:
                    successful_bet = self.bet_on_game(market.event_date, home_team, team_id, price, team_name, back, conf.BANKROLL_PERCENTAGE, market)
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
                    if back:
                        diff = prediction.home_win - (1/runner_price)
                        diffs.append(diff)
                        if diff > max_diff:
                            max_diff = diff
                            if diff > conf.THRESHOLD:
                                price = runner_price
                                team = runner.name
                                team_id = runner.db_id
                    else:
                        pred_against = prediction.away_win + prediction.draw
                        back_odd = 1 + (1 / (runner_price - 1))
                        diff = pred_against - (1/back_odd)
                        if diff > max_diff:
                            max_diff = diff
                            if diff > conf.THRESHOLD:
                                price = runner_price
                                team = runner.name
                                team_id = runner.db_id
                elif runner.db_id == away_team:
                    if back:
                        diff = prediction.home_win - (1/runner_price)
                        diffs.append(diff)
                        if diff > max_diff:
                            max_diff = diff
                            if diff > conf.THRESHOLD:
                                price = runner_price
                                team = runner.name
                                team_id = runner.db_id
                    else:
                        pred_against = prediction.home_win + prediction.draw
                        back_odd = 1 + (1 / (runner_price - 1))
                        diff = pred_against - (1/back_odd)
                        if diff > max_diff:
                            max_diff = diff
                            if diff > conf.THRESHOLD:
                                price = runner_price
                                team = runner.name
                                team_id = runner.db_id
                elif runner.db_id == draw:
                    if back:
                        diff = prediction.draw - (1/runner_price)
                        diffs.append(diff)
                        if diff > max_diff:
                            max_diff = diff
                            if diff > conf.THRESHOLD:
                                price = runner_price
                                team = runner.name
                                team_id = runner.db_id
                    else:
                        pred_against = prediction.away_win + prediction.home_win
                        back_odd = 1 + (1 / (runner_price - 1))
                        diff = pred_against - (1/back_odd)
                        if diff > max_diff:
                            max_diff = diff
                            if diff > conf.THRESHOLD:
                                price = runner_price
                                team = runner.name
                                team_id = runner.db_id
                else:
                    raise RuntimeError(f"Team {runner.name} isnt home, away or draw, they must be one of these")
            except:
                raise RuntimeError("uh oh")


            if max_diff > conf.THRESHOLD:
                return True, max_diff, team_id, team, price
            else:
                return False, max_diff, None, None, None
            

    def bet_on_game(self, date, home_team, team_to_bet, price, team_name, back, bet_percentage, market: Market):
        current_bankroll = self.mfc.check_bankroll()
        bet_size = round(current_bankroll.bankroll * bet_percentage, 2)
        if bet_size > current_bankroll.bankroll - current_bankroll.amount_in_play:
            log.info(f"Insufficient funds available from bankroll to bet, too many in play bets")
        else:
            bet_already_placed = self.mfc.bet_exists(date, home_team)
            if bet_already_placed:
                log.info(f"Cant place another bet on {team_name}, bet already placed")
                return False
            if back:
                save_price = price
                exchange_bet_size = bet_size
            else:
                save_price = 1+(1/(price-1))
                exchange_bet_size = round(bet_size/(price-1),2)
                if exchange_bet_size < 1:
                    log.info(f"Cannot lay {team_to_bet} at {price}, to make liability be {bet_size} the exchange bet size would have to be less than 1")
                    return False
            exchange_bet = self.bet_on_exchange(market, team_to_bet, back, price, exchange_bet_size)
            self.mfc.make_bet(date, home_team, team_to_bet, save_price, bet_size, team_name, back)
            current_bankroll.amount_in_play += bet_size
            #current_bankroll.total_bet += bet_size
            current_bankroll.date = datetime.now()
            self.mfc.update_amount_in_play(current_bankroll)
            if back:
                self.mail_client.send_mail(f"Bet Found for {team_name}", ["tristrmistr@gmail.com"], f"Back {team_name} at {price} or better for £{round(bet_size, 2)}")
            else:
                self.mail_client.send_mail(f"Bet Found for {team_name}", ["tristrmistr@gmail.com"], f"Lay {team_name} at {1+(1/(price-1))} or lower with liability of £{round(bet_size, 2)}")
            return True

    def get_and_check_odds(self):
        events = self.get_events()
        for event in events:
            runner_info = self.get_market_catalogue(event)

    def bet_on_exchange(self, market: Market, team_to_bet, back, price, size=1):
        try:
            selection_id = None
            for runner in market.runners:
                if runner.db_id == team_to_bet:
                    selection_id = runner.selection_id
                    team_name = runner.name

            if selection_id is None:
                raise RuntimeError(f"{team_to_bet} could not be found in the list of runners")
            
            if back:
                side="BACK"
            else:
                side="LAY"

            limit_order = {"size": size, "price": price, "persistenceType": "LAPSE"}
            instruction = {"selectionId": selection_id, "side": side, "orderType": "LIMIT", "limitOrder": limit_order}
            exchange_bet: PlaceOrders = self.trading.betting.place_orders(market.market_id,[instruction])
            if exchange_bet.place_instruction_reports[0].error_code is None:
                log.info(f"Successfully placed bet on {team_name} in the game {market.event_name} on the exchange, this does not mean all money has been matched")
                return True
            else:
                log.info(f"Could not place bet on {team_name} in the game {market.event_name} on the exchange, error code {exchange_bet.place_instruction_reports[0].error_code}")
                return False
        except Exception as e:
            log.debug(e)
            self.trading.login()
            return False


