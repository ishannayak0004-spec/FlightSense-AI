"""Serve the complete FlightSense website through Streamlit Community Cloud."""
from pathlib import Path
import shutil
import tempfile

import streamlit as st
from streamlit.components.v1 import declare_component

st.set_page_config(page_title="FlightSense AI", page_icon="✈️", layout="wide")


@st.cache_resource
def component_assets():
    # Keep local edits in dist intact. The frame handshake is specific to Streamlit.
    folder = tempfile.TemporaryDirectory(prefix="flightsense-")
    target = Path(folder.name)
    shutil.copytree(Path(__file__).resolve().parent / "dist", target, dirs_exist_ok=True)
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


website = declare_component("flightsense", path=component_assets().name)
website(key="flightsense-website", default=None)
