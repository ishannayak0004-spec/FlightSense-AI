import {loadJSON} from './loading.js';
const categoricalFields = ["source_city", "destination_city", "airline", "class", "stops", "departure_time", "arrival_time"];
const keyFor = record => JSON.stringify(categoricalFields.map(field => record[field]));

function treePrediction(tree, x) {
  let node = tree[0];
  while (node.length > 1) {
    node = tree[x[node[0]] <= node[1] ? node[2] : node[3]];
  }
  return node[0];
}

function neuralPrediction(network, x) {
  let layer = x;
  for (let n = 0; n < network.weights.length; n++) {
    const weights = network.weights[n];
    const output = network.biases[n].slice();
    for (let i = 0; i < layer.length; i++) {
      for (let j = 0; j < output.length; j++) output[j] += layer[i] * weights[i][j];
    }
    layer = n === network.weights.length - 1 ? output : output.map(x => Math.max(0, x));
  }
  return Math.exp(layer[0]);
}

export function createEngine(model, options, report) {
  const support = new Map(options.map(o => [keyFor(o), o]));
  function predict(record) {
    const option = support.get(keyFor(record));
    if (!option) throw new RangeError("Choose a flight combination represented in the training data.");
    const {duration, days_left: days} = record;
    if (!Number.isFinite(duration) || duration < option.durationMin || duration > option.durationMax ||
        !Number.isInteger(days) || days < option.daysMin || days > option.daysMax) {
      throw new RangeError("Duration or booking lead time falls outside this itinerary’s observed range.");
    }
    const x = model.categories.flatMap((values, i) => values.map(v => Number(v === record[categoricalFields[i]])));
    x.push((duration - model.mean[0]) / model.scale[0], (days - model.mean[1]) / model.scale[1]);
    let price = 0;
    if (model.weight > 0) {
      let logPrice = model.boost.bias;
      for (const tree of model.boost.trees) logPrice += treePrediction(tree, x);
      price += model.weight * Math.exp(logPrice);
    }
    if (model.weight < 1) price += (1 - model.weight) * neuralPrediction(model.neural, x);
    const radius = model.radii[record.class];
    return {price, low: Math.max(0, price - radius), high: price + radius};
  }
  return {options, report, predict};
}

export async function loadEngine() {
  const [model, options, report] = await Promise.all(["model", "options", "report"].map(async name => {
    return loadJSON(new URL(name + ".json", import.meta.url), 'Loading the India model');
  }));
  return createEngine(model, options, report);
}
