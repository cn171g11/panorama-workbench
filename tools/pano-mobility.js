'use strict';

const RULE_VERSION = 'navigation-v1';
const MERCATOR_LIMIT = 20037508.34;
const LONGITUDE_LIMIT = 180;
const LATITUDE_LIMIT = 90;
const COORDINATE_PRECISION = 6;
const DIRECTION_OFFSET = 270;
const FULL_CIRCLE = 360;
const MOVEMENT_RANK = { intersection: 3, branch: 2, forward: 1, backward: 1 };
const NEIGHBOR_OFFSETS = [[-1, 'backward'], [1, 'forward']];

function readFiniteNumber(value) {
  if (value === null || value === undefined || value === '' || typeof value === 'boolean') return NaN;
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue : NaN;
}

function hasValidCoordinates(longitude, latitude) {
  return Number.isFinite(longitude) && Number.isFinite(latitude)
    && Math.abs(longitude) <= LONGITUDE_LIMIT && Math.abs(latitude) <= LATITUDE_LIMIT
    && (longitude !== 0 || latitude !== 0);
}

function readLocation(basic, address) {
  const longitude = readFiniteNumber(address?.x_lng ?? address?.lng);
  const latitude = readFiniteNumber(address?.y_lat ?? address?.lat);
  if (hasValidCoordinates(longitude, latitude)) return { lng: longitude, lat: latitude };
  const projectedX = readFiniteNumber(basic?.x), projectedY = readFiniteNumber(basic?.y);
  if (!Number.isFinite(projectedX) || !Number.isFinite(projectedY)) return null;
  const convertedLongitude = projectedX / MERCATOR_LIMIT * LONGITUDE_LIMIT;
  const convertedLatitude = LONGITUDE_LIMIT / Math.PI
    * (2 * Math.atan(Math.exp(projectedY / MERCATOR_LIMIT * Math.PI)) - Math.PI / 2);
  const lng = Number(convertedLongitude.toFixed(COORDINATE_PRECISION));
  const lat = Number(convertedLatitude.toFixed(COORDINATE_PRECISION));
  return hasValidCoordinates(lng, lat) ? { lng, lat } : null;
}

function addMovement(movements, currentId, basic, neighbor, type) {
  const neighborId = String(neighbor?.svid || '');
  const neighborX = readFiniteNumber(neighbor?.x), neighborY = readFiniteNumber(neighbor?.y);
  const currentX = readFiniteNumber(basic?.x), currentY = readFiniteNumber(basic?.y);
  if (!neighborId || neighborId === currentId) return;
  if (![neighborX, neighborY, currentX, currentY].every(Number.isFinite)) return;
  if (neighborX === 0 && neighborY === 0) return;
  const bearing = Math.atan2(neighborX - currentX, neighborY - currentY) * LONGITUDE_LIMIT / Math.PI;
  const angle = (bearing + FULL_CIRCLE + DIRECTION_OFFSET) % FULL_CIRCLE;
  const previous = movements.get(neighborId);
  if (!previous || MOVEMENT_RANK[type] > MOVEMENT_RANK[previous.type]) {
    movements.set(neighborId, { panoId: neighborId, angle, type });
  }
}

function addSequenceMovements(movements, currentId, basic, sequence) {
  if (!Array.isArray(sequence)) return;
  const currentIndex = sequence.findIndex(point => point?.svid === currentId);
  if (currentIndex < 0) return;
  for (const [offset, type] of NEIGHBOR_OFFSETS) {
    addMovement(movements, currentId, basic, sequence[currentIndex + offset], type);
  }
}

function readMovements(detail, currentId) {
  // History switches and scenic exits do not establish forward/backward street navigation.
  const movements = new Map();
  for (const road of detail?.roads || []) {
    addSequenceMovements(movements, currentId, detail.basic, road?.points);
  }
  for (const intersection of detail?.vpoints || []) {
    if (intersection?.svid !== currentId) continue;
    for (const neighbor of intersection.link || []) {
      addMovement(movements, currentId, detail.basic, neighbor, 'intersection');
    }
  }
  addSequenceMovements(movements, currentId, detail.basic, detail?.all_scenes);
  return [...movements.values()];
}

function invalidPanorama(currentId, reason) {
  return { sid: currentId, ruleVersion: RULE_VERSION, status: 'invalid',
    isValid: false, canMove: false, movementCount: 0, movementIds: [], reason };
}

function inspectPanorama(currentId, responsePayload) {
  if (!currentId || !responsePayload || typeof responsePayload !== 'object' || Array.isArray(responsePayload)) {
    throw new TypeError('A panorama identifier and metadata object are required');
  }
  const errorCode = readFiniteNumber(responsePayload.info?.error ?? responsePayload.info?.errno);
  if (Number.isFinite(errorCode) && errorCode !== 0) return invalidPanorama(currentId, `metadata-error:${errorCode}`);
  const detail = responsePayload.detail, basic = detail?.basic;
  if (!basic) return invalidPanorama(currentId, 'missing-basic');
  if (String(basic.svid || '') !== currentId) return invalidPanorama(currentId, 'svid-mismatch');
  const location = readLocation(basic, detail.addr || responsePayload.addr);
  if (!location) return invalidPanorama(currentId, 'zero-or-invalid-coordinates');
  const movements = readMovements(detail, currentId);
  return { sid: currentId, ruleVersion: RULE_VERSION, status: movements.length ? 'regular' : 'hidden',
    isValid: true, canMove: movements.length > 0, movementCount: movements.length,
    movementIds: movements.map(movement => movement.panoId), location };
}

function createViewingMetadata(currentId, responsePayload) {
  const verification = inspectPanorama(currentId, responsePayload);
  if (!verification.isValid) return { verification, Heading: 0, movements: [] };
  return { verification, Heading: readFiniteNumber(responsePayload.detail.basic.dir) || 0,
    movements: readMovements(responsePayload.detail, currentId) };
}

module.exports = { RULE_VERSION, inspectPanorama, createViewingMetadata };
