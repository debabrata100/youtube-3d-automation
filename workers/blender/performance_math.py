"""Deterministic continuous envelopes, with no bpy dependency."""
import math

def smoother(t):
    t=max(0.,min(1.,t));return t*t*t*(t*(6*t-15)+10)
def release(t,duration):return 1-smoother(t/duration)
def safety_envelope(allowed,max_step=.045):
    values=list(allowed)
    for i in range(1,len(values)):values[i]=min(values[i],values[i-1]+max_step)
    for i in range(len(values)-2,-1,-1):values[i]=min(values[i],values[i+1]+max_step)
    return values

def percentile(values,p=.95):
    values=sorted(values)
    if not values:return None
    index=(len(values)-1)*p;a=int(index);b=min(a+1,len(values)-1)
    return values[a]+(values[b]-values[a])*(index-a)
def foot_metrics(samples,masks,fps=24):
    contact=[];swing=[];vertical=[];all_steps=[]
    for name,mask in masks.items():
        for i,(a,b) in enumerate(zip(samples,samples[1:])):
            dx=b[name][0]-a[name][0];dy=b[name][1]-a[name][1];dz=b[name][2]-a[name][2]
            distance=math.sqrt(dx*dx+dy*dy+dz*dz);vertical.append(abs(dz));all_steps.append(distance)
            if i<len(mask) and mask[i]:contact.append(math.hypot(dx,dy)*fps)
            else:swing.append(distance)
    return {'meanStanceVelocity':sum(contact)/len(contact) if contact else None,'p95StanceVelocity':percentile(contact),'maxStanceVelocity':max(contact) if contact else None,'maxSwingReleaseStepMeters':max(swing) if swing else None,'maxFootStepMeters':max(all_steps) if all_steps else None,'maxVerticalStepMeters':max(vertical) if vertical else None,'stancePairs':len(contact)}
