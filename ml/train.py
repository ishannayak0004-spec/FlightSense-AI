"""Train and export FlightSense's offline airfare models from Clean_Dataset.csv."""
import argparse
import json
import os
from pathlib import Path

for variable in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[variable] = "2"

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import OneHotEncoder, StandardScaler

CAT = ["source_city", "destination_city", "airline", "class", "stops", "departure_time", "arrival_time"]
NUM = ["duration", "days_left"]


def split(frame, fraction, seed):
    train, test = next(GroupShuffleSplit(n_splits=1, test_size=fraction, random_state=seed)
                       .split(frame, groups=frame.flight))
    return frame.iloc[train], frame.iloc[test]


def emit(path, data):
    path.write_text(json.dumps(data, separators=(",", ":"), allow_nan=False))


def metrics(name, actual, pred):
    return dict(name=name, mae=float(mean_absolute_error(actual, pred)),
                rmse=float(np.sqrt(mean_squared_error(actual, pred))),
                r2=float(r2_score(actual, pred)), within10=float(np.mean(np.abs(actual - pred) <= .1 * actual)))


def trees_json(model):
    # Every numeric threshold operates on the same one-hot + scaled feature matrix.
    return dict(bias=float(model._baseline_prediction.item()), trees=[
        [[int(n["feature_idx"]), float(n["num_threshold"]), int(n["left"]), int(n["right"])]
         if not n["is_leaf"] else [float(n["value"])] for n in step[0].nodes]
        for step in model._predictors])


def main(csv, out):
    frame = pd.read_csv(csv).dropna(subset=CAT + NUM + ["price", "flight"])
    frame = frame.loc[(frame.price > 0) & (frame.duration > 0) & (frame.days_left >= 1)]
    # Partition whole flight numbers, so repeated observations cannot cross boundaries.
    development, test = split(frame, .16, 395)
    learn, calibration = split(development, .12, 396)
    train, validation = split(learn, .14, 397)
    groups = [set(x.flight) for x in [train, validation, calibration, test]]
    assert all(a.isdisjoint(b) for i, a in enumerate(groups) for b in groups[i+1:])
    prep = ColumnTransformer([("categories", OneHotEncoder(sparse_output=False, handle_unknown="ignore"), CAT),
                              ("numeric", StandardScaler(), NUM)])
    x = prep.fit_transform(train)
    xv, xc, xt = (prep.transform(d) for d in (validation, calibration, test))
    y = train.price.to_numpy()
    print("Partitions", [len(d) for d in [train, validation, calibration, test]], flush=True)
    ridge = Ridge(alpha=1.).fit(x, np.log(y))
    candidates = []
    for leaves in [31, 63]:
        model = HistGradientBoostingRegressor(max_iter=140, max_leaf_nodes=leaves, learning_rate=.12,
                                              min_samples_leaf=35, l2_regularization=1, early_stopping=False,
                                              random_state=395).fit(x, np.log(y))
        err = mean_absolute_error(validation.price, np.exp(model.predict(xv)))
        candidates.append((err, leaves, model))
        print("Boost validation", leaves, err, flush=True)
    _, leaves, boost = min(candidates, key=lambda v: v[0])
    sample = np.random.default_rng(395).choice(len(train), min(len(train), 90000), replace=False)
    neural = MLPRegressor(hidden_layer_sizes=(64, 32, 16), batch_size=512, max_iter=65,
                          learning_rate_init=.002, early_stopping=True, n_iter_no_change=6,
                          random_state=395).fit(x[sample], np.log(y[sample]))
    # Select a convex blend on validation only; calibration and test are untouched.
    bv, nv = np.exp(boost.predict(xv)), np.exp(neural.predict(xv))
    weights = np.linspace(0, 1, 21)
    w = float(min(weights, key=lambda a: mean_absolute_error(validation.price, a * bv + (1-a) * nv)))
    def blend(xx):
        return w * np.exp(boost.predict(xx)) + (1-w) * np.exp(neural.predict(xx))
    residual = np.abs(calibration.price - blend(xc))
    radii = {}
    for cabin in sorted(train["class"].unique()):
        scores = np.sort(residual[calibration["class"] == cabin])
        radii[cabin] = float(scores[min(len(scores)-1, int(np.ceil(.9 * (len(scores)+1)))-1)])
    estimates = blend(xt)
    results = [metrics("Ridge regression", test.price, np.exp(ridge.predict(xt))),
               metrics("Gradient boosting", test.price, np.exp(boost.predict(xt))),
               metrics("Deep neural network", test.price, np.exp(neural.predict(xt))),
               metrics("Validation-selected blend", test.price, estimates)]
    coverage = float(np.mean(np.abs(test.price-estimates) <= test["class"].map(radii)))
    # Joint combinations and support reflect observed flights in the learning data only.
    combos = train.groupby(CAT).agg(durationMin=("duration","min"), durationMax=("duration","max"),
                                    durationMedian=("duration","median"), daysMin=("days_left","min"),
                                    daysMax=("days_left","max")).reset_index()
    output = Path(out)
    output.mkdir(exist_ok=True, parents=True)
    rep = dict(rows=len(frame), trainRows=len(train), validationRows=len(validation), testRows=len(test),
               calibrationRows=len(calibration), flightGroups=[len(g) for g in groups], metrics=results,
               coverage=coverage, model="Validation-selected blend", features=CAT+NUM, boostWeight=w,
               radii=radii, tuning=[dict(leaves=l,validationMAE=e) for e,l,_ in candidates],
               neuralEpochs=neural.n_iter_, hiddenLayers=[64,32,16], seed=395)
    enc = prep.named_transformers_["categories"]
    scaler = prep.named_transformers_["numeric"]
    artifact = dict(categories=[v.tolist() for v in enc.categories_], mean=scaler.mean_.tolist(),
                    scale=scaler.scale_.tolist(), boost=trees_json(boost), weight=w, radii=radii,
                    neural=dict(weights=[v.tolist() for v in neural.coefs_], biases=[v.tolist() for v in neural.intercepts_]))
    emit(output/"model.json", artifact)
    emit(output/"options.json", combos.to_dict("records"))
    emit(output/"report.json", rep)
    fixture = combos.sample(8,random_state=17).to_dict("records")
    for f in fixture:
        f["duration"] = f["durationMedian"]
        f["days_left"] = (f["daysMin"] + f["daysMax"]) // 2
    expected = blend(prep.transform(pd.DataFrame(fixture)))
    emit(Path(__file__).parent/"parity.json", [dict(record=f,price=float(p)) for f,p in zip(fixture,expected)])
    print(json.dumps(rep, indent=2), flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("csv")
    parser.add_argument("--out", default="dist")
    args = parser.parse_args()
    main(args.csv, args.out)
