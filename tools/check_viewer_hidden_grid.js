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

loadScript("data_meta.js");
loadScript("grid_all.js");
const expectedGrid = JSON.stringify(context.window.PANO_GRID_ALL.hidden);
loadScript("hidden_pano.js");

const hiddenEntries = context.window.PANO_CITY.hidden;
const hiddenGrid = context.window.PANO_GRID_ALL.hidden;
assert.equal(JSON.stringify(hiddenGrid), expectedGrid, "hidden_pano.js replaced the generated grid");
assert.equal(hiddenEntries.length, context.window.PANO_COUNT.hidden);
assert.equal(hiddenGrid.reduce((total, cell) => total + cell[2], 0), hiddenEntries.length);

const visibleCells = new Set(hiddenGrid.map((cell) => `${cell[0]},${cell[1]}`));
for (const entry of hiddenEntries) {
  const cellX = Math.floor(entry[1] / GRID_RESOLUTION);
  const cellY = Math.floor(entry[2] / GRID_RESOLUTION);
  assert(visibleCells.has(`${cellX},${cellY}`), `Missing hidden panorama grid cell: ${entry[0]}`);
}
assert(context.window.PANO_GRID_ALL["370500"].length, "Missing regular Dongying grid");
assert(context.window.PANO_GRID_ALL["371600"].length, "Missing regular Binzhou grid");
console.log(`Verified actual load order: ${hiddenEntries.length} hidden points, ${hiddenGrid.length} cells`);
