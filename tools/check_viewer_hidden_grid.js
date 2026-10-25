const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const VIEWER_ROOT = path.resolve(__dirname, "..", "city-viewer");
const GRID_RESOLUTION = 0.004;
const context = vm.createContext({ window: {} });

function loadScript(fileName) {
  vm.runInContext(fs.readFileSync(path.join(VIEWER_ROOT, fileName), "utf8"), context, {
    filename: fileName,
  });
}

function isHiddenKey(key) {
  return key === "hidden" || key.startsWith("hidden_");
}

loadScript("data_meta.js");
loadScript("grid_all.js");
const generatedGrid = context.window.PANO_GRID_ALL;
const expectedGrid = {};
for (const key of Object.keys(generatedGrid)) {
  if (isHiddenKey(key)) expectedGrid[key] = JSON.stringify(generatedGrid[key]);
}
assert(Object.keys(expectedGrid).length > 0, "grid_all.js has no hidden collections");
loadScript("hidden_pano.js");

let points = 0;
let cells = 0;
for (const [key, serialized] of Object.entries(expectedGrid)) {
  const entries = context.window.PANO_CITY[key];
  const grid = context.window.PANO_GRID_ALL[key];
  assert(entries, `hidden collection ${key} is missing from hidden_pano.js`);
  assert.equal(JSON.stringify(grid), serialized, `${key}: hidden_pano.js replaced the generated grid`);
  assert.equal(entries.length, context.window.PANO_COUNT[key], `${key}: point count mismatch`);
  assert.equal(grid.reduce((total, cell) => total + cell[2], 0), entries.length, `${key}: grid total mismatch`);
  assert(entries.every((entry) => entry.length === 9), `${key}: entry shape changed`);

  const visibleCells = new Set(grid.map((cell) => `${cell[0]},${cell[1]}`));
  for (const entry of entries) {
    const cellX = Math.floor(entry[1] / GRID_RESOLUTION);
    const cellY = Math.floor(entry[2] / GRID_RESOLUTION);
    assert(visibleCells.has(`${cellX},${cellY}`), `${key}: missing grid cell for ${entry[0]}`);
  }
  const province = (context.window.PANO_META[key] || {}).province;
  assert(province, `${key}: province is not set`);
  points += entries.length;
  cells += grid.length;
}

const declared = Object.keys(context.window.PANO_META).filter(isHiddenKey);
assert.deepEqual(declared.sort(), Object.keys(expectedGrid).sort(), "hidden collections in meta and grid differ");
assert(context.window.PANO_GRID_ALL["370500"].length, "Missing regular Dongying grid");
assert(context.window.PANO_GRID_ALL["371600"].length, "Missing regular Binzhou grid");
console.log(`Verified ${declared.length} hidden collections: ${points} points, ${cells} cells`);
