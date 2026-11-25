"""Inference using the same portable weights as the browser."""
import json
import math
from pathlib import Path

import numpy as np

FIELDS = ["source_city", "destination_city", "airline", "class", "stops", "departure_time", "arrival_time"]


class FareModel:
    def __init__(self, root="dist"):
        root = Path(root)
        self.model, self.options, self.report = [
            json.loads((root / (name + ".json")).read_text()) for name in ("model", "options", "report")]
        self.support = {tuple(row[k] for k in FIELDS): row for row in self.options}

    def predict(self, record):
        key = tuple(record[k] for k in FIELDS)
        option = self.support.get(key)
        if option is None:
            raise ValueError("Choose an observed itinerary.")
        d, days = record["duration"], record["days_left"]
        if not (option["durationMin"] <= d <= option["durationMax"] and
                option["daysMin"] <= days <= option["daysMax"] and float(days).is_integer()):
            raise ValueError("Duration or lead time outside observed itinerary range.")
        m = self.model
        x = [float(cat == value) for value, cats in zip(key, m["categories"]) for cat in cats]
        x.extend((v - mu) / sigma for v, mu, sigma in zip([d, days], m["mean"], m["scale"]))
        log_price = m["boost"]["bias"]
        for tree in m["boost"]["trees"]:
            node = tree[0]
            while len(node) > 1:
                node = tree[node[2] if x[node[0]] <= node[1] else node[3]]
            log_price += node[0]
        layer = np.array(x)
        for i, (weight, bias) in enumerate(zip(m["neural"]["weights"], m["neural"]["biases"])):
            layer = layer @ weight + bias
            if i + 1 < len(m["neural"]["weights"]):
                layer = np.maximum(0, layer)
        price = m["weight"] * math.exp(log_price) + (1 - m["weight"]) * math.exp(layer.item())
        radius = m["radii"][record["class"]]
        return {"price": price, "low": max(0., price - radius), "high": price + radius}
