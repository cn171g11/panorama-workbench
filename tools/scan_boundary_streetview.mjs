#!/usr/bin/env node
/*
 * Seed a boundary with /xf probes, then expand through /sv metadata with BFS.
 *
 * Each response is fed to the navigation-v1 rule, so the mobility verdict is produced by
 * the same code the audit tool uses: no second pass over the points is needed.
 *
 * Expansion is restricted to the boundary bbox plus a small margin, otherwise a sequence
 * that crosses into the neighbouring province would drag the scan out of the region.
 *
 * State is resumable: records append to JSONL, and the visited/frontier lists are
 * checkpointed to a small JSON file.
 *
 * Usage:
 *   node tools/scan_boundary_streetview.mjs --adcode 810000 --boundaries <dir> --work <dir>
 */
import fs from 'node:fs';
import path from 'node:path';
import net from 'node:net';
import tls from 'node:tls';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { RULE_VERSION, inspectPanorama } = require('./pano-mobility.js');

const MERCATOR_LIMIT = 20037508.34;
const DECODE = (buffer) => {
  try { return new TextDecoder('gbk').decode(buffer); } catch { return new TextDecoder('utf-8').decode(buffer); }
};

const args = { rate: 12.5, seedStep: 0.004, radius: 250, margin: 0.02, checkpoint: 2000 };
for (let index = 2; index < process.argv.length; index += 1) {
  const flag = process.argv[index];
  const value = process.argv[index + 1];
  if (flag === '--adcode') { args.adcode = value; index += 1; }
  else if (flag === '--boundaries') { args.boundaries = value; index += 1; }
  else if (flag === '--work') { args.work = value; index += 1; }
  else if (flag === '--proxy') { args.proxy = value; index += 1; }
  else if (flag === '--rate') { args.rate = Number(value); index += 1; }
  else if (flag === '--seed-step') { args.seedStep = Number(value); index += 1; }
  else if (flag === '--name') { args.name = value; index += 1; }
  else if (flag === '--seed-only') { args.seedOnly = true; }
  else if (flag === '--harvest') { args.harvest = true; }
  else if (flag === '--max-visits') { args.maxVisits = Number(value); index += 1; }
  else throw new Error(`unknown argument ${flag}`);
}
if (!args.adcode || !args.boundaries || !args.work) throw new Error('--adcode --boundaries --work are required');
fs.mkdirSync(args.work, { recursive: true });

/* ---------------------------------------------------------------- rate + routes */
const RATE_QUOTA = 16.7;
const rate = { current: Math.min(args.rate, RATE_QUOTA * 0.85) };
const bucket = { tokens: 6, refilledAt: Date.now() };
const routes = {
  direct: { blockedUntil: 0, penaltyMs: 30000 },
  proxy: { blockedUntil: 0, penaltyMs: 30000 },
};
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function takeToken() {
  for (;;) {
    const now = Date.now();
    bucket.tokens = Math.min(6, bucket.tokens + ((now - bucket.refilledAt) / 1000) * rate.current);
    bucket.refilledAt = now;
    if (bucket.tokens >= 1) { bucket.tokens -= 1; return; }
    await sleep(Math.max(20, Math.ceil(((1 - bucket.tokens) / rate.current) * 1000)));
  }
}

let cursor = 0;
let failures = 0;
let lastSave = Date.now();
function availableRoutes() {
  const now = Date.now();
  const list = [];
  if (now >= routes.direct.blockedUntil) list.push('direct');
  if (args.proxy && now >= routes.proxy.blockedUntil) list.push('proxy');
  return list;
}
async function waitForRoute() {
  for (;;) {
    const list = availableRoutes();
    if (list.length) return list[cursor++ % list.length];
    const soonest = Math.min(routes.direct.blockedUntil, args.proxy ? routes.proxy.blockedUntil : Infinity);
    await sleep(Math.max(1000, soonest - Date.now()));
  }
}
function blockRoute(name) {
  routes[name].blockedUntil = Date.now() + routes[name].penaltyMs;
  routes[name].penaltyMs = Math.min(180000, routes[name].penaltyMs * 2);
  rate.current = Math.max(4, Number((rate.current * 0.7).toFixed(1)));
  process.stderr.write(`route ${name} blocked for ${Math.round(routes[name].penaltyMs / 1000)}s\n`);
}
function forgiveRoute(name) {
  routes[name].penaltyMs = 30000;
  rate.current = Math.min(args.rate, Number((rate.current + 0.3).toFixed(1)));
}

