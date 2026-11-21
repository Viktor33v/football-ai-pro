import unittest
from datetime import datetime,timezone,timedelta
from reliability26 import wilson_interval,calibration_summary,reliability

class Reliability26Tests(unittest.TestCase):
    def test_wilson(self):
        lo,hi=wilson_interval(50,100)
        self.assertAlmostEqual(lo,.4038,places=3)
        self.assertAlmostEqual(hi,.5962,places=3)
        self.assertIsNone(wilson_interval(0,0))
        self.assertIsNone(wilson_interval(11,10))
    def test_calibration(self):
        records=[[.65,1]]*65+[[.65,0]]*35
        s=calibration_summary(records,60,80)
        self.assertEqual((s["n"],s["wins"]),(100,65))
        self.assertAlmostEqual(s["gap"],0)
        self.assertTrue(s["low"]<.65<s["high"])
    def test_excludes_out_of_range_and_invalid(self):
        s=calibration_summary([[.9,1],[.65,1],[float("nan"),1],[".65",1],[.65,2]],60,80)
        self.assertEqual(s["n"],1)
        self.assertFalse(s["sufficient"])
    def test_reliability(self):
        s=calibration_summary([[.65,1]]*195+[[.65,0]]*105,60,80)
        good=reliability(s,{"n":1802,"model":.243,"baseline":.244},[20,20])
        self.assertIsInstance(good["score"],int)
        self.assertIn("🟢",good["status"])
        bad=reliability(s,{"n":1802,"model":.25,"baseline":.24},[20,20])
        self.assertIn("🔴",bad["status"])
        self.assertIsNone(reliability(s,{"n":50},[20,20])["score"])
        self.assertIsNone(reliability(s,{"n":1802,"model":.2,"baseline":.3},[2,20])["score"])
    def test_stale(self):
        s=calibration_summary([[.65,1]]*195+[[.65,0]]*105,60,80)
        now=datetime.now(timezone.utc)
        result=reliability(s,{"n":1802,"model":.2,"baseline":.3},[20,20],(now-timedelta(days=3)).isoformat(),now)
        self.assertIsNone(result["score"])
    def test_no_data(self):
        self.assertIsNone(reliability({"sufficient":False},{"n":1000,"model":.2,"baseline":.3},[20,20])["score"])

if __name__=="__main__":
    unittest.main()
