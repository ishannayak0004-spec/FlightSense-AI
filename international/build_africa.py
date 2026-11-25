"""Generate directional, carrier-specific fare statistics from Mazano's v1 ZIP."""
import argparse
import csv
import hashlib
import io
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from zipfile import ZipFile


AIRPORTS = {
    "CPT": ("Cape Town", "ZA"),
    "DUR": ("Durban", "ZA"),
    "GBE": ("Gaborone", "BW"),
    "HRE": ("Harare", "ZW"),
    "JNB": ("Johannesburg", "ZA"),
    "LUN": ("Lusaka", "ZM"),
    "MPM": ("Maputo", "MZ"),
    "VFA": ("Victoria Falls", "ZW"),
    "WDH": ("Windhoek", "NA"),
}
# All nine airports were at UTC+02:00 during this departure window.
LOCAL_TZ = timezone(timedelta(hours=2))
ROOT = Path(__file__).resolve().parents[1]
SOURCE = "Southern Africa"


def summarize(archive):
    quotes = defaultdict(list)
    seen = set()
    with ZipFile(archive) as zipped:
        csv_bytes = zipped.read("flights.csv")
    digest = hashlib.sha256(csv_bytes).hexdigest()
    if digest != "2a63eea60d2a4be967f5985f6bada35cbf516f9a9db451a10a3d8a6e1dd9627a":
        raise ValueError("Input differs from the documented Kaggle v1 file")
    for row in csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig"))):
        origin, origin_country = AIRPORTS[row["from"]]
        destination, destination_country = AIRPORTS[row["to"]]
        if origin_country == destination_country:
            continue
        price = int(row["price"])
        departure, arrival = int(row["departure"]), int(row["arrival"])
        if price <= 0 or arrival <= departure or not row["airline"]:
            raise ValueError(f"Invalid fare, itinerary time, or airline in row {row['id']}")
        key = (origin, destination, row["airline"], departure, arrival, price)
        if key in seen:
            continue
        seen.add(key)
        month = datetime.fromtimestamp(departure, LOCAL_TZ).strftime("%Y-%m")
        quotes[(origin, destination, month, row["airline"])].append(price)
    return [
        dict(origin=o, destination=d, month=m, airline=a, currency="ZAR",
             source=SOURCE, count=len(prices), low=min(prices),
             median=median(prices), high=max(prices))
        for (o, d, m, a), prices in sorted(quotes.items())
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/global/africa.json")
    args = parser.parse_args()
    report = summarize(args.archive)
    args.output.parent.mkdir(exist_ok=True, parents=True)
    args.output.write_text(json.dumps(report, separators=(",", ":")) + "\n")
