import unittest
from performance_math import smoother,release,safety_envelope,percentile,foot_metrics
class PerformanceMathTests(unittest.TestCase):
 def test_continuous_release_and_endpoints(self):
  self.assertEqual(release(0,24),1);self.assertEqual(release(24,24),0)
  values=[release(i/10,24) for i in range(241)];self.assertEqual(values,sorted(values,reverse=True))
  self.assertLess(abs((release(.001,24)-1)/.001),1e-5)
  self.assertLess(abs(release(23.999,24)/.001),1e-5)
 def test_safety_weights_are_deterministic_bounded_and_rate_limited(self):
  allowed=[1]*12+[.2]+[1]*12;a=safety_envelope(allowed)
  self.assertEqual(a,safety_envelope(allowed));self.assertTrue(all(0<=x<=limit for x,limit in zip(a,allowed)))
  self.assertLessEqual(max(abs(y-x) for x,y in zip(a,a[1:])),.04500001)
 def test_percentiles_and_fixed_masks(self):
  self.assertAlmostEqual(percentile([0,1,2,3,4]),3.8)
  samples=[{'Foot.L':[i*.01,0,0]} for i in range(6)];masks={'Foot.L':[True]*5}
  m=foot_metrics(samples,masks);self.assertAlmostEqual(m['meanStanceVelocity'],.24);self.assertEqual(m['stancePairs'],5)
if __name__=='__main__':unittest.main()
