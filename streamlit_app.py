"""Serve the complete FlightSense website through Streamlit Community Cloud."""
from datetime import date, datetime, timezone
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
    if (event.source !== parent || event.data?.type !== "streamlit:render") return;
    if (!window.flightState && event.data.args.openLive) location.hash = "live";
    window.flightState = event.data.args;
    window.dispatchEvent(new Event("fare-render"));
    resize();
  });
  window.sendFareRequest = value => send("setComponentValue", {dataType:"json",value});
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
        raise ValueError(messages.get(exc.code, "The provider could not complete this search.")) from None
    except (URLError, TimeoutError, ValueError):
        raise ValueError("Could not reach the fare provider. Try again.") from None
    if payload.get("error"):
        raise ValueError("The provider could not return offers for these search details.")
    return sorted((offer for field in ("best_flights","other_flights")
                   for offer in payload.get(field, []) if offer.get("flights")),
                  key=lambda offer: offer.get("price") if isinstance(offer.get("price"), (float,int)) else float("inf"))


def search_params(request):
    origin, dest = request["origin"], request["dest"]
    if origin == dest or origin not in airports() or dest not in airports():
        raise ValueError("Choose two different airports from the directory.")
    depart = date.fromisoformat(request["depart"])
    back = date.fromisoformat(request["back"]) if request.get("back") else None
    if depart < date.today() or (back and back < depart):
        raise ValueError("Check your departure and return dates.")
    adults, cabin = int(request["adults"]), int(request["cabin"])
    if not 1 <= adults <= 9 or not 1 <= cabin <= 4:
        raise ValueError("Choose a valid passenger count and cabin.")
    params = dict(departure_id=origin, arrival_id=dest, outbound_date=depart.isoformat(),
                  type=1 if back else 2, adults=adults, travel_class=cabin,
                  stops=1 if request.get("nonstop") is True else 0)
    if back:
        params["return_date"] = back.isoformat()
    return params


def handle(request, key, state):
    result = dict(id=request["id"])
    try:
        if not key:
            raise ValueError("Add your SerpApi key in Streamlit Secrets.")
        if request.get("action") == "return":
            previous = state["outbound"]
            index = int(request["index"])
            if request["searchId"] != previous["id"] or not 0 <= index < len(previous["offers"]):
                raise ValueError("Run the outbound search again.")
            params = dict(previous["params"], departure_token=previous["offers"][index]["departure_token"])
        else:
            state.pop("outbound", None)
            params = search_params(request)
        offers = flight_search(key, params)
        result.update(offers=offers, checked=datetime.now(timezone.utc).strftime("%H:%M UTC"))
        if request.get("action") != "return":
            state["outbound"] = dict(id=request["id"], params=params, offers=offers)
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        result["error"] = str(exc) if isinstance(exc, ValueError) else "Run a new flight search."
    return result


try:
    api_key = st.secrets.get("serpapi", {}).get("api_key", "")
except FileNotFoundError:
    api_key = ""
revision = asset_revision()
website = declare_component(f"flightsense_{revision}", path=component_assets(revision).name)
reply = st.session_state.get("fare_reply", {})
request = website(openLive=st.query_params.get("view") == "live", ready=bool(api_key), reply=reply, key="flightsense-website", default=None)
if isinstance(request, dict) and isinstance(request.get("id"), str) and request["id"] != reply.get("id"):
    st.session_state.fare_reply = handle(request, api_key, st.session_state)
    st.rerun()
