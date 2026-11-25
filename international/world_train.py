"""Fit a transferable international economy base-fare model from original ANAC sales."""
from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd
from sklearn.linear_model import HuberRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GroupKFold

def fit_world(data_dir, airports_file, output):
    airports = pd.read_csv(airports_file, keep_default_na=False, low_memory=False)
    lut = {}
    for airport in airports.itertuples():
        if airport.type != "closed" and len(airport.iata_code) == 3:
            for code in (airport.ident, airport.icao_code):
                if code:
                    lut[code] = airport
    files = sorted(data_dir.glob("2024-*.csv"))
    if len(files) != 12:
        raise ValueError("Expected twelve 2024 monthly ANAC CSVs")
    df = pd.concat([pd.read_csv(f, sep=";", dtype=str, keep_default_na=False) for f in files])
    df = df[(df.RETORNO == "9999") & (df["CLASSE IDA"] == "Y")].copy()
    df["fare"] = pd.to_numeric(df.TARIFA.str.replace(",", ".", regex=False), errors="coerce")
    df["seats"] = pd.to_numeric(df.ASSENTOS, errors="coerce")
    df = df[df.ORIGEM.isin(lut) & df.DESTINO.isin(lut) & (df.seats > 0) & (df.fare > 0)].copy()
    df["dep"] = df.ORIGEM.map(lambda x: lut[x].iata_code)
    df["arr"] = df.DESTINO.map(lambda x: lut[x].iata_code)
    by_iata = {a.iata_code:a for a in lut.values()}
    df = df[df.dep.map(lambda x:by_iata[x].iso_country) != df.arr.map(lambda x:by_iata[x].iso_country)]
    def stats(g):
        ordered = g.sort_values("fare")
        seats = ordered.seats.cumsum().values
        def quantile(q):
            return round(float(ordered.fare.iloc[np.searchsorted(seats, seats[-1]*q)]),2)
        return [quantile(.5),int(seats[-1])]
    def features(a,b):
        lat1,lat2,lon1,lon2=np.radians([a.latitude_deg,b.latitude_deg,a.longitude_deg,b.longitude_deg])
        h=np.sin((lat2-lat1)/2)**2+np.cos(lat1)*np.cos(lat2)*np.sin((lon2-lon1)/2)**2
        km=12742*np.arcsin(np.sqrt(np.clip(h,0,1)))
        return km,[np.log(max(1,km)), float(a.continent!=b.continent)]
    known, carrier, records = {},{},[]
    for (dep,arr),g in df.groupby(["dep","arr"]):
        key=f"{dep}-{arr}"
        known[key]=stats(g)
        carrier[key]={c:stats(cg) for c,cg in g.groupby("EMPRESA")}
        if known[key][1]>=5:
            km,x=features(by_iata[dep],by_iata[arr])
            records.append((key,"-".join(sorted([dep,arr])),km,x,known[key][0]))
    X=np.array([r[3] for r in records]); y=np.array([r[4] for r in records]); groups=[r[1] for r in records]
    estimates=np.empty(len(y)); baselines=np.empty(len(y))
    def train(index):
        return HuberRegressor(max_iter=500).fit(X[index], np.log(y[index]))
    for train_idx,test_idx in GroupKFold(5,shuffle=True,random_state=395).split(X,y,groups):
        estimates[test_idx]=np.exp(train(train_idx).predict(X[test_idx]))
        baselines[test_idx]=np.median(y[train_idx])
    model=train(np.arange(len(y)));distances=[r[2] for r in records]
    result=dict(fit=dict(intercept=model.intercept_,weights=model.coef_.tolist()),currency="USD",
                minKm=min(distances),maxKm=max(distances),known=known,carriers=carrier,
                seats=int(df.seats.sum()),salesRows=len(df),routes=len(known),trainingRoutes=len(records),
                groups=len(set(groups)),mae=mean_absolute_error(y,estimates),baselineMae=mean_absolute_error(y,baselines),
                medianAPE=float(np.median(abs(estimates-y)/y)),within20=float(np.mean(abs(estimates-y)<=.2*y)))
    output.write_text(json.dumps(result,separators=(",",":"),allow_nan=False))
    print({k:v for k,v in result.items() if k not in ("known","carriers")})
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("anac_folder",type=Path);p.add_argument("airports_csv",type=Path)
    args=p.parse_args()
    fit_world(args.anac_folder,args.airports_csv,Path(__file__).resolve().parents[1]/"dist/global/world-model.json")
