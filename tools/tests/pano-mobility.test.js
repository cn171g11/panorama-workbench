const assert = require('node:assert/strict');
const { test } = require('node:test');
const { inspectPanorama, createViewingMetadata } = require('../pano-mobility');

const CURRENT_ID = '10101012120819135641300';
const NEIGHBOR_ID = '10101012120901123026900';
const PROJECTED_X = 13200000;
const PROJECTED_Y = 3770000;
const NEXT_PROJECTED_X = 13200010;

function metadata(overrides = {}) {
  return { info: { error: 0 }, detail: { basic: { svid: CURRENT_ID, x: PROJECTED_X, y: PROJECTED_Y },
    roads: [], vpoints: [], all_scenes: [], ...overrides } };
}

function point(identifier, projectedX = PROJECTED_X) {
  return { svid: identifier, x: projectedX, y: PROJECTED_Y };
}

test('keeps a valid historical frame immobile when only history links exist', () => {
  const reply = metadata({ history: [{ svid: NEIGHBOR_ID }] });
  const verification = inspectPanorama(CURRENT_ID, reply);
  assert.equal(verification.status, 'hidden');
  assert.equal(verification.movementCount, 0);
});

test('recognizes forward road navigation as a regular panorama', () => {
  const reply = metadata({ roads: [{ points: [point(CURRENT_ID), point(NEIGHBOR_ID, NEXT_PROJECTED_X)] }] });
  assert.equal(inspectPanorama(CURRENT_ID, reply).status, 'regular');
  assert.equal(createViewingMetadata(CURRENT_ID, reply).movements[0].panoId, NEIGHBOR_ID);
});

test('recognizes scenic sequence navigation independently of the park type', () => {
  const reply = metadata({ all_scenes: [point(NEIGHBOR_ID, NEXT_PROJECTED_X), point(CURRENT_ID)] });
  assert.equal(inspectPanorama(CURRENT_ID, reply).canMove, true);
});

test('does not confuse a self-reference or a zero-coordinate link with movement', () => {
  const reply = metadata({ vpoints: [{ svid: CURRENT_ID, link: [point(CURRENT_ID), { svid: NEIGHBOR_ID, x: 0, y: 0 }] }] });
  assert.equal(inspectPanorama(CURRENT_ID, reply).status, 'hidden');
});

test('rejects an API error even when stale basic metadata is present', () => {
  const reply = metadata();
  reply.info.error = -1;
  assert.equal(inspectPanorama(CURRENT_ID, reply).status, 'invalid');
});

test('rejects missing or mismatched identifiers instead of inventing a hidden frame', () => {
  assert.equal(inspectPanorama(CURRENT_ID, metadata({ basic: { x: PROJECTED_X, y: PROJECTED_Y } })).status, 'invalid');
  assert.equal(inspectPanorama(CURRENT_ID, metadata({ basic: { svid: NEIGHBOR_ID, x: PROJECTED_X, y: PROJECTED_Y } })).status, 'invalid');
});

test('rejects Null Island and absent projection coordinates', () => {
  assert.equal(inspectPanorama(CURRENT_ID, metadata({ basic: { svid: CURRENT_ID, x: 0, y: 0 } })).status, 'invalid');
  assert.equal(inspectPanorama(CURRENT_ID, metadata({ basic: { svid: CURRENT_ID } })).status, 'invalid');
});
