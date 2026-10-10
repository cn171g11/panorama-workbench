import json
import os

ROOT = 'E:/Desktop/Github Tools/tencent-panorama-scan'
VIEWER_DIR = ROOT + '/_viewer'
os.makedirs(VIEWER_DIR, exist_ok=True)


def build_city(city_key, manifest_path, city_dir):
    with open(manifest_path, encoding='utf-8') as handle:
        manifest = json.load(handle)
    entries = []
    missing_thumb = 0
    for record in manifest:
        panoid = record['panoid']
        has_thumb = 1 if os.path.exists(city_dir + '/images/' + panoid + '.jpg') else 0
        has_pano = 1 if os.path.exists(city_dir + '/panoramas/' + panoid + '.jpg') else 0
        if not has_thumb:
            missing_thumb += 1
        entries.append([
            panoid,
            record['lng'],
            record['lat'],
            record.get('road') or '',
            record.get('captured') or '',
            str(record.get('dir') or ''),
            has_thumb,
            has_pano,
        ])
    payload = 'window.PANO_CITY=window.PANO_CITY||{};window.PANO_CITY[%s]=%s;' % (
        json.dumps(city_key),
        json.dumps(entries, ensure_ascii=False, separators=(',', ':')),
    )
    output_path = VIEWER_DIR + '/data_' + city_key + '.js'
    with open(output_path, 'w', encoding='utf-8') as handle:
        handle.write(payload)
    pano_count = sum(item[7] for item in entries)
    print('%s: %d entries, %d pano, %d missing thumb -> %s (%.1f MB)'
          % (city_key, len(entries), pano_count, missing_thumb, output_path, os.path.getsize(output_path) / 1048576))


build_city('mohe', ROOT + '/mohe/mohe-panoramas.json', ROOT + '/mohe')
build_city('erguna', ROOT + '/erguna/erguna-panoramas.json', ROOT + '/erguna')