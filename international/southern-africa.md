# Southern Africa historical economy fares

Mazano collected these economy flight listings on March 14, 2025. Their departure dates cover March 15 through April 13, 2025. Prices use South African rand (ZAR). Each source row contains a directional flight, its carrier, a departure and arrival timestamp and one price. The source does not specify tax or baggage inclusion, a return-ticket rule, or the booking channel. Describe these values as observed economy listings for the chosen direction and carrier. Each price group stays within this source, currency and cabin.

Source: Mazano, *Southern Africa Flight Prices*, Kaggle version 1, published March 16, 2025. The publisher lists the MIT license. [Dataset and download](https://www.kaggle.com/datasets/mazano/southern-africa-flight-prices)

## Rebuild

From the project root, run with Python 3.9 or later:

```sh
curl --fail --location 'https://www.kaggle.com/api/v1/datasets/download/mazano/southern-africa-flight-prices' --output southern-africa.zip
python3 international/build_africa.py southern-africa.zip
```

The script verifies the CSV checksum, filters to cross-border journeys, and collapses exact repetitions of origin, destination, airline, departure time, arrival time, and price. It groups prices by directional city pair, origin-local departure month, and airline. Each group records its minimum, median, maximum and number of distinct listing observations. Low sample counts and the single collection date limit what these statistics can tell us about typical prices.

The original CSV has 15,393 rows. Across all routes, 8,161 remain after removing exact repetitions. The explorer uses 2,888 cross-border observations, spanning 37 directional routes, 9 airports, 6 countries and 16 carriers. It publishes 165 route-month-carrier groups. Among those groups, 28 contain fewer than five observations.
