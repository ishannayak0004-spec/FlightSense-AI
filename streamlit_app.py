"""Serve the complete FlightSense website through Streamlit Community Cloud."""
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import hashlib
import shutil
import tempfile

import streamlit as st
from streamlit.components.v1 import declare_component

st.set_page_config(page_title="FlightSense AI", page_icon="✈️", layout="wide")


ASSETS = Path(__file__).resolve().parent / "dist"


def asset_revision():
    digest = hashlib.sha256()
    for asset in sorted(ASSETS.rglob("*")):
        if asset.is_file():
            digest.update(asset.relative_to(ASSETS).as_posix().encode() + b"\0")
            digest.update(hashlib.sha256(asset.read_bytes()).digest())
    return digest.hexdigest()[:16]


@st.cache_resource
def component_assets(revision):
    # Keep local edits in dist intact. The frame handshake is specific to Streamlit.
    folder = tempfile.TemporaryDirectory(prefix="flightsense-")
    target = Path(folder.name)
    shutil.copytree(ASSETS, target, dirs_exist_ok=True)
    index = target / "index.html"
    bridge = """
<script>
  const send = (type, fields) => parent.postMessage(
    {isStreamlitMessage: true, type: "streamlit:" + type, ...fields}, "*");
  const resize = () => send("setFrameHeight", {
    height: Math.ceil(document.body.getBoundingClientRect().height) + 8
  });
  addEventListener("message", event => {
    if (event.source === parent && event.data?.type === "streamlit:render") resize();
  });
  new ResizeObserver(resize).observe(document.body);
  send("componentReady", {apiVersion: 1});
  resize();
</script>
"""
    index.write_text(index.read_text(encoding="utf-8").replace("</body>", bridge + "</body>"), encoding="utf-8")
    return folder


@lru_cache(maxsize=1)
def airports():
    with (ASSETS / "global" / "airports.json").open(encoding="utf-8") as f:
        return {r[0]: f"{r[0]} · {r[2] or r[1]} · {r[1]} ({r[3]})" for r in json.load(f)}


def get_json(request):
    with urlopen(request, timeout=25) as response:
        return json.load(response)


def flight_search(key, params):
    query = dict(params, engine="google_flights", currency="INR", hl="en", gl="in",
                 no_cache="true", api_key=key)
    try:
        payload = get_json(Request("https://serpapi.com/search.json?" + urlencode(query)))
    except HTTPError as exc:
        messages = {401: "Check your SerpApi key in Streamlit Secrets.",
                    403: "The provider denied access. Check your SerpApi account.",
                    429: "Search quota or rate limit reached. Check your SerpApi dashboard."}
        st.error(messages.get(exc.code, "The provider could not complete this search."))
        return None
    except (URLError, TimeoutError, ValueError):
        st.error("Could not reach the fare provider. Try again.")
        return None
    if payload.get("error"):
        st.warning("The provider could not return offers for these search details.")
        return None
    return sorted((offer for field in ("best_flights","other_flights")
                   for offer in payload.get(field, []) if offer.get("flights")),
                  key=lambda offer: offer.get("price") if isinstance(offer.get("price"), (float,int)) else float("inf"))


