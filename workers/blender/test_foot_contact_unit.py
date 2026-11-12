import unittest
from foot_contact import stance_pairs,intervals,statistics,release_weight
class ContactTests(unittest.TestCase):
    def test_detection_uses_velocity_and_height(self):
        samples=[{'f':[i*.02,0,z]} for i,z in enumerate([0,0,.03,.03,0])]
        mask=stance_pairs(samples,'f',24)
        self.assertEqual(mask,[True,False,True,False])
    def test_intervals_and_release(self):
        self.assertEqual(intervals([True]*5+[False]+[True]*5),[(0,11)])
        self.assertEqual(release_weight(0,12),1);self.assertEqual(release_weight(12,12),0)
        weights=[release_weight(i,12) for i in range(13)];self.assertEqual(weights,sorted(weights,reverse=True))
    def test_statistics_keep_same_masks(self):
        a=[{'f':[i*.02,0,0]} for i in range(6)];b=[{'f':[0,0,0]} for i in range(6)];mask={'f':[True]*5}
        self.assertAlmostEqual(statistics(a,mask,24)['meanMetersPerSecond'],.48)
        self.assertEqual(statistics(b,mask,24)['meanMetersPerSecond'],0)
        self.assertEqual(statistics(a,mask,24)['contactPairs'],statistics(b,mask,24)['contactPairs'])
if __name__=='__main__':unittest.main()
