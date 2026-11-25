# FlightSense AI
An airfare prediction project for INT395 Supervised Learning. The included model runs locally in a browser. The worldwide estimator uses original 2024 international sales records. The India model uses domestic listings from February–March 2022.

## Open the website on macOS
Extract the project, open Terminal in its folder, and run:
```sh
python3 -m http.server 8000 --bind 127.0.0.1 --directory dist
```
Open http://localhost:8000. The Worldwide tab accepts two airports in different countries. Try GRU to JFK for a recorded route and DEL to LHR for an extrapolation. Open the India model tab and choose a route, cabin, airline, stops and booking lead time, then select **Estimate airfare**. The workspace plots how predictions change with lead time. Model lab shows held-out scores. Dataset explorer shows route coverage.

## Run the course practicals
See [the course guide](course/README.md) for the Streamlit app, mapping to all six units and practical results. See [training instructions](ml/README.md) to reproduce the model and performance comparison. The distribution archive includes the original Kaggle dataset at data/airfares.zip. Extract its Clean_Dataset.csv to retrain, or pass the ZIP directly to course/practicals.py.

## Dataset credit
Shubham Bathwal, Flight Price Prediction, Kaggle (CC0). Historical EaseMyTrip listings.
https://www.kaggle.com/datasets/shubhambathwal/flight-price-prediction


## Worldwide model
The estimator predicts the historical seat-weighted median USD base fare for a one-way economy route. It uses Huber regression on log fare, log great-circle distance and a cross-continent indicator. The training target comes exclusively from actual Brazilian ANAC international sales in 2024. Taxes, booking date, connections and current availability are outside this model.

After matching airports and filtering positive fares, sold seats and eligible itineraries, the data contains 178,882 price records with 829,245 sold seats on 1,712 directed routes. All originate in Brazil. Each of the 1,292 routes with at least five seats receives equal weight in the fit. Five-fold validation groups both directions of each airport pair together. Withheld route-median MAE was USD 103.16, compared with USD 218.55 for the training-fold median. Median absolute percentage error was 17.0%. Validation measures transfer between Brazil-origin routes. It does not establish the error in a new origin market.

The displayed estimate uses geography for worldwide comparability. An exact route match adds an empirical fare and seat count. If the optional carrier matches a recorded airline, its observed median is displayed separately. The airline directory includes historic operators. A listed airport pair or carrier does not establish flight availability.

### Rebuild the worldwide model
The project ZIP includes the original twelve ANAC monthly CSV files and the OurAirports geographic snapshot used in this run. From the extracted project directory:
```sh
python -m pip install -r ml/requirements.txt
python international/world_train.py data/anac-2024 data/airports.csv
python international/prepare_airports.py data/airports.csv
```
The original ANAC files are downloadable from https://sas.anac.gov.br/sas/tarifainternacional/2024/. OurAirports provides public-domain airport data at https://ourairports.com/data/. The transformed OpenFlights directory is licensed under ODbL 1.0 and its individual contents under the Database Contents License, https://openflights.org/data.php.

### International fare explorer
Southern African historical economy listings and European fares to Thessaloniki are displayed in their original currencies, independently from ANAC model training. See international/southern-africa.md. The Greece summaries use the 188 rows in the public file at https://github.com/NMyrsini/Flight-Dataset, credited to Myrsini Ntemi and Constantine Kotropoulos, *A dynamic dyadic particle filter for price prediction*, Signal Processing 167 (2020). Download All_flights.txt from the repository and run `python international/prepare_greece.py All_flights.txt` to reproduce.

The local website includes INR conversion and dated nonstop-route lookup. Internet access is used to refresh exchange rates. The India model currently covers six cities and 30 directional routes. Delhi to Patna is outside that training set.
