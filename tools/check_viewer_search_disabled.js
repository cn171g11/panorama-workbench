#!/usr/bin/env node
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'city-viewer/index.html'), 'utf8');
const inline = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]).join('\n');
assert(!html.includes('id="search"'), 'Search input should be absent');
assert(!/els\.search|PANO_SEARCH_INDEX|SEARCH_INDEX_FILE|searchActive/.test(inline), 'Stale search reference');
new vm.Script(inline, { filename: 'viewer-inline.js' });

// Execute actual initialization with no search element and unavailable Leaflet.
// This checks DOM wiring; the separate display-mode test covers zoom/LOD behavior.
class Element {
  constructor() { this.style = {}; this.value = ''; this.options = []; this.offsetHeight = 52; }
  set innerHTML(value) { this.html = value; this.options = []; }
  get innerHTML() { return this.html || ''; }
  appendChild(child) { this.options.push(child); }
  addEventListener() {}
}
const elements = Object.fromEntries([...html.matchAll(/\bid="([^"]+)"/g)].map(m => [m[1], new Element()]));
const document = {
  getElementById: id => elements[id] || null,
  createElement: () => new Element(),
  querySelector: () => new Element(),
  addEventListener() {},
  documentElement: { style: { setProperty() {} } },
  head: { appendChild() { throw new Error('Unexpected index/data download at initialization'); } },
};
const win = {
  PANO_META: {
    '500000': { name: '重庆市', province: '重庆市', pref: '500000' },
    hidden_500000: { name: '重庆·隐藏', province: '重庆市', pref: 'hidden_500000' },
    hidden_game: { name: '剑灵', province: '腾讯游戏街景', pref: 'hidden_game' },
  },
  PANO_COUNT: { '500000': 2, hidden_500000: 1, hidden_game: 1 },
  PANO_GRID_ALL: { '500000': [[26500, 7300, 2]], hidden_500000: [[26500, 7300, 1]], hidden_game: [[0, 0, 1]] },
  addEventListener() {},
};
const init = vm.createContext({ window: win, document, navigator: { userAgent: '' }, console, setTimeout() {} });
vm.runInContext(inline, init);
assert(elements.stats.textContent.includes('4 点'), 'Overview failed to initialize');
assert(elements.provinceSelect.innerHTML.includes('重庆市'));
assert(elements.provinceSelect.innerHTML.includes('腾讯游戏街景'), 'Game group disappeared');

// Exercise the actual detail filter/render functions without a search element.
function functionSource(name) {
  const start = html.indexOf(`  function ${name}(`);
  assert(start >= 0, `Missing function: ${name}`);
  const lineEnd = html.indexOf('\n', start);
  if (html.slice(start, lineEnd).trim().endsWith('}')) return html.slice(start, lineEnd);
  const end = html.indexOf('\n  }', start + 1);
  assert(end > start);
  return html.slice(start, end + '\n  }'.length);
}
const a = ['p1', 106.12345678901234, 29.12345678901234, '路A', '2014-01-01', '', 0, 0, '腾讯常规', '500000', '500101'];
const b = ['p2', 106.2, 29.2, '路B', '', '', 0, 0, '腾讯常规', '500000', '500102'];
const h = ['h1', 106.3, 29.3, '路A', '', '', 0, 0, '腾讯隐藏', 'hidden_500000'];
const g = ['game1', 0, 0, '', '', '', 0, 0, '腾讯隐藏', 'hidden_game'];
const original = JSON.stringify([a, b, h, g]);
let rendered;
const scope = vm.createContext({
  state: { entries: [a, b, h, g], results: [], mode: 'detail', dispMode: 'points', countyFilter: '', activePid: null },
  els: { road: { value: '' }, city: { value: '' } },
  map: {}, POINT_LIMIT: 1000000,
  pointLayer: { setData: (base, hits) => { rendered = { base, hits }; } },
});
for (const name of ['isHiddenPref', 'isHiddenEntry', 'computeResults', 'renderMapPoints']) vm.runInContext(functionSource(name), scope);
scope.computeResults();
assert.equal(scope.state.results.length, 4);
scope.renderMapPoints();
assert.equal(rendered.hits.length, 4);
assert.equal(rendered.hits.filter(p => p[3]).length, 2, 'Hidden/game markers lost');
scope.els.city.value = '500000'; scope.computeResults(); assert.equal(scope.state.results.length, 2);
scope.els.road.value = '路A'; scope.computeResults(); assert.equal(scope.state.results.length, 1);
scope.state.countyFilter = '500102'; scope.computeResults(); assert.equal(scope.state.results.length, 0);
assert.equal(JSON.stringify([a, b, h, g]), original, 'Filtering altered panorama data');

const { addEntryToStats } = require('./build_viewer_index');
const stats = { grid: {}, withSearch: false, prefix: {}, segments: {}, roads: {}, dates: {} };
addEntryToStats(stats, '500000', a);
assert.equal(stats.grid['500000'].size, 1);
assert.equal(Object.keys(stats.prefix).length + Object.keys(stats.segments).length + Object.keys(stats.roads).length + Object.keys(stats.dates).length, 0);
const searchStats = { grid: {}, withSearch: true, prefix: {}, segments: {}, roads: {}, dates: {} };
addEntryToStats(searchStats, '500000', a);
assert(Object.keys(searchStats.roads).length, 'Explicit recovery option broken');
assert.equal(JSON.stringify([a, b, h, g]), original);
console.log('PASS: search-free initialization, city/county/road filters, hidden/game markers, default grid-only builder');
