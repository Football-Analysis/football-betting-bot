from src.exchange_client import BetfairClient
from time import sleep
from datetime import datetime

bc = BetfairClient()

while True:
    print(f"Running analysis for all events at {datetime.now()}")
    total = 0
    events = bc.get_events()
    no_id = 0
    no_pred = 0
    no_idea=0
    id_prob = 0
    print(f"Found {len(events)} events")
    for event in events:
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
    print(f"Found predictions for {total} events")
    print(f"Found predictions for {(total/len(events))*100}% of events")
    print(f"no pred total {no_pred}")
    print(f"ID problem {id_prob}")
    print(f"Unknown error {no_idea}")