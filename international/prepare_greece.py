"""Rebuild the observed monthly summaries from NMyrsini/Flight-Dataset."""
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median

source = Path(sys.argv[1])
groups = defaultdict(list)
for row in csv.reader(source.open(encoding="utf-8")):
    departure = datetime.strptime(row[9], "%m/%d/%Y")
    groups[row[3], row[4], departure.strftime("%Y-%m")].append(float(row[13]))
rows = [dict(origin=a, destination=b, month=m, count=len(prices), low=min(prices),
             median=median(prices), high=max(prices), currency="EUR", airline="", source="Greece study")
        for (a, b, m), prices in sorted(groups.items())]
out = Path(__file__).resolve().parents[1] / "dist/global/greece.json"
out.write_text(json.dumps(rows, separators=(",", ":")), encoding="utf-8")
