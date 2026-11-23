import unittest
from datetime import datetime,timezone,timedelta
from forward28 import archive,settle,report

class Forward28Tests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,21,12,tzinfo=timezone.utc)
        self.k=(self.now+timedelta(days=1)).isoformat()
        self.rows=[dict(fixture_id=123,market="Обе забьют",group="goals",p=.65,home="A",away="B",kickoff=self.k)]
    def test_archive_immutable_and_future_only(self):
        j=archive({},self.rows,self.now)
        self.assertEqual(len(j),1)
        self.rows[0]["p"]=.99
        archive(j,self.rows,self.now)
        self.assertEqual(next(iter(j.values()))["p"],.65)
        archive(j,[dict(self.rows[0],fixture_id=124,kickoff=self.now.isoformat())],self.now)
        self.assertEqual(len(j),1)
    def test_settle_verified_and_idempotent(self):
        j=archive({},self.rows,self.now)
        future=self.now+timedelta(days=2)
        result={"123":{"status":"FINISHED","utcDate":self.k,"score":{"duration":"REGULAR","fullTime":{"home":2,"away":1},"halfTime":{"home":1,"away":0}}}}
        self.assertEqual(settle(j,result,future),1)
        self.assertEqual(next(iter(j.values()))["result"],1)
        self.assertEqual(settle(j,result,future),0)
        self.assertIn("1/1",report(j,future))
    def test_reject_unverified_and_post_kickoff(self):
        j=archive({},self.rows,self.now)
        future=self.now+timedelta(days=2)
        result={"123":{"status":"TIMED","utcDate":self.k,"score":{"fullTime":{"home":2,"away":1},"halfTime":{"home":1,"away":0}}}}
        self.assertEqual(settle(j,result,future),0)
        result["123"]["status"]="FINISHED"
        next(iter(j.values()))["created"]=(self.now+timedelta(days=1,hours=1)).isoformat()
        self.assertEqual(settle(j,result,future),0)
    def test_forward_calibration_by_market(self):
        now=self.now
        journal={}
        for i in range(40):
            journal[str(i)]={"market":"Обе забьют","kickoff":(now-timedelta(days=1)).isoformat(),
                "p":0.65,"result":int(i<24)}
        out=report(journal,now)
        self.assertIn("Калибровка: средний прогноз 65.0%, факт 60.0%",out)
        self.assertIn("60%–70%: 40 прогнозов",out)
        self.assertNotIn("80%–100%: 0 прогнозов",out)

    def test_half_second_half(self):
        rows=[dict(self.rows[0],market="ТБ 0.5 2Т")]
        j=archive({},rows,self.now)
        result={"123":{"status":"FINISHED","utcDate":self.k,"score":{"duration":"REGULAR","fullTime":{"home":1,"away":0},"halfTime":{"home":1,"away":0}}}}
        settle(j,result,self.now+timedelta(days=2))
        self.assertEqual(next(iter(j.values()))["result"],0)

if __name__=="__main__":unittest.main()
