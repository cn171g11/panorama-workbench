#!/usr/bin/env node
/*
 * Rebuild the nationwide grid and the on-demand search index.
 *
 * The search index lets the viewer answer panoid and road-name queries
 * without loading every city file or rendering the nationwide point layer.
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const VIEWER_ROOT = path.resolve(__dirname, "..", "city-viewer");
const GRID_RESOLUTION = 0.004;
const SEGMENT_START = 15;
const SEGMENT_END = 20;
const PREFIX_LENGTH = 4;

function loadScript(context, fileName) {
  const source = fs.readFileSync(path.join(VIEWER_ROOT, fileName), "utf8");
  vm.runInContext(source, context, { filename: fileName });
}

function parseCityFile(filePath) {
  const source = fs.readFileSync(filePath, "utf8");
  const match = source.match(/PANO_CITY\[(.+?)\]=(\[.*\]);\s*$/s);
  if (!match) return null;
  return { key: JSON.parse(match[1]), entries: JSON.parse(match[2]) };
}

function normalizeRoadName(value) {
  return String(value || "")
    .replace(/[\uFF01-\uFF5E]/g, (character) => String.fromCharCode(character.charCodeAt(0) - 0xfee0))
    .replace(/\u3000/g, " ")
    .toLowerCase()
    .replace(/\s+/g, "");
}

function addToIndex(index, value, key) {
  if (!value) return;
  const existing = index[value];
  if (existing) existing.add(key);
  else index[value] = new Set([key]);
}

function serializeIndex(index) {
  const sortedKeys = Object.keys(index).sort();
  const output = {};
  for (const value of sortedKeys) output[value] = Array.from(index[value]).sort();
  return output;
}

function addEntryToStats(stats, key, entry) {
  const panoramaId = String(entry[0]);
  const longitude = Number(entry[1]);
  const latitude = Number(entry[2]);
  if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) return;

  const cellX = Math.floor(longitude / GRID_RESOLUTION);
  const cellY = Math.floor(latitude / GRID_RESOLUTION);
  const cellKey = `${cellX},${cellY}`;
  const cells = stats.grid[key] || (stats.grid[key] = new Map());
  cells.set(cellKey, (cells.get(cellKey) || 0) + 1);

  if (panoramaId.length >= PREFIX_LENGTH) {
    addToIndex(stats.prefix, panoramaId.slice(0, PREFIX_LENGTH).toUpperCase(), key);
  }
  if (panoramaId.length >= SEGMENT_END) {
    addToIndex(stats.segments, panoramaId.slice(SEGMENT_START, SEGMENT_END).toUpperCase(), key);
  }
  addToIndex(stats.roads, normalizeRoadName(entry[3]), key);
  addToIndex(stats.dates, String(entry[4] || "").trim(), key);
}

function collectCityFiles() {
  return fs
    .readdirSync(VIEWER_ROOT)
    .filter((fileName) => /^data_.*\.js$/.test(fileName))
    .filter((fileName) => fileName !== "data_meta.js" && fileName !== "data_districts.js")
    .map((fileName) => path.join(VIEWER_ROOT, fileName));
}

function buildStats() {
  const stats = { grid: {}, prefix: {}, segments: {}, roads: {}, dates: {} };
  let totalEntries = 0;

  for (const filePath of collectCityFiles()) {
    const city = parseCityFile(filePath);
    if (!city) continue;
    for (const entry of city.entries) {
      addEntryToStats(stats, city.key, entry);
    }
    totalEntries += city.entries.length;
  }

  const context = { window: {} };
  vm.createContext(context);
  loadScript(context, "hidden_pano.js");
  const hiddenEntries = (context.window.PANO_CITY || {}).hidden || [];
  stats.grid.hidden = stats.grid.hidden || new Map();
  for (const entry of hiddenEntries) addEntryToStats(stats, "hidden", entry);
  totalEntries += hiddenEntries.length;

  return { stats, totalEntries };
}

function writeGrid(stats) {
  const output = {};
  for (const key of Object.keys(stats.grid)) {
    const cells = [];
    for (const [cellKey, count] of stats.grid[key]) {
      const [cellX, cellY] = cellKey.split(",").map(Number);
      cells.push([cellX, cellY, count]);
    }
    output[key] = cells;
  }
  const payload = `window.PANO_GRID_ALL=${JSON.stringify(output)};`;
  fs.writeFileSync(path.join(VIEWER_ROOT, "grid_all.js"), payload, "utf8");
  return { keys: Object.keys(output).length, cells: Object.values(output).reduce((sum, list) => sum + list.length, 0), bytes: Buffer.byteLength(payload) };
}

function writeSearchIndex(stats) {
  const payload = `window.PANO_SEARCH_INDEX=${JSON.stringify({
    prefix: serializeIndex(stats.prefix),
    seg1620: serializeIndex(stats.segments),
    roads: serializeIndex(stats.roads),
    dates: serializeIndex(stats.dates),
  })};`;
  fs.writeFileSync(path.join(VIEWER_ROOT, "pano_search_index.js"), payload, "utf8");
  return {
    prefixes: Object.keys(stats.prefix).length,
    segments: Object.keys(stats.segments).length,
    roads: Object.keys(stats.roads).length,
    bytes: Buffer.byteLength(payload),
  };
}

function main() {
  const startedAt = Date.now();
  const { stats, totalEntries } = buildStats();
  const grid = writeGrid(stats);
  const index = writeSearchIndex(stats);
  const seconds = ((Date.now() - startedAt) / 1000).toFixed(1);
  console.log(
    `entries=${totalEntries} grid_keys=${grid.keys} grid_cells=${grid.cells} grid_mb=${(grid.bytes / 1048576).toFixed(2)}`
  );
  console.log(
    `prefixes=${index.prefixes} segments=${index.segments} roads=${index.roads} search_mb=${(index.bytes / 1048576).toFixed(2)} seconds=${seconds}`
  );
}

main();
