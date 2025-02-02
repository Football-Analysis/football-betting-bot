from requests import post, get
import os
from betfairlightweight import APIClient, filters
from betfairlightweight.resources.bettingresources import EventResult, MarketBook, RunnerBook
from typing import List


class BetfairClient:
    def __init__(self):
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
                                 certs="/home/tristan/betfair-cert/")
        
        self.trading.login()

    def get_funds(self):
        funds = self.trading.account.get_account_funds(lightweight=True)
        print(funds)

    def list_market_book(self, market_id):
        market_book: List[MarketBook] = self.trading.betting.list_market_book([market_id], )
        runners: List[RunnerBook] = market_book[0].runners
        print(runners[0].__dict__)

    def list_runner_book(self, market_id, selection_id):
        runner_book = self.trading.betting.list_runner_book(market_id, selection_id)
        print(type(runner_book.__dict__))

    def get_events(self):
        event_filter = filters.market_filter(event_type_ids=["1"], market_countries=["GB"])
        events: List[EventResult]  = self.trading.betting.list_events(filter=event_filter)
        print(events[0].event.name)
