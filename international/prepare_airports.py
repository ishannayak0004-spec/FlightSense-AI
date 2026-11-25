"""Build the world airport picker from the OurAirports public-domain airports.csv."""
import csv
import json
from pathlib import Path
import sys

types = {"small_airport", "medium_airport", "large_airport", "seaplane_base", "heliport"}
records = {}
with open(sys.argv[1], encoding="utf8") as stream:
    for row in csv.DictReader(stream):
        code = row["iata_code"]
        if len(code) != 3 or not code.isalpha() or row["type"] not in types:
            continue
        priority = (row["scheduled_service"] == "yes", row["type"] == "large_airport", row["type"] == "medium_airport")
        if code not in records or priority > records[code][0]:
            records[code] = (priority, [code, row["name"], row["municipality"], row["iso_country"], row["continent"],
                                        round(float(row["latitude_deg"]), 5), round(float(row["longitude_deg"]), 5),
                                        row["scheduled_service"] == "yes"])
out = Path(__file__).resolve().parents[1] / "dist/global/airports.json"
out.write_text(json.dumps([records[k][1] for k in sorted(records)], ensure_ascii=False, separators=(",", ":")))
print(len(records), "unique IATA codes")
