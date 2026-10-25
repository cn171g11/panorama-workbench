/**
 * Split the single "hidden" collection into per-province collections.
 *
 * Province attribution is data-driven: every city-layer point votes for its
 * province inside a coarse grid cell, and each hidden panorama takes the
 * majority province of its cell (expanding up to two rings when empty).
 */
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const VIEWER_ROOT = path.resolve(import.meta.dirname, '..', 'city-viewer');
const VOTE_CELL = 0.2;
const GRID_CELL = 0.004;
const HIDDEN_NAME = '腾讯隐藏街景/时光机';
const MARKER = '腾讯隐藏';

function jsonEnd(source, start) {
  let depth = 0;
  let inString = false;
  let escaped = false;
  for (let index = start; index < source.length; index++) {
    const char = source[index];
    if (inString) {
      if (escaped) escaped = false;
      else if (char === '\\') escaped = true;
      else if (char === '"') inString = false;
      continue;
    }
    if (char === '"') { inString = true; continue; }
    if (char === '{' || char === '[') depth += 1;
    else if (char === '}' || char === ']') {
      depth -= 1;
      if (depth === 0) return index + 1;
    }
  }
  throw new Error('unterminated JSON at ' + start);
}

function assignmentBounds(source, name) {
  const marker = `window.${name}=`;
  const start = source.indexOf(marker) + marker.length;
  return { start, end: jsonEnd(source, start) };
}

function readAssignment(source, name) {
  const { start, end } = assignmentBounds(source, name);
  return JSON.parse(source.slice(start, end));
}

function parseCityFile(filePath) {
  const source = fs.readFileSync(filePath, 'utf8');
  const context = { window: {} };
  vm.createContext(context);
  vm.runInContext(source, context, { timeout: 60000 });
  const collection = context.window.PANO_CITY || {};
  const key = Object.keys(collection)[0];
  return key ? { key, entries: collection[key] } : null;
}

function provincePrefixes(meta) {
  const byProvince = new Map();
  for (const [key, definition] of Object.entries(meta)) {
    if (!/^\d{6}$/.test(key)) continue;
    const province = definition.province;
    if (!province) continue;
    const counts = byProvince.get(province) || new Map();
    const prefix = key.slice(0, 2);
    counts.set(prefix, (counts.get(prefix) || 0) + 1);
    byProvince.set(province, counts);
  }
  const result = new Map();
  for (const [province, counts] of byProvince) {
    const [prefix] = [...counts.entries()].sort((a, b) => b[1] - a[1])[0];
    result.set(province, prefix);
  }
  return result;
}

function buildVotes(meta) {
  const votes = new Map();
  const files = fs.readdirSync(VIEWER_ROOT).filter((name) => /^data_.+\.js$/.test(name)
    && name !== 'data_meta.js' && name !== 'data_districts.js' && !name.startsWith('data_hidden')
    && !name.startsWith('data_qq_'));
  let seen = 0;
  for (const name of files) {
    const city = parseCityFile(path.join(VIEWER_ROOT, name));
    if (!city) continue;
    const province = (meta[city.key] || {}).province;
    if (!province) continue;
    for (const entry of city.entries) {
      const cx = Math.floor(entry[1] / VOTE_CELL);
      const cy = Math.floor(entry[2] / VOTE_CELL);
      const cellKey = cx + ',' + cy;
      let bucket = votes.get(cellKey);
      if (!bucket) { bucket = new Map(); votes.set(cellKey, bucket); }
      bucket.set(province, (bucket.get(province) || 0) + 1);
      seen += 1;
    }
  }
  return { votes, seen };
}

function assignProvince(votes, lng, lat) {
  const cx = Math.floor(lng / VOTE_CELL);
  const cy = Math.floor(lat / VOTE_CELL);
  for (let ring = 0; ring <= 2; ring++) {
    const totals = new Map();
    for (let dx = -ring; dx <= ring; dx++) {
      for (let dy = -ring; dy <= ring; dy++) {
        if (Math.max(Math.abs(dx), Math.abs(dy)) !== ring) continue;
        const bucket = votes.get((cx + dx) + ',' + (cy + dy));
        if (!bucket) continue;
        for (const [province, count] of bucket) totals.set(province, (totals.get(province) || 0) + count);
      }
    }
    if (totals.size) {
      return [...totals.entries()].sort((a, b) => b[1] - a[1])[0][0];
    }
  }
  return null;
}

