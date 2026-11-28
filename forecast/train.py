"""Train a next-day fare change regressor on observed, matched Expedia quotes."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error

ROUTES = ("ATL-BOS", "BOS-ATL", "LAX-JFK", "JFK-LAX")
KEY = ["flightDate","route","legId","fareBasisCode","segmentsCabinCode","isBasicEconomy",
       "isRefundable","segmentsDepartureTimeEpochSeconds","segmentsArrivalTimeEpochSeconds",
       "segmentsAirlineCode"]
FEATURES = ["totalFare","daysAhead","weekday","seatsRemaining"]


def load_quotes(path):
    columns = [k for k in KEY if k != "route"] + ["startingAirport","destinationAirport",
              "searchDate","totalFare","seatsRemaining","isNonStop"]
    selected = []
    count = 0
    for block in pd.read_csv(path, usecols=columns, chunksize=150000):
        count += len(block)
        block["route"] = block.startingAirport + "-" + block.destinationAirport
        selected.append(block[block.route.isin(ROUTES) & block.isNonStop & (block.totalFare > 0)])
    frame = pd.concat(selected).dropna(subset=KEY + FEATURES[:1] + ["seatsRemaining"])
    for col in ("searchDate","flightDate"):
        frame[col] = pd.to_datetime(frame[col])
    # Keep the lowest quote per product and day, with a deterministic seats tie-break.
    frame = frame.sort_values(["totalFare","seatsRemaining"]).drop_duplicates(KEY + ["searchDate"])
    return frame, count


def train(path, output):
    quotes, count = load_quotes(path)
    future = quotes[KEY + ["searchDate","totalFare"]].copy()
    future["searchDate"] -= pd.Timedelta(days=1)
    future.rename(columns={"totalFare":"tomorrow"}, inplace=True)
    pairs = quotes.merge(future, on=KEY + ["searchDate"], validate="one_to_one")
    pairs["daysAhead"] = (pairs.flightDate - pairs.searchDate).dt.days
    pairs = pairs[pairs.daysAhead > 1].copy()
    pairs["weekday"] = pairs.flightDate.dt.dayofweek
    dates = sorted(pairs.searchDate.unique())
    flights = sorted(pairs.flightDate.unique())
    if len(dates) < 4 or len(flights) < 4:
        raise ValueError("More consecutive observation and departure dates are required.")
    split = pd.Timestamp(dates[int(.65*len(dates))])
    depart_split = pd.Timestamp(flights[int(.7*len(flights))])
    train = pairs[(pairs.searchDate + pd.Timedelta(days=1) < split) & (pairs.flightDate < depart_split)]
    test = pairs[(pairs.searchDate >= split) & (pairs.flightDate >= depart_split)].copy()
    if min(len(train),len(test)) < 100:
        raise ValueError("Too few observations in the nonoverlapping chronological split.")
    model = GradientBoostingRegressor(loss="absolute_error", n_estimators=40, max_depth=2,
                                      learning_rate=.08,min_samples_leaf=25,random_state=37)
    model.fit(train[FEATURES],train.tomorrow-train.totalFare)
    test["prediction"] = np.maximum(0, test.totalFare + model.predict(test[FEATURES]))
    def metrics(x):
        return dict(pairs=len(x), modelMAE=round(mean_absolute_error(x.tomorrow,x.prediction),3),
                    baselineMAE=round(mean_absolute_error(x.tomorrow,x.totalFare),3))
    def span(x,col):
        return [str(x[col].min().date()),str(x[col].max().date())]
    report = dict(sourceRows=count, eligibleQuotes=len(quotes), consecutivePairs=len(pairs),
                  trainPairs=len(train), trainSearch=span(train,"searchDate"),testSearch=span(test,"searchDate"),
                  trainDepartures=span(train,"flightDate"),testDepartures=span(test,"flightDate"),
                  test=metrics(test), routes={r:metrics(g) for r,g in test.groupby("route")})
    trees = []
    for est in model.estimators_[:,0]:
        t = est.tree_
        trees.append([[int(t.feature[i]),float(t.threshold[i]),int(t.children_left[i]),int(t.children_right[i])]
                      if t.children_left[i]>=0 else [float(t.value[i,0,0])] for i in range(t.node_count)])
    output.mkdir(parents=True,exist_ok=True)
    (output/"model.json").write_text(json.dumps(dict(features=FEATURES,initial=float(model.init_.constant_[0,0]),
                         rate=model.learning_rate,trees=trees),separators=(",",":")))
    # Select by chronology, independently of forecast error.
    examples = []
    for r,g in test.groupby("route"):
        row = g.sort_values(["searchDate","flightDate","legId"]).iloc[0]
        examples.append(dict(route=r,search=str(row.searchDate.date()),departure=str(row.flightDate.date()),
                             features=[float(row[k]) for k in FEATURES],actual=float(row.tomorrow),
                             predicted=round(row.prediction,4)))
    (output/"evaluation.json").write_text(json.dumps(dict(**report,examples=examples),indent=2))
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("csv",type=Path)
    parser.add_argument("--output",type=Path,default=Path("dist/forecast"))
    args=parser.parse_args()
    train(args.csv,args.output)