def display_offers(offers, key, params, returning=False):
    if not offers:
        st.info("No fares found for this search.")
    for index, offer in enumerate(offers):
        legs = offer["flights"]
        with st.container(border=True):
            a, b, c = st.columns([1,5,3])
            logo = offer.get("airline_logo") or legs[0].get("airline_logo")
            if logo and logo.startswith("https://"):
                a.image(logo, width=48)
            b.write(" · ".join(dict.fromkeys(leg.get("airline","Airline") for leg in legs)))
            price = offer.get("price")
            c.write(f"₹{price:,.0f}" if isinstance(price,(int,float)) else "Price unavailable")
            start, end = legs[0]["departure_airport"], legs[-1]["arrival_airport"]
            st.write(f"{start['id']} {start['time']} → {end['id']} {end['time']}")
            minutes = offer.get("total_duration")
            length = f" · {minutes//60}h {minutes%60}m" if isinstance(minutes,int) else ""
            st.caption(("Nonstop" if len(legs)==1 else f"{len(legs)-1} stop(s)") + length + " · Airport local times")
            with st.expander("Flight details"):
                for leg in legs:
                    st.write(f"{leg['departure_airport']['id']} → {leg['arrival_airport']['id']} · {leg.get('flight_number','')}")
            token = offer.get("departure_token")
            if not returning and params["type"] == 1 and token and st.button("See return flights", key=f"return_{index}"):
                st.session_state.pop("return_options",None)
                with st.spinner("Checking return flights…"):
                    choices = flight_search(key, dict(params, departure_token=token))
                if choices is not None:
                    st.session_state.return_options = (f"{start['id']} → {end['id']} · {start['time']} · {legs[0].get('flight_number','')}", choices)


def live_search():
    st.title("Search flight prices")
    st.write("Compare domestic and international fares in rupees.")
    try:
        key = st.secrets.get("serpapi", {}).get("api_key","")
    except FileNotFoundError:
        key = ""
    ready = bool(key)
    if not ready:
        st.info("Add your SerpApi API key in Streamlit Secrets to enable flight search.")
    catalog = airports()
    codes = list(catalog)
    trip = st.radio("Trip type", ["One way","Round trip"], horizontal=True)
    today = date.today()
    with st.form("flight_search"):
        a,b = st.columns(2)
        origin = a.selectbox("From", codes, index=codes.index("DEL"), format_func=catalog.get)
        destination = b.selectbox("To", codes, index=codes.index("LHR"), format_func=catalog.get)
        a,b = st.columns(2)
        depart = a.date_input("Departure", today+timedelta(days=14), min_value=today)
        back = b.date_input("Return", today+timedelta(days=21), min_value=today) if trip == "Round trip" else None
        a,b = st.columns(2)
        adults = a.number_input("Adults",1,9,1)
        cabin = b.selectbox("Cabin", ["Economy","Premium economy","Business","First"])
        nonstop = st.checkbox("Nonstop only")
        submitted = st.form_submit_button("Search flights",type="primary",disabled=not ready)
    if submitted:
        st.session_state.pop("serp_offers",None)
        st.session_state.pop("return_options",None)
        if origin == destination or (back and back < depart):
            st.error("Choose different airports and a return date on or after departure.")
            return
        params = dict(departure_id=origin, arrival_id=destination, type=1 if back else 2,
                      outbound_date=depart.isoformat(), adults=adults, stops=1 if nonstop else 0,
                      travel_class=["Economy","Premium economy","Business","First"].index(cabin)+1)
        if back:
            params["return_date"] = back.isoformat()
        with st.spinner("Searching Google Flights via SerpApi…"):
            offers = flight_search(key, params)
        if offers is not None:
            st.session_state.serp_offers = (params,offers,datetime.now(timezone.utc).strftime("%H:%M UTC"))
    if ready and "serp_offers" in st.session_state:
        params,offers,checked = st.session_state.serp_offers
        st.subheader(f"{params['departure_id']} → {params['arrival_id']}")
        dates = params["outbound_date"] + (" – " + params["return_date"] if "return_date" in params else "")
        st.caption(f"{dates} · {params['adults']} adult(s) · Checked {checked} · Google Flights via SerpApi")
        display_offers(offers,key,params)
        if "return_options" in st.session_state:
            selected, choices = st.session_state.return_options
            st.subheader("Return flights")
            st.caption("Selected outbound: " + selected)
            display_offers(choices,key,params,returning=True)


section = st.radio("Explore FlightSense", ["Fare predictions", "Live flight prices"], horizontal=True)
if section == "Live flight prices":
    live_search()
else:
    revision = asset_revision()
    website = declare_component(f"flightsense_{revision}", path=component_assets(revision).name)
    website(key="flightsense-website", default=None)
