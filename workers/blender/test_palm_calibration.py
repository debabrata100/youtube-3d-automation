"""Reject the previous dorsal-facing wrist pose using an independently wrong fixture."""
import bpy,json,sys
from copy import deepcopy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from forward_wave import orient_palm
from wave_diagnostics import measure
job=Path(sys.argv[sys.argv.index('--')+1]);execution=json.loads((job/'scene-plan.json').read_text())
config=json.loads((Path(__file__).resolve().parents[2]/'assets/characters/wolf-warrior/animation-config.json').read_text())
for entry in execution['controllers']:
    name=entry['id'];rig=bpy.data.objects['Character.'+name+'.rig'];body=bpy.data.objects['Character.'+name+'.body']
    strip=next(s for t in rig.animation_data.nla_tracks if t.name.startswith('Controller.Wave') for s in t.strips)
    original=strip.action;slot=strip.action_slot;wrong=original.copy()
    try:
        strip.action=wrong;strip.action_slot=wrong.slots[0]
        dorsal=deepcopy(config);dorsal['forwardWave']['palmNormalLocal']=[0,0,-1]
        orient_palm(rig,wrong,wrong.slots[0],dorsal,entry['controller']['performance']['wave'],strip.frame_start,strip.frame_end)
        result=measure(rig,body,int(strip.frame_start),int(strip.frame_end),enforce=False)
        assert not result['passed'] and any('palm' in f for f in result['failures'])
        assert all(s['palmForwardAlignment']<0 for s in result['samples'] if s['activeGreeting'])
    finally:
        strip.action=original;strip.action_slot=slot;bpy.data.actions.remove(wrong)
print('REVERSED_PALM_FIXTURE_REJECTED_FOR_BOTH_ACTORS')
