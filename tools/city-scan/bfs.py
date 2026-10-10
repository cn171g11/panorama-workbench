import json,ssl,urllib.request,time,math,os
from concurrent.futures import ThreadPoolExecutor
BASE='E:/Desktop/Github Tools/tencent-panorama-scan/mohe'
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
b=json.load(open(BASE+'/mohe-boundary.geojson',encoding='utf-8'))
geom=b['features'][0]['geometry']
rings=[p[0] for p in geom['coordinates']] if geom['type']=='MultiPolygon' else [geom['coordinates'][0]]
def pip(lng,lat,ring):
    inside=False; n=len(ring); j=n-1
    for i in range(n):
        xi,yi=ring[i][0],ring[i][1]; xj,yj=ring[j][0],ring[j][1]
        if ((yi>lat)!=(yj>lat)) and (lng<(xj-xi)*(lat-yi)/(yj-yi+1e-15)+xi): inside=not inside
        j=i
    return inside
def in_mohe(lng,lat): return any(pip(lng,lat,r) for r in rings)
def merc2ll(x,y):
    return x/20037508.34*180, 180/math.pi*(2*math.atan(math.exp((y/20037508.34*180)*math.pi/180))-math.pi/2)

PAUSE=300  # 风控暂停秒数
def fetch(sid):
    for att in range(4):
        try:
            time.sleep(0.22)
            r=urllib.request.Request('https://sv.map.qq.com/sv?svid=%s&output=json'%sid,
                headers={'User-Agent':'Mozilla/5.0','Referer':'https://map.qq.com/'})
            return sid,json.loads(urllib.request.urlopen(r,timeout=25,context=ctx).read().decode('gbk'))
        except Exception:
            time.sleep(1.5+att*2)
    return sid,None

SEEDS=['16131012130717101809100','16131012130720161240800']
CONC=4
# 断点续传
STATE=BASE+'/raw/_state.json'
recs={}; visited=set(); seen=set(SEEDS)
if os.path.exists(STATE) and os.path.getsize(STATE)>10:
    st=json.load(open(STATE,encoding='utf-8'))
    recs={r['svid']:r for r in st['recs']}
    visited=set(st['visited']); seen=set(st['seen'])|set(SEEDS)
    frontier=[s for s in st['frontier'] if s not in visited]
    print('RESUME from state: recs=%d frontier=%d'%(len(recs),len(frontier)),flush=True)
else:
    frontier=list(SEEDS)
t0=time.time(); errs=0; pause_until=0
def save():
    json.dump({'recs':list(recs.values()),'visited':list(visited),'seen':list(seen),'frontier':frontier},
        open(STATE,'w',encoding='utf-8'),ensure_ascii=False)
while frontier:
    now=time.time()
    if now<pause_until:
        time.sleep(5); continue
    batch=frontier[:60]; frontier=frontier[60:]
    batch=[s for s in dict.fromkeys(batch) if s not in visited]
    if not batch: continue
    with ThreadPoolExecutor(max_workers=CONC) as ex:
        results=list(ex.map(fetch,batch))
    fails=sum(1 for _,d in results if d is None)
    for sid,d in results:
        visited.add(sid)
        if not d: errs+=1; continue
        det=d.get('detail') or {}; bb=det.get('basic') or {}; a=det.get('addr') or {}
        if not bb.get('svid'): continue
        lng,lat=a.get('x_lng'),a.get('y_lat')
        if lng is None and bb.get('x'): lng,lat=merc2ll(bb['x'],bb['y'])
        if not (lng and in_mohe(lng,lat)): continue
        recs[sid]={'svid':sid,'lng':lng,'lat':lat,'dir':bb.get('dir'),'rdid':bb.get('rdid'),
                   'addr':bb.get('append_addr'),'sno':bb.get('sno'),'source':bb.get('source'),
                   'level0':bb.get('level0'),'tile_width':bb.get('tile_width'),
                   'entrances':(det.get('region') or {}).get('entrances') or []}
        for s in (det.get('all_scenes') or []):
            ns=s.get('svid')
            if not ns or ns in seen or ns in visited: continue
            try: nlng,nlat=merc2ll(s['x'],s['y'])
            except Exception: continue
            if not in_mohe(nlng,nlat): continue
            seen.add(ns); frontier.append(ns)
    # 风控检测
    if fails>len(batch)*0.3 and len(batch)>=8:
        pause_until=time.time()+PAUSE
        print('!! rate-limited (%d/%d fails) -> pause %ds'%(fails,len(batch),PAUSE),flush=True)
    if len(visited)%300<len(batch):
        save()
        print('  visited=%d inMohe=%d frontier=%d errs=%d %.0fs'%(len(visited),len(recs),len(frontier),errs,time.time()-t0),flush=True)
save()
print('DONE visited=%d recs=%d errs=%d %.1fs'%(len(visited),len(recs),errs,time.time()-t0),flush=True)
import collections
print('top addrs:',collections.Counter(r['addr'] for r in recs.values()).most_common(12),flush=True)
lngs=[r['lng'] for r in recs.values()]; lats=[r['lat'] for r in recs.values()]
print('bbox lng %.5f~%.5f lat %.5f~%.5f'%(min(lngs),max(lngs),min(lats),max(lats)),flush=True)
out=BASE+'/raw/_mohe_inside.json'
json.dump(list(recs.values()),open(out,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
print('SAVED %s (%d recs)'%(out,len(recs)),flush=True)
