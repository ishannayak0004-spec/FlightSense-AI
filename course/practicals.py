"""Reproduce the INT395 experiments from the original Kaggle archive."""
import argparse
import json
from pathlib import Path
from zipfile import ZipFile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score, mean_absolute_error,
                             precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.statespace.sarimax import SARIMAX

CATEGORICAL = ["source_city", "destination_city", "airline", "arrival_time", "departure_time", "stops"]
NUMERIC = ["duration", "days_left"]


def evaluate_classification(fares):
    """Estimate the chance an economy fare exceeds a fixed training-set threshold."""
    df = fares.loc[fares["class"].eq("Economy")].drop_duplicates().reset_index(drop=True)
    splitter = GroupShuffleSplit(n_splits=1, test_size=.2, random_state=395)
    train_idx, test_idx = next(splitter.split(df, groups=df["flight"]))
    train, test = df.iloc[train_idx], df.iloc[test_idx]
    threshold = float(train.price.quantile(.75))
    y_train, y_test = train.price.gt(threshold), test.price.gt(threshold)
    prep = ColumnTransformer([
        ("category", make_pipeline(SimpleImputer(strategy="most_frequent"),
                                   OneHotEncoder(handle_unknown="ignore")), CATEGORICAL),
        ("numeric", make_pipeline(SimpleImputer(strategy="median"), StandardScaler()), NUMERIC),
    ])
    clf = make_pipeline(prep, LogisticRegression(class_weight="balanced", max_iter=800, random_state=395))
    clf.fit(train, y_train)
    pred = clf.predict(test)
    evaluation = test.sample(min(4000, len(test)), random_state=395)
    feature_names = CATEGORICAL + NUMERIC
    importance = permutation_importance(clf, evaluation[feature_names], evaluation.price.gt(threshold),
                                        n_repeats=3, scoring="roc_auc", random_state=395)
    return {
        "permutation_auc_drop": dict(zip(feature_names, importance.importances_mean)),
        "threshold_inr": threshold,
        "train_quotes": len(train), "test_quotes": len(test),
        "positive_fraction_test": y_test.mean(),
        "always_standard_accuracy": (~y_test).mean(),
        "accuracy": accuracy_score(y_test, pred), "precision": precision_score(y_test, pred),
        "recall": recall_score(y_test, pred), "f1": f1_score(y_test, pred),
        "roc_auc": roc_auc_score(y_test, clf.predict_proba(test)[:, 1]),
        "confusion_matrix": confusion_matrix(y_test, pred, labels=[False, True]).tolist(),
    }


def evaluate_series(raw, output_dir):
    """Use departure dates, because the source has no repeated quote timestamps."""
    raw = raw.copy()
    raw["date"] = pd.to_datetime(raw.date, format="%d-%m-%Y", errors="raise")
    raw["price"] = pd.to_numeric(raw.price.astype(str).str.replace(",", "", regex=False), errors="raise")
    daily = raw.groupby("date").price.median().sort_index().asfreq("D")
    if daily.isna().any() or len(daily) < 35:
        raise ValueError("The experiment requires a continuous series of at least 35 daily medians.")
    train, test = daily.iloc[:-7], daily.iloc[-7:]
    series = pd.DataFrame({"observed": test, "last_value": train.iloc[-1],
                           "weekly_repeat": train.iloc[-7:].to_numpy()})
    series["arima"] = ARIMA(train, order=(1, 1, 0)).fit().forecast(len(test))
    series["sarima"] = SARIMAX(train, order=(1, 1, 0), seasonal_order=(1, 0, 0, 7),
                               enforce_stationarity=True).fit(disp=False).forecast(len(test))
    series.round(2).to_csv(output_dir / "departure_forecast.csv")
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(train.index, train.to_numpy(), color="#183153", label="Training observations")
    for col in ["observed", "weekly_repeat", "arima", "sarima"]:
        ax.plot(series.index, series[col], label=col.replace("_", " ").title(), marker=".")
    ax.set(xlabel="Departure date, 2022", ylabel="Daily median economy fare (INR)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(output_dir / "departure_forecast.png", dpi=160)
    plt.close(fig)
    return {"train_days": len(train), "test_days": len(test), "first": str(daily.index.min().date()),
            "last": str(daily.index.max().date()), "mae_inr": {
                col: mean_absolute_error(test, series[col]) for col in series if col != "observed"
            }}


def explore(fares, output_dir):
    summary = fares.groupby(["source_city", "destination_city", "class"]).price.agg(
        quotes="size", median_inr="median", minimum_inr="min", maximum_inr="max")
    summary.to_csv(output_dir / "route_summary.csv")
    profile = fares.groupby(["days_left", "class"], as_index=False).price.median()
    fig, ax = plt.subplots(figsize=(8, 4))
    sns.lineplot(data=profile, x="days_left", y="price", hue="class", ax=ax)
    ax.set(xlabel="Days before departure", ylabel="Median quoted fare (INR)")
    fig.tight_layout()
    fig.savefig(output_dir / "lead_time_profile.png", dpi=160)
    plt.close(fig)
    return {"raw_rows": len(fares), "duplicate_observations": int(fares.duplicated().sum()),
            "missing": fares.isna().sum().to_dict(), "routes": int(len(summary.index.droplevel("class").unique()))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="Original ZIP containing Clean_Dataset.csv and economy.csv")
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "results")
    args = parser.parse_args()
    args.out.mkdir(exist_ok=True, parents=True)
    with ZipFile(args.archive) as archive:
        fares = pd.read_csv(archive.open("Clean_Dataset.csv"), usecols=lambda c: not c.startswith("Unnamed"))
        raw = pd.read_csv(archive.open("economy.csv"), usecols=["date", "price"])
    results = {"exploration": explore(fares, args.out), "classification": evaluate_classification(fares),
               "departure_date_series": evaluate_series(raw, args.out)}
    content = json.dumps(results, indent=2, allow_nan=False)
    (args.out / "practicals.json").write_text(content + "\n")
    print(content)


if __name__ == "__main__":
    main()
