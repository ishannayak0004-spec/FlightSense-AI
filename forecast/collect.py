"""Save one real SerpApi snapshot per route and India-local observation day."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen
from zoneinfo import ZoneInfo


def target_departure(day):
    # Follow one Sunday's departure across a full week, always >= 2 days ahead.
    return day + timedelta(days=2 + (6 - (day.weekday() + 2)) % 7)


def fetch(key, dest, departure):
    params = dict(engine="google_flights", departure_id="DEL", arrival_id=dest,
                  outbound_date=departure.isoformat(), type=2, adults=1, travel_class=1,
                  stops=1, currency="INR", gl="in", hl="en", no_cache="true", api_key=key)
    try:
        with urlopen("https://serpapi.com/search.json?" + urlencode(params),timeout=50) as response:
            data=json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"Provider returned HTTP {exc.code}.") from None
    except (URLError,TimeoutError,ValueError):
        raise RuntimeError("Provider response unavailable.") from None
    if data.get("error") or data.get("search_metadata",{}).get("status") != "Success":
        raise RuntimeError("Provider did not confirm a successful search.")
    matched={}
    for offer in data.get("best_flights",[]) + data.get("other_flights",[]):
        legs=offer.get("flights",[])
        if len(legs)!=1 or not isinstance(offer.get("price"),(float,int)) or offer["price"]<=0:
            continue
        leg=legs[0]
        origin,end=leg["departure_airport"],leg["arrival_airport"]
        if origin["id"]!="DEL" or end["id"]!=dest or origin["time"][:10]!=departure.isoformat():
            continue
        identity=(leg["airline"],leg["flight_number"],origin["time"],end["time"],
                  leg.get("travel_class","Economy"))
        if identity not in matched or offer["price"]<matched[identity]:
            matched[identity]=offer["price"]
    return [dict(airline=k[0],flight=k[1],departs=k[2],arrives=k[3],cabin=k[4],fareINR=v)
            for k,v in sorted(matched.items())]


def collect(folder):
    key=os.getenv("SERPAPI_KEY")
    if not key:
        raise SystemExit("Missing Actions secret SERPAPI_KEY. No provider requests made.")
    now=datetime.now(ZoneInfo("Asia/Kolkata"))
    day=now.date()
    departure=target_departure(day)
    failed=[]
    for dest in ("IXR","PAT"):
        path=folder/day.isoformat()/f"DEL-{dest}.json"
        if path.exists():
            continue
        try:
            offers=fetch(key,dest,departure)
        except RuntimeError as e:
            failed.append(f"DEL-{dest}: {e}")
            continue
        item=dict(checkedAt=datetime.now(timezone.utc).isoformat(),searchDate=day.isoformat(),
                  departureDate=departure.isoformat(),origin="DEL",destination=dest,currency="INR",
                  adults=1,nonstop=True,offers=offers)
        path.parent.mkdir(parents=True,exist_ok=True)
        tmp=path.with_suffix(".tmp")
        tmp.write_text(json.dumps(item,indent=2))
        tmp.replace(path)
        print(f"DEL-{dest}: saved {len(offers)} observed itineraries")
    if failed:
        raise SystemExit("\n".join(failed))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("folder",type=Path)
    collect(parser.parse_args().folder)
