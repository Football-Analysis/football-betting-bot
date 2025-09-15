from src.exchange_client import BetfairClient
from time import sleep
from datetime import datetime
from logging import getLogger
from src.logging_setup import setup_logging, get_logger


setup_logging()
log = get_logger("main")
log.info("Initialising the Betfair Client")
bc = BetfairClient()

while True:
    log.info(f"Running analysis for all events")
    total = 0
    events = bc.get_events()
    no_id = 0
    no_pred = 0
    no_idea=0
    id_prob = 0
    log.info(f"Found {len(events)} events")
    for event in events:
        if event is None:
            continue
        market, problem = bc.get_market_catalogue(event)
        if market is not None:
            total += 1
            updated_market = bc.list_market_book(market)
            if updated_market is not None:
                bc.compare_predictions(updated_market)
        else:
            if isinstance(problem, tuple):
                no_pred +=1
            elif problem == "no id":
                id_prob += 1
            else:
                no_idea +=1
    log.debug(f"Found predictions for {total} events")
    log.info(f"Found predictions for {(total/len(events))*100}% of events")
    log.debug(f"no pred total {no_pred}")
    log.debug(f"ID problem {id_prob}")
    log.debug(f"Unknown error {no_idea}")