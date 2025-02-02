from src.exchange_client import BetfairClient

bc = BetfairClient()
#bc.get_funds()
bc.list_market_book("1.238429998")
#bc.list_runner_book("1.238429998",1096)
#bc.get_events()