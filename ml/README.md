# Reproduce the predictor

Use Python 3.11 or newer. From the project root, install the pinned training packages and download the historical Clean_Dataset.csv from [Shubham Bathwal's Flight Price Prediction dataset](https://www.kaggle.com/datasets/shubhambathwal/flight-price-prediction). The input file used for this run had SHA-256 `c27377aa4451d4427794523f3292dd2c2dc312f29c6d880aef4df1dcf1aaf7a3`.

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r ml/requirements.txt
python ml/train.py /path/to/Clean_Dataset.csv
```

Training partitions by flight number before fitting categorical encodings, scaling or estimating model parameters. Training, validation, calibration and test sets are disjoint. Candidates learn log INR fares. The tuning split chooses the boosting tree size and the blend fraction by rupee MAE. The MLP trains on 90,000 sampled training rows with three ReLU hidden layers and early stopping. A separate calibration split supplies cabin-specific 90th percentile absolute errors for displaying approximate prediction intervals. Test coverage is measured on the final blend. Repeated quotes within a flight are correlated, and future markets can shift.

The data span six Indian cities in 2022. Flight number is a partition key only. The source lacks scrape dates for individual rows, so the evaluation tests generalization across historical flights. Each interface itinerary has observed training support. Its observed duration and advance-purchase bounds are marginal ranges and intermediate combinations may be interpolations.

Generated files are dist/model.json (parameters), dist/options.json (supported itinerary combinations), dist/report.json (evaluation) and ml/parity.json (prediction fixtures from scikit-learn). The static web engine and the Python companion both consume the same JSON weights. Browser inference runs on the user's device after its initial asset load.
