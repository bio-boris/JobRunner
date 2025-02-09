# -*- coding: utf-8 -*-
import os
import unittest
from unittest.mock import patch
from mock import MagicMock

from JobRunner.JobRunner import JobRunner
from nose.plugins.attrib import attr
from copy import deepcopy
from .mock_data import CATALOG_GET_MODULE_VERSION, NJS_JOB_PARAMS, \
        CATALOG_LIST_VOLUME_MOUNTS


class JobRunnerTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.token = os.environ.get('KB_AUTH_TOKEN', '')
        cls.admin_token = os.environ.get('KB_ADMIN_AUTH_TOKEN', 'bogus')
        cls.cfg = {}
        base = 'https://ci.kbase.us/services/'
        if 'TEST_URL' in os.environ:
            base = "http://%s/services/" % (os.environ['TEST_URL'])
        cls.njs_url = base + 'njs_wrapper'
        cls.jobid = '1234'
        cls.workdir = '/tmp/jr/'
        cls.cfg['token'] = cls.token
        cls.config = {
            'catalog-service-url': base + 'catalog',
            'auth-service-url': base + 'auth/api/legacy/KBase/Sessions/Login',
            'auth2-url': base + 'auth/api/V2/token',
            'workdir': '/tmp/jr'
            }
        if not os.path.exists('/tmp/jr'):
            os.mkdir('/tmp/jr')
        if 'KB_ADMIN_AUTH_TOKEN' not in os.environ:
            os.environ['KB_ADMIN_AUTH_TOKEN'] = 'bogus'

    def _cleanup(self, job):
        d = os.path.join(self.workdir, job)
        if os.path.exists(d):
            for fn in ['config.properties', 'input.json', 'output.json',
                       'token']:
                if os.path.exists(os.path.join(d, fn)):
                    os.unlink(os.path.join(d, fn))
            os.rmdir(d)

    @attr('offline')
    @patch('JobRunner.JobRunner.KBaseAuth', autospec=True)
    @patch('JobRunner.JobRunner.NJS', autospec=True)
    def test_run_sub(self, mock_njs, mock_auth):
        self._cleanup(self.jobid)
        params = deepcopy(NJS_JOB_PARAMS)
        params[0]['method'] = 'RunTester.run_RunTester'
        params[0]['params'] = [{'depth': 3, 'size': 1000, 'parallel': 5}]
        params[1]['auth-service-url'] = self.config['auth-service-url']
        params[1]['auth.service.url.v2'] = self.config['auth2-url']
        jr = JobRunner(self.config, self.njs_url, self.jobid, self.token,
                       self.admin_token)
        rv = deepcopy(CATALOG_GET_MODULE_VERSION)
        rv['docker_img_name'] = 'test/runtester:latest'
        jr.cc.catalog.get_module_version = MagicMock(return_value=rv)
        jr.cc.catadmin.list_volume_mounts = MagicMock(return_value=[])
        jr.logger.njs.add_job_logs = MagicMock(return_value=rv)
        jr.njs.get_job_params.return_value = params
        jr.njs.check_job_canceled.return_value = {'finished': False}
        jr.auth.get_user.return_value = "bogus"
        out = jr.run()
        self.assertIn('result', out)
        self.assertNotIn('error', out)

    @attr('offline')
    @patch('JobRunner.JobRunner.KBaseAuth', autospec=True)
    @patch('JobRunner.JobRunner.NJS', autospec=True)
    def test_run(self, mock_njs, mock_auth):
        self._cleanup(self.jobid)
        params = deepcopy(NJS_JOB_PARAMS)
        params[0]['method'] = 'mock_app.bogus'
        params[0]['params'] = {'param1': 'value1'}
        jr = JobRunner(self.config, self.njs_url, self.jobid, self.token,
                       self.admin_token)
        rv = deepcopy(CATALOG_GET_MODULE_VERSION)
        rv['docker_img_name'] = 'mock_app:latest'
        # jr.mr.catalog.get_module_version = MagicMock(return_value=rv)
        # jr.mr.catadmin.list_volume_mounts = MagicMock(return_value=[])
        jr.cc.catalog.get_module_version = MagicMock(return_value=rv)
        jr.cc.catadmin.list_volume_mounts = MagicMock(return_value=[])
        jr.logger.njs.add_job_logs = MagicMock(return_value=rv)
        jr.njs.get_job_params.return_value = params
        jr.njs.check_job_canceled.return_value = {'finished': False}
        jr.auth.get_user.return_value = "bogus"
        out = jr.run()
        self.assertIn('result', out)
        self.assertNotIn('error', out)

    @attr('offline')
    @patch('JobRunner.JobRunner.KBaseAuth', autospec=True)
    @patch('JobRunner.JobRunner.NJS', autospec=True)
    def test_run_volume(self, mock_njs, mock_auth):
        self._cleanup(self.jobid)
        params = deepcopy(NJS_JOB_PARAMS)
        params[0]['method'] = 'mock_app.voltest'
        params[0]['params'] = {'param1': 'value1'}
        jr = JobRunner(self.config, self.njs_url, self.jobid, self.token,
                       self.admin_token)
        rv = deepcopy(CATALOG_GET_MODULE_VERSION)
        rv['docker_img_name'] = 'mock_app:latest'
        vols = deepcopy(CATALOG_LIST_VOLUME_MOUNTS)
        jr.cc.catalog.get_module_version = MagicMock(return_value=rv)
        jr.cc.catadmin.list_volume_mounts = MagicMock(return_value=vols)
        jr.logger.njs.add_job_logs = MagicMock(return_value=rv)
        jr.njs.get_job_params.return_value = params
        jr.njs.check_job_canceled.return_value = {'finished': False}
        jr.auth.get_user.return_value = "bogus"
        if not os.path.exists('/tmp/bogus'):
            os.mkdir('/tmp/bogus')
        with open('/tmp/bogus/input.fa', 'w') as f:
            f.write('>contig-50_0 length_64486 read_count_327041\n')
            f.write('GTCGTGCTGCTGCCGATCGACCGCGCCTATGCGATGTTGCCGGACGGCATCC\n')
        out = jr.run()
        self.assertIn('result', out)
        self.assertNotIn('error', out)

    @attr('offline')
    @patch('JobRunner.JobRunner.KBaseAuth', autospec=True)
    @patch('JobRunner.JobRunner.NJS', autospec=True)
    def test_cancel(self, mock_njs, mock_auth):
        self._cleanup(self.jobid)
        params = deepcopy(NJS_JOB_PARAMS)
        params[0]['method'] = 'RunTester.run_RunTester'
        params[0]['params'] = [{'depth': 3, 'size': 1000, 'parallel': 5}]
        jr = JobRunner(self.config, self.njs_url, self.jobid, self.token,
                       self.admin_token)
        rv = deepcopy(CATALOG_GET_MODULE_VERSION)
        rv['docker_img_name'] = 'test/runtester:latest'
        jr.cc.catalog.get_module_version = MagicMock(return_value=rv)
        jr.cc.catadmin.list_volume_mounts = MagicMock(return_value=[])
        jr.logger.njs.add_job_logs = MagicMock(return_value=rv)
        jr.njs.get_job_params.return_value = params
        nf = {'finished': False}
        jr.njs.check_job_canceled.side_effect = [nf, nf, nf, nf, nf,
                                                 {'finished': True}]
        jr.auth.get_user.return_value = "bogus"
        out = jr.run()
        self.assertIsNotNone(out)
        # Check that all containers are gone

    @attr('online')
    @patch('JobRunner.JobRunner.NJS', autospec=True)
    def test_run_online(self, mock_njs):
        self._cleanup(self.jobid)
        params = deepcopy(NJS_JOB_PARAMS)
        jr = JobRunner(self.config, self.njs_url, self.jobid, self.token,
                       self.admin_token)
        rv = deepcopy(CATALOG_GET_MODULE_VERSION)
        rv['docker_img_name'] = 'mock_app:latest'
        jr.logger.njs.add_job_logs = MagicMock(return_value=rv)
        jr.njs.check_job_canceled.return_value = {'finished': False}
        jr.njs.get_job_params.return_value = params
        out = jr.run()
        self.assertIn('result', out)
        self.assertNotIn('error', out)

    @patch('JobRunner.JobRunner.NJS', autospec=True)
    @patch('JobRunner.JobRunner.KBaseAuth', autospec=True)
    def test_token(self, mock_njs, mock_auth):
        self._cleanup(self.jobid)
        params = deepcopy(NJS_JOB_PARAMS)
        os.environ['KB_AUTH_TOKEN'] = 'bogus'
        jr = JobRunner(self.config, self.njs_url, self.jobid, self.token,
                       self.admin_token)
        jr.njs.check_job_canceled.return_value = {'finished': False}
        jr.njs.get_job_params.return_value = params
        jr.auth.get_user.side_effect = OSError()
        with self.assertRaises(Exception):
            jr.run()
