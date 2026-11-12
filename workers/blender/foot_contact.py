"""Contact proxies and a bounded correction envelope; no rig assumptions here."""
import math

def stance_pairs(samples,name,fps,height_band=.045,vertical_speed=.16):
    minimum=min(p[name][2] for p in samples)
    return [max(a[name][2],b[name][2])<=minimum+height_band and abs(b[name][2]-a[name][2])*fps<=vertical_speed for a,b in zip(samples,samples[1:])]

def intervals(mask):
    result=[];start=None
    for i,value in enumerate(mask+[False]):
        if value and start is None:start=i
        if not value and start is not None:
            if i-start>=3:result.append((start,i))
            start=None
    merged=[]
    for start,end in result:
        if merged and start-merged[-1][1]<=3:merged[-1]=(merged[-1][0],end)
        else:merged.append((start,end))
    return merged

def statistics(samples,masks,fps):
    speeds=[]
    for name,mask in masks.items():
        for i,contact in enumerate(mask):
            if contact:speeds.append(math.hypot(samples[i+1][name][0]-samples[i][name][0],samples[i+1][name][1]-samples[i][name][1])*fps)
    return {'meanMetersPerSecond':sum(speeds)/len(speeds) if speeds else None,'maxMetersPerSecond':max(speeds) if speeds else None,'contactPairs':len(speeds)}

def release_weight(offset,duration):
    t=max(0,min(1,offset/duration));return 1-t*t*(3-2*t)