function gridOf(entries) {
  const cells = new Map();
  for (const entry of entries) {
    const cellKey = Math.floor(entry[1] / GRID_CELL) + ',' + Math.floor(entry[2] / GRID_CELL);
    cells.set(cellKey, (cells.get(cellKey) || 0) + 1);
  }
  return [...cells.entries()].map(([cellKey, count]) => {
    const [x, y] = cellKey.split(',').map(Number);
    return [x, y, count];
  });
}

const metaSource = fs.readFileSync(path.join(VIEWER_ROOT, 'data_meta.js'), 'utf8');
const meta = readAssignment(metaSource, 'PANO_META');
const counts = readAssignment(metaSource, 'PANO_COUNT');
const prefixes = provincePrefixes(meta);

console.log(JSON.stringify({ step: 'prefixes', provinces: prefixes.size }), null, 0);
const { votes, seen } = buildVotes(meta);
console.log(JSON.stringify({ step: 'votes', points: seen, cells: votes.size }));

const hiddenSource = fs.readFileSync(path.join(VIEWER_ROOT, 'hidden_pano.js'), 'utf8');
const hiddenBounds = assignmentBounds(hiddenSource, 'PANO_CITY["hidden"]');
const hiddenEntries = JSON.parse(hiddenSource.slice(hiddenBounds.start, hiddenBounds.end));

const groups = new Map();
let unassigned = 0;
for (const entry of hiddenEntries) {
  const province = assignProvince(votes, entry[1], entry[2]);
  const prefix = province ? prefixes.get(province) : null;
  if (!prefix) { unassigned += 1; }
  const key = prefix ? 'hidden_' + prefix : 'hidden';
  if (!groups.has(key)) groups.set(key, { province: province || HIDDEN_NAME, entries: [] });
  groups.get(key).entries.push(entry);
}

const ordered = [...groups.keys()].sort((a, b) => (a === 'hidden' ? 1 : b === 'hidden' ? -1 : a.localeCompare(b)));
const parts = [
  'window.PANO_META=window.PANO_META||{};window.PANO_COUNT=window.PANO_COUNT||{};',
  'window.PANO_GRID_ALL=window.PANO_GRID_ALL||{};window.PANO_CITY=window.PANO_CITY||{};',
];
const metaUpdates = {};
for (const key of ordered) {
  const group = groups.get(key);
  const province = key === 'hidden' ? HIDDEN_NAME : group.province;
  parts.push(`window.PANO_META[${JSON.stringify(key)}]=${JSON.stringify({ name: HIDDEN_NAME, province, pref: key })};`);
  parts.push(`window.PANO_COUNT[${JSON.stringify(key)}]=${group.entries.length};`);
  parts.push(`window.PANO_GRID_ALL[${JSON.stringify(key)}]=${JSON.stringify(gridOf(group.entries))};`);
  parts.push(`window.PANO_CITY[${JSON.stringify(key)}]=${JSON.stringify(group.entries)};`);
  metaUpdates[key] = { name: HIDDEN_NAME, province, pref: key, count: group.entries.length };
}

fs.writeFileSync(path.join(VIEWER_ROOT, 'hidden_pano.js'), parts.join(''), 'utf8');

for (const key of Object.keys(meta)) {
  if (key === 'hidden' || key.startsWith('hidden_')) { delete meta[key]; delete counts[key]; }
}
for (const [key, update] of Object.entries(metaUpdates)) {
  meta[key] = { name: update.name, province: update.province, pref: update.pref };
  counts[key] = update.count;
}
const metaBounds = assignmentBounds(metaSource, 'PANO_META');
const countsBounds = assignmentBounds(metaSource, 'PANO_COUNT');
fs.writeFileSync(path.join(VIEWER_ROOT, 'data_meta.js'),
  metaSource.slice(0, metaBounds.start) + JSON.stringify(meta)
  + metaSource.slice(metaBounds.end, countsBounds.start) + JSON.stringify(counts)
  + metaSource.slice(countsBounds.end),
  'utf8');

console.log(JSON.stringify({ groups: Object.fromEntries(Object.entries(metaUpdates).map(([k, v]) => [k, v.count])),
  unassigned, total: hiddenEntries.length }, null, 1));
