import json,os,collections
BASE='E:/Desktop/Github Tools/tencent-panorama-scan/mohe'
st=json.load(open(BASE+'/raw/_state.json',encoding='utf-8'))
recs=st['recs']
def when(svid):
    s=svid[8:18]
    if len(s)<10 or not s.isdigit(): return None
    return '20%s-%s-%s %s:%s'%(s[0:2],s[2:4],s[4:6],s[6:8],s[8:10])
out=[]
for p in sorted(recs,key=lambda x:(x.get('addr') or '',x['svid'])):
    tf=BASE+'/images/'+p['svid']+'.jpg'
    pf=BASE+'/panoramas/'+p['svid']+'.jpg'
    out.append({'panoid':p['svid'],'lng':round(p['lng'],6),'lat':round(p['lat'],6),
        'dir':p.get('dir'),'road':p.get('addr'),'segment_id':p.get('rdid'),
        'captured':when(p['svid']),'source':p.get('source'),
        'thumb':('images/'+p['svid']+'.jpg') if os.path.exists(tf) else None,
        'panorama':('panoramas/'+p['svid']+'.jpg') if os.path.exists(pf) else None})
json.dump(out,open(BASE+'/mohe-panoramas.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
json.dump([o['panoid'] for o in out],open(BASE+'/mohe-panoids.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
open(BASE+'/mohe-panoids.txt','w',encoding='utf-8').write('\n'.join(o['panoid'] for o in out))
imgs=len([o for o in out if o['thumb']])
lngs=[o['lng'] for o in out]; lats=[o['lat'] for o in out]
lines=[]
lines.append('# 漠河市腾讯街景全量扫描（2026-10-09）')
lines.append('')
lines.append('- 扫描方式：从市区+北极村 2 个种子点出发，沿 `all_scenes` 相邻采集点 BFS 爬行，漠河市界多边形实时过滤')
lines.append('- 数据源：腾讯街景非官方接口（sv.map.qq.com /sv、sv1.map.qq.com /thumb /tile），GBK 解码')
lines.append('- 坐标过滤：阿里 DataV GeoAtlas `232701.json` 漠河市边界（ruiduobao.com 同源行政区划体系备用）')
lines.append('')
lines.append('| 指标 | 数值 |')
lines.append('|---|---|')
lines.append('| 街景点（panoid）总数 | %d |'%len(out))
lines.append('| 已下载缩略图（512x256） | %d |'%imgs)
lines.append('| 道路/路段数 | %d |'%len(set(o['road'] or '?' for o in out)))
lines.append('| 采集年代 | %s ~ %s（soso 时期）|'%(min(o['captured'][:4] for o in out if o['captured']),max(o['captured'][:4] for o in out if o['captured'])))
lines.append('| 经度范围 | %.5f ~ %.5f |'%(min(lngs),max(lngs)))
lines.append('| 纬度范围 | %.5f ~ %.5f |'%(min(lats),max(lats)))
lines.append('| 审图号 | %s |'%(out[0].get('source') and 'GS(2018)1865号（接口返回）'))
lines.append('')
lines.append('## 文件结构')
lines.append('```')
lines.append('mohe/')
lines.append('  mohe-panoramas.json   # 全量清单：panoid/坐标/朝向/道路/采集时间/图片路径')
lines.append('  mohe-panoids.json|.txt# 纯 panoid 列表')
lines.append('  mohe-boundary.geojson # 漠河市边界（adcode 232701）')
lines.append('  images/               # 全量缩略图 <panoid>.jpg（512x256）')
lines.append('  panoramas/            # 高清全景 <panoid>.jpg（4096x2048，80m 网格采样）')
lines.append('  raw/                  # BFS 中间数据与探针（含 entrances 字段，仅内部使用）')
lines.append('```')
lines.append('')
lines.append('## ⚠️ 合规与使用注意')
lines.append('1. 非官方接口：无文档/无 SLA，随时可能变更；影像版权归腾讯，商用需解决授权（审图号 GS(2018)1865号）')
lines.append('2. **`entrances` 字段已从本清单剔除**（detail.region.entrances 会返回地名，直接泄露猜谜答案）；原始数据在 raw/ 内部保留')
lines.append('3. 请求速率：~13-30 req/s；曾因 16 并发全速触发 29 分钟 IP 风控（500），已验证该阈值，重试需降速')
lines.append('4. 全景图为 4x8 瓦片拼接（level0），如需 level1（8192x4096）可按同一 svid 换 level 参数重取')
open(BASE+'/README.md','w',encoding='utf-8').write('\n'.join(lines))
print('manifests written: %d panoids, thumbs=%d'%(len(out),imgs))
print('roads:',len(set(o['road'] or '?' for o in out)))
print('sample:',json.dumps(out[0],ensure_ascii=False)[:200])