/* ---------------------------------------------------------------- http */
function openTunnel(proxy, host, port) {
  return new Promise((resolve, reject) => {
    const socket = net.connect(Number(proxy.port || 80), proxy.hostname);
    socket.once('connect', () => {
      socket.write(`CONNECT ${host}:${port} HTTP/1.1\r\nHost: ${host}:${port}\r\n\r\n`);
      let buffer = '';
      const onData = (chunk) => {
        buffer += chunk.toString('latin1');
        if (!buffer.includes('\r\n\r\n')) return;
        socket.removeListener('data', onData);
        if (!buffer.slice(0, buffer.indexOf('\r\n')).includes(' 200')) return reject(new Error('proxy-connect'));
        const secure = tls.connect({ socket, servername: host });
        secure.once('secureConnect', () => resolve(secure));
        secure.once('error', reject);
      };
      socket.on('data', onData);
    });
    socket.once('error', reject);
  });
}

async function httpGetJson(url, attempts = 3) {
  let route = await waitForRoute();
  await takeToken();
  for (let attempt = 0; attempt < attempts; attempt += 1) {
  try {
    let buffer;
    if (route === 'proxy') {
      const target = new URL(url);
      const socket = await openTunnel(new URL(args.proxy), target.hostname, target.port || 443);
      buffer = await new Promise((resolve, reject) => {
        const chunks = [];
        socket.on('data', (chunk) => chunks.push(chunk));
        socket.once('error', reject);
        socket.once('close', () => resolve(Buffer.concat(chunks)));
        socket.write(`GET ${target.pathname}${target.search} HTTP/1.1\r\nHost: ${target.hostname}\r\n`
          + 'User-Agent: Mozilla/5.0\r\nReferer: https://map.qq.com/\r\nConnection: close\r\n\r\n');
      });
      const split = buffer.indexOf('\r\n\r\n');
      const head = buffer.slice(0, split).toString('latin1');
      if (!head.includes(' 200')) throw new Error(`http-${head.split(' ')[1]}`);
      buffer = buffer.slice(split + 4);
    } else {
      const response = await fetch(url, {
        signal: AbortSignal.timeout(20000),
        headers: { 'User-Agent': 'Mozilla/5.0', Referer: 'https://map.qq.com/' },
      });
      if (!response.ok) throw new Error(`http-${response.status}`);
      buffer = Buffer.from(await response.arrayBuffer());
    }
    forgiveRoute(route);
    return JSON.parse(DECODE(buffer));
  } catch (error) {
    blockRoute(route);
    route = await waitForRoute();
    await takeToken();
  }
  }
  failures += 1;
  return null;
}

/* ---------------------------------------------------------------- geometry */
function readFeatures(adcode) {
  // The district file (areas_v3/bound/<adcode>_full.json) is far more detailed than the
  // country-level outline: 5564 vs 109 vertices for Hong Kong, 479 vs 12 for Macao.
  // A coarse outline cuts streets that run along the waterfront, so prefer it.
  const detailed = path.join(args.boundaries, `${adcode}.json`);
  let features;
  if (fs.existsSync(detailed)) {
    const data = JSON.parse(fs.readFileSync(detailed, 'utf8'));
    features = data.features.filter((item) => item.properties?.name && item.geometry);
  } else {
    const country = JSON.parse(fs.readFileSync(path.join(args.boundaries, 'country.json'), 'utf8'));
    const feature = country.features.find((item) => String(item.properties.adcode) === adcode);
    if (!feature) throw new Error(`boundary ${adcode} not found`);
    features = [feature];
  }
  const rings = [];
  for (const feature of features) {
    const geometry = feature.geometry;
    const polygons = geometry.type === 'MultiPolygon' ? geometry.coordinates : [geometry.coordinates];
    for (const polygon of polygons) if (polygon[0] && polygon[0].length > 3) rings.push(polygon[0]);
  }
  if (!rings.length) throw new Error(`boundary ${adcode} has no usable rings`);
  return rings;
}

