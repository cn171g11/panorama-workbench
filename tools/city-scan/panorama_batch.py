import json
import os
import io
import ssl
import time
import random
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

BASE_DIR = 'E:/Desktop/Github Tools/tencent-panorama-scan/mohe'
OUTPUT_DIR = BASE_DIR + '/panoramas'
SAMPLE_IDS_PATH = BASE_DIR + '/raw/_pano_sample_ids.json'
TILE_HOST = 'sv1.map.qq.com'
ROW_COUNT = 4
COLUMN_COUNT = 8
TILE_SIZE = 512
MIN_VALID_BYTES = 50000
WORKER_COUNT = 8
REQUEST_PAUSE_SECONDS = 0.05
MAX_RETRY_ATTEMPTS = 4
FAIL_RATIO_LIMIT = 0.4
PROGRESS_LOG_INTERVAL = 100
HTTP_TIMEOUT_SECONDS = 25

SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE
HTTP_HEADERS = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://map.qq.com/'}


def log(message):
    print('%s %s' % (time.strftime('%H:%M:%S'), message), flush=True)


def fetch_tile(task):
    svid, x, y = task
    url = 'https://%s/tile?from=web&svid=%s&level=0&x=%d&y=%d' % (TILE_HOST, svid, x, y)
    for attempt in range(MAX_RETRY_ATTEMPTS):
        try:
            time.sleep(REQUEST_PAUSE_SECONDS + random.random() * 0.05)
            request = urllib.request.Request(url, headers=HTTP_HEADERS)
            payload = urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS, context=SSL_CONTEXT).read()
            return (x, y, payload) if payload[:2] == b'\xff\xd8' else (x, y, None)
        except OSError:
            time.sleep(1.0 + attempt * 1.5)
    return (x, y, None)


def assemble_panorama(svid):
    output_path = os.path.join(OUTPUT_DIR, svid + '.jpg')
    if os.path.exists(output_path) and os.path.getsize(output_path) > MIN_VALID_BYTES:
        return ('skip', 0)
    tasks = [(svid, x, y) for y in range(ROW_COUNT) for x in range(COLUMN_COUNT)]
    tiles = {}
    failure_count = 0
    with ThreadPoolExecutor(max_workers=WORKER_COUNT) as executor:
        for x, y, payload in executor.map(fetch_tile, tasks):
            if payload:
                tiles[(x, y)] = payload
            else:
                failure_count += 1
    if failure_count > ROW_COUNT * COLUMN_COUNT * FAIL_RATIO_LIMIT:
        return ('bad', failure_count)
    canvas = Image.new('RGB', (COLUMN_COUNT * TILE_SIZE, ROW_COUNT * TILE_SIZE), (0, 0, 0))
    for (x, y), payload in tiles.items():
        try:
            tile = Image.open(io.BytesIO(payload)).convert('RGB')
        except OSError:
            continue
        canvas.paste(tile, (x * TILE_SIZE, y * TILE_SIZE))
    canvas.save(output_path, 'JPEG', quality=82)
    return ('ok', os.path.getsize(output_path))


def load_pending_ids():
    with open(SAMPLE_IDS_PATH, encoding='utf-8') as handle:
        sample_ids = json.load(handle)
    pending = []
    for svid in sample_ids:
        output_path = os.path.join(OUTPUT_DIR, svid + '.jpg')
        if not os.path.exists(output_path) or os.path.getsize(output_path) <= MIN_VALID_BYTES:
            pending.append(svid)
    return sample_ids, pending


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    sample_ids, pending_ids = load_pending_ids()
    log('resume total=%d pending=%d workers=%d' % (len(sample_ids), len(pending_ids), WORKER_COUNT))
    started_at = time.time()
    stats = {'ok': 0, 'skip': 0, 'bad': 0}
    total_bytes = 0
    for index, svid in enumerate(pending_ids):
        status, size = assemble_panorama(svid)
        stats[status] += 1
        if status == 'ok':
            total_bytes += size
        if (index + 1) % PROGRESS_LOG_INTERVAL == 0 or status == 'bad':
            elapsed = time.time() - started_at
            completed = index + 1
            tile_rate = completed * ROW_COUNT * COLUMN_COUNT / elapsed if elapsed else 0
            remaining = len(pending_ids) - completed
            eta_minutes = remaining / (completed / elapsed) / 60 if elapsed and completed else 0
            log('progress %d/%d ok=%d bad=%d rate=%.1f tile/s eta=%.0f min'
                % (completed, len(pending_ids), stats['ok'], stats['bad'], tile_rate, eta_minutes))
    log('DONE ok=%d skip=%d bad=%d size=%.1f MB elapsed=%.0f s'
        % (stats['ok'], stats['skip'], stats['bad'], total_bytes / 1048576, time.time() - started_at))


if __name__ == '__main__':
    main()
