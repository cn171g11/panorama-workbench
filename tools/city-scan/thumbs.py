import json,ssl,os,time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
BASE='E:/Desktop/Github Tools/tencent-panorama-scan/mohe'
IMG=BASE+'/images'; os.makedirs(IMG,exist_ok=True)
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
def load_targets():
    pts=[]
    st=json.load(open(BASE+'/raw/_state.json',encoding='utf-8'))
    for r in st['recs']: pts.append({'svid':r['svid']})
    if os.path.exists(BASE+'/raw/_mohe_inside.json') and os.path.getsize(BASE+'/raw/_mohe_inside.json')>10:
        seen=set(p['svid'] for p in pts)
        for r in json.load(open(BASE+'/raw/_mohe_inside.json',encoding='utf-8')):
            if r['svid'] not in seen: pts.append({'svid':r['svid']})
    return pts
def fetch(p):
    svid=p['svid']; fp=os.path.join(IMG,svid+'.jpg')
    if os.path.exists(fp) and os.path.getsize(fp)>500: return ('skip',0)
    for att in range(3):
        try:
            time.sleep(0.08)
            r=urllib.request.Request('https://sv1.map.qq.com/thumb?from=web&svid=%s&level=0&x=0&y=0'%svid,
                headers={'User-Agent':'Mozilla/5.0','Referer':'https://map.qq.com/'})
            d=urllib.request.urlopen(r,timeout=25,context=ctx).read()
            if d[:2]==b'\xff\xd8' and len(d)>500:
                open(fp,'wb').write(d); return ('ok',len(d))
            return ('bad',len(d))
        except Exception:
            time.sleep(0.8+att*0.8)
    return ('err',0)
t0=time.time(); stats={'ok':0,'skip':0,'bad':0,'err':0}; total=0
pts=load_targets()
print('targets:',len(pts),flush=True)
batch=pts[:len(pts)]  # 本轮先下当前 state 里全部
with ThreadPoolExecutor(max_workers=10) as ex:
    for i,(st,n) in enumerate(ex.map(fetch,batch)):
        stats[st]+=1
        if st=='ok': total+=n
        if (i+1)%500==0:
            print('  %d/%d ok=%d skip=%d err=%d %.0fs'%(i+1,len(batch),stats['ok'],stats['skip'],stats['err'],time.time()-t0),flush=True)
print('DONE',stats,'new %.1f MB'%(total/1048576),'%.0fs'%(time.time()-t0),flush=True)