function inRing(lng, lat, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if ((yi > lat) !== (yj > lat) && lng < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

/* ---------------------------------------------------------------- state */
const recordsPath = path.join(args.work, `${args.adcode}.jsonl`);
const statePath = path.join(args.work, `${args.adcode}-state.json`);
const rings = readFeatures(args.adcode);
const lngs = rings.flat().map((point) => point[0]);
const lats = rings.flat().map((point) => point[1]);
const bbox = [Math.min(...lngs), Math.min(...lats), Math.max(...lngs), Math.max(...lats)];
const expandBox = [bbox[0] - args.margin, bbox[1] - args.margin, bbox[2] + args.margin, bbox[3] + args.margin];
const inside = (lng, lat) => rings.some((ring) => inRing(lng, lat, ring));

let visited = new Set();
let frontier = [];
let records = 0;
if (fs.existsSync(statePath)) {
  const state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
  visited = new Set(state.visited);
  frontier = state.frontier;
  records = state.records;
  process.stderr.write(`resume: visited=${visited.size} frontier=${frontier.length} records=${records}\n`);
}

const sink = fs.createWriteStream(recordsPath, { flags: 'a' });
function saveState() {
  fs.writeFileSync(statePath, JSON.stringify({ visited: [...visited], frontier, records }), 'utf8');
}

/* ---------------------------------------------------------------- seeding */
function mercatorToLngLat(x, y) {
  const lng = (x / MERCATOR_LIMIT) * 180;
  const lat = (180 / Math.PI) * (2 * Math.atan(Math.exp((y / MERCATOR_LIMIT) * Math.PI)) - Math.PI / 2);
  return [lng, lat];
}

async function seed() {
  const cells = [];
  for (let lat = bbox[1]; lat <= bbox[3]; lat += args.seedStep) {
    for (let lng = bbox[0]; lng <= bbox[2]; lng += args.seedStep) {
      if (inside(lng, lat)) cells.push([lng, lat]);
    }
  }
  process.stderr.write(`seed cells inside boundary: ${cells.length}\n`);
  const seeds = new Set();
  let index = 0;
  let probed = 0;
  let failedCells = [];
  async function worker(queue) {
    while (index < queue.length) {
      const [lng, lat] = queue[index++];
      const before = failures;
      const payload = await httpGetJson(
        `https://sv.map.qq.com/xf?lat=${lat.toFixed(5)}&lng=${lng.toFixed(5)}&r=${args.radius}&output=json`);
      probed += 1;
      if (failures > before) failedCells.push([lng, lat]);
      const svid = payload?.detail?.svid;
      if (svid && !visited.has(svid)) seeds.add(svid);
      if (probed % 200 === 0) process.stderr.write(`seed ${probed}/${queue.length} found=${seeds.size} failed=${failedCells.length}\n`);
    }
  }
  await Promise.all(Array.from({ length: 10 }, () => worker(cells)));
  // A refused probe hides coverage, so failed cells are retried before the seed set is trusted.
  if (failedCells.length) {
    process.stderr.write(`retrying ${failedCells.length} failed seed cells\n`);
    const retry = failedCells;
    failedCells = [];
    index = 0;
    await Promise.all(Array.from({ length: 10 }, () => worker(retry)));
    process.stderr.write(`after retry found=${seeds.size} still_failed=${failedCells.length}\n`);
  }
  for (const svid of seeds) frontier.push(svid);
  process.stderr.write(`seeded ${seeds.size} panoramas (cells=${cells.length})\n`);
}

/* ---------------------------------------------------------------- expansion */
async function expand() {
  let processed = 0;
  const started = Date.now();
  while (frontier.length) {
    const batch = frontier.splice(0, 40);
    const queue = [...new Set(batch)].filter((sid) => !visited.has(sid));
    const results = await Promise.all(queue.map(async (sid) => {
      const payload = await httpGetJson(`https://sv.map.qq.com/sv?svid=${encodeURIComponent(sid)}&output=json`);
      return { sid, payload };
    }));
    for (const { sid, payload } of results) {
      if (visited.has(sid)) continue;
      visited.add(sid);
      processed += 1;
      if (!payload) continue;
      const verification = inspectPanorama(sid, payload);
      if (!verification.isValid) continue;
      const { lng, lat } = verification.location;
      const basic = payload.detail.basic;
      if (inside(lng, lat)) {
        emit({ sid, lng, lat, dir: String(basic.dir || ''), road: basic.name || '',
               captured: capturedOf(sid), status: verification.status,
               movementCount: verification.movementCount, origin: 'measured' });
      }
      if (args.harvest) harvestSequence(payload);
      for (const neighbor of collectNeighbors(payload)) {
        if (!visited.has(neighbor)) frontier.push(neighbor);
      }
    }
    if (processed % 500 < 24) {
      const elapsed = (Date.now() - started) / 1000;
      process.stderr.write(`records=${records} visited=${visited.size} frontier=${frontier.length} `
        + `rate=${(processed / elapsed).toFixed(1)}/s budget=${rate.current}/s elapsed=${elapsed.toFixed(0)}s\n`);
    }
    if (Date.now() - lastSave > 60000) { saveState(); lastSave = Date.now(); }
    if (args.maxVisits && visited.size >= args.maxVisits) {
      process.stderr.write(`max-visits ${args.maxVisits} reached\n`);
      break;
    }
  }
}

function collectNeighbors(payload) {
  const detail = payload.detail || {};
  const out = [];
  const consider = (item) => {
    const id = item?.svid;
    if (!id || visited.has(id)) return;
    const x = Number(item.x);
    const y = Number(item.y);
    if (!Number.isFinite(x) || !Number.isFinite(y) || (x === 0 && y === 0)) return;
    const [lng, lat] = mercatorToLngLat(x, y);
    // Only walk inside the region itself: a sequence that crosses the land border would
    // otherwise pull the scan into the neighbouring province and waste the quota there.
    if (!inside(lng, lat)) return;
    out.push(id);
  };
  for (const road of detail.roads || []) for (const point of road.points || []) consider(point);
  for (const intersection of detail.vpoints || []) for (const link of intersection.link || []) consider(link);
  for (const scene of detail.all_scenes || []) consider(scene);
  return out;
}

function capturedOf(sid) {
  return /^\d{23}$/.test(sid)
    ? `20${sid.slice(8, 10)}-${sid.slice(10, 12)}-${sid.slice(12, 14)} ${sid.slice(14, 16)}:${sid.slice(16, 18)}`
    : '';
}

function emit(record) {
  sink.write(`${JSON.stringify(record)}\n`);
  records += 1;
}

/* One response carries the whole street sequence in all_scenes (200-450 frames with
 * their mercator coordinates). Recording those frames directly turns a per-panorama
 * walk into a per-sequence one, which is what makes a province-sized region feasible:
 * a frame that sits next to another frame in the same sequence has an adjacent frame,
 * so it is regular under navigation-v1 by construction. */
function harvestSequence(payload) {
  const detail = payload.detail || {};
  const candidates = [];
  for (const scene of detail.all_scenes || []) candidates.push(scene);
  for (const road of detail.roads || []) for (const point of road.points || []) candidates.push(point);
  for (const intersection of detail.vpoints || []) for (const link of intersection.link || []) candidates.push(link);
  for (const item of candidates) {
    const id = item?.svid;
    if (!id || visited.has(id)) continue;
    const x = Number(item.x);
    const y = Number(item.y);
    if (!Number.isFinite(x) || !Number.isFinite(y) || (x === 0 && y === 0)) continue;
    const [lng, lat] = mercatorToLngLat(x, y);
    if (!inside(lng, lat)) continue;
    visited.add(id);
    emit({ sid: id, lng, lat, dir: '', road: '', captured: capturedOf(id),
           status: 'regular', movementCount: 2, origin: 'sequence' });
  }
}

/* ---------------------------------------------------------------- main */
const started = Date.now();
process.stderr.write(`boundary ${args.adcode} bbox=${bbox.map((v) => v.toFixed(3)).join(',')} rate=${rate.current}/s\n`);
if (!visited.size) {
  await seed();
  saveState();
}
if (!args.seedOnly) await expand();
saveState();
sink.end();
const elapsed = (Date.now() - started) / 1000;
process.stderr.write(`done records=${records} visited=${visited.size} frontier=${frontier.length} seconds=${elapsed.toFixed(0)}\n`);
