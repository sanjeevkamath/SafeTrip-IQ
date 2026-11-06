import copy
import unittest
from scripts.check_refresh_activation import verify_run
from scripts.check_production_health import valid_health


class OperationsTests(unittest.TestCase):
    def test_refresh_only_failed_fork_and_unverified_runs_cannot_enable_scheduling(self):
        run={'event':'workflow_dispatch','head_branch':'main','path':'.github/workflows/refresh-advisories.yml',
             'status':'completed','conclusion':'success','repository':{'full_name':'owner/repo'}}
        jobs={'jobs':[{'name':'refresh','conclusion':'success'},{'name':'publish','conclusion':'success',
            'steps':[{'name':'Independently read back outputs and verify preserved model inputs','conclusion':'success'}]}]}
        verify_run(run,jobs,'owner/repo')
        for field,value in [('event','schedule'),('head_branch','other'),('conclusion','failure'),
                            ('repository',{'full_name':'fork/repo'})]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                verify_run({**run,field:value},jobs,'owner/repo')
        for change in ['skipped','failed','unverified']:
            bad=copy.deepcopy(jobs)
            if change=='unverified':bad['jobs'][1]['steps']=[]
            else:bad['jobs'][1]['conclusion']=change
            with self.subTest(change=change), self.assertRaises(ValueError):verify_run(run,bad,'owner/repo')

    def test_http_success_without_fresh_source_and_score_evidence_is_insufficient(self):
        data={'healthy':True,'refresh_threshold_hours':216,
              'sources':{s:{'fresh':True} for s in ['us_state','uk_fcdo']},'publication':{'fresh':True}}
        self.assertTrue(valid_health(data))
        for value in [{}, {'healthy':True}, {**data,'sources':{'us_state':{'fresh':True}}},
                      {**data,'publication':{'fresh':False}}, {**data,'refresh_threshold_hours':48}]:
            self.assertFalse(valid_health(value))


if __name__=='__main__':unittest.main()
