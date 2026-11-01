const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const VIEWER_ROOT = path.resolve(__dirname, "..", "city-viewer");
const context = vm.createContext({ window: {} });

function loadScript(fileName) {
  vm.runInContext(fs.readFileSync(path.join(VIEWER_ROOT, fileName), "utf8"), context, {
    filename: fileName,
  });
}

function isHiddenKey(key) {
  return key === "hidden" || key.startsWith("hidden_");
}

// The hidden street-view layer was merged into the regular city layers (v3.0.0).
// This check is now a guard: no hidden collection may come back through meta, grid or data files.
loadScript("data_meta.js");
loadScript("grid_all.js");
const metaKeys = Object.keys(context.window.PANO_META).filter(isHiddenKey);
const countKeys = Object.keys(context.window.PANO_COUNT).filter(isHiddenKey);
const gridKeys = Object.keys(context.window.PANO_GRID_ALL).filter(isHiddenKey);
assert.equal(metaKeys.length, 0, `hidden keys returned to PANO_META: ${metaKeys.join(", ")}`);
assert.equal(countKeys.length, 0, `hidden keys returned to PANO_COUNT: ${countKeys.join(", ")}`);
assert.equal(gridKeys.length, 0, `hidden keys returned to PANO_GRID_ALL: ${gridKeys.join(", ")}`);
assert(!fs.existsSync(path.join(VIEWER_ROOT, "hidden_pano.js")), "hidden_pano.js must stay deleted");
const cityFiles = fs.readdirSync(VIEWER_ROOT).filter((name) => /^data_.*\.js$/.test(name) && !/^data_(meta|districts)\.js$/.test(name));
assert(!cityFiles.some((name) => isHiddenKey(name.replace(/^data_|\.js$/g, ""))), "hidden data files must stay deleted");
console.log(`Verified no hidden collections remain across ${cityFiles.length} data files (layer merged into regular city layers)`);
