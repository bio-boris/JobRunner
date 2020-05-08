# -*- coding: utf-8 -*-
import os
import unittest
from unittest.mock import patch
from copy import deepcopy
from queue import Queue

from JobRunner.MethodRunner import MethodRunner
from JobRunner.logger import Logger
from .mock_data import NJS_JOB_PARAMS, CATALOG_GET_MODULE_VERSION,\
    CATALOG_GET_SECURE_CONFIG_PARAMS


class MockLogger(object):
    def __init__(self):
        self.lines = []
        self.errors = []

    def log_lines(self, lines):
        self.lines.append(lines)

    def log(self, line):
        self.lines.append(line)

    def error(self, line):
        self.errors.append(line)


class MockRunner(object):
    def __init__(self):
        self.env = None

    def get_image(self, image):
        return '1234'

    def run(self, job_id, image, env, vols, labels, qs):
        self.env = env


class MethodRunnerTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.token = os.environ.get('KB_AUTH_TOKEN', '')
        # WARNING: don't call any logging metholsds on the context object,
        # it'll result in a NoneType error
        cls.cfg = {
            'catalog-service-url': 'http://localhost',
            'token': cls.token,
            'admin_token': os.environ.get('KB_ADMIN_AUTH_TOKEN'),
            'workdir': '/tmp/mr'
        }
        cls.logger = MockLogger()
        cls.mr = MethodRunner(cls.cfg, '1234', logger=cls.logger)
        base = 'https://ci.kbase.us/services/'
        cls.conf = {
            'kbase.endpoint': base,
            'workspace.srv.url': base,
            'shock.url': base,
            'handle.url': base,
            'auth-service-url': base,
            'auth-service-url-allow-insecure': True,
            'scratch': '/kb/module/work/tmp',
            'user': 'mrbogus'
        }

    def test_run(self):
        mr = MethodRunner(self.cfg, '1234', logger=MockLogger())
        module_info = deepcopy(CATALOG_GET_MODULE_VERSION)
        module_info['docker_img_name'] = 'mock_app:latest'
        try:
            os.makedirs('/tmp/mr/')
        except:
            pass
        q = Queue()
        action = mr.run(self.conf, module_info, NJS_JOB_PARAMS[0], '1234',
                        fin_q=q)
        self.assertIn('name', action)
        out = q.get(timeout=10)
        self.assertEqual(out[0], 'finished')
        self.assertEqual('1234', out[1])

    def test_no_output(self):
        mr = MethodRunner(self.cfg, '1234', logger=MockLogger())
        module_info = deepcopy(CATALOG_GET_MODULE_VERSION)
        module_info['docker_img_name'] = 'mock_app:latest'
        try:
            os.makedirs('/tmp/mr/')
        except:
            pass
        if os.path.exists('/tmp/mr/workdir/output.json'):
            os.remove('/tmp/mr/workdir/output.json')
        q = Queue()
        params = deepcopy(NJS_JOB_PARAMS[0])
        params['method'] = 'echo_test.noout'
        action = mr.run(self.conf, module_info, params, '1234', fin_q=q)
        self.assertIn('name', action)
        out = q.get(timeout=10)
        self.assertEqual(out[0], 'finished')
        self.assertEqual('1234', out[1])
        result = mr.get_output('1234', subjob=False)
        self.assertIn('error', result)
        self.assertEquals(result['error']['name'], 'Output not found')

    def test_too_much_output(self):
        mr = MethodRunner(self.cfg, '1234', logger=MockLogger())
        module_info = deepcopy(CATALOG_GET_MODULE_VERSION)
        module_info['docker_img_name'] = 'mock_app:latest'
        try:
            os.makedirs('/tmp/mr/')
        except:
            pass
        if os.path.exists('/tmp/mr/workdir/output.json'):
            os.remove('/tmp/mr/workdir/output.json')
        q = Queue()
        params = deepcopy(NJS_JOB_PARAMS[0])
        params['method'] = 'echo_test.bogus'
        action = mr.run(self.conf, module_info, params, '1234', fin_q=q)
        self.assertIn('name', action)
        out = q.get(timeout=10)
        self.assertEqual(out[0], 'finished')
        self.assertEqual('1234', out[1])
        result = mr.get_output('1234', subjob=False, max_size=10)
        self.assertIn('error', result)
        err = 'Too much output from a method'
        self.assertEquals(result['error']['name'], err)

    def test_secure_params(self):
        mr = MethodRunner(self.cfg, '1234', logger=MockLogger())
        module_info = deepcopy(CATALOG_GET_MODULE_VERSION)
        module_info['docker_img_name'] = 'mock_app:latest'
        module_info['secure_config_params'] = CATALOG_GET_SECURE_CONFIG_PARAMS
        try:
            os.makedirs('/tmp/mr/')
        except:
            pass
        if os.path.exists('/tmp/mr/workdir/output.json'):
            os.remove('/tmp/mr/workdir/output.json')
        q = Queue()
        params = deepcopy(NJS_JOB_PARAMS[0])
        params['method'] = 'echo_test.bogus'
        mockrunner = MockRunner()
        mr.runner = mockrunner
        action = mr.run(self.conf, module_info, params, '1234', fin_q=q)
        self.assertIn('KBASE_SECURE_CONFIG_PARAM_param1', mockrunner.env)

    def test_bad_method(self):
        mr = MethodRunner(self.cfg, '1234', logger=MockLogger())
        module_info = deepcopy(CATALOG_GET_MODULE_VERSION)
        module_info['docker_img_name'] = 'mock_app:latest'
        try:
            os.makedirs('/tmp/mr/')
        except:
            pass
        if os.path.exists('/tmp/mr/workdir/output.json'):
            os.remove('/tmp/mr/workdir/output.json')
        q = Queue()
        params = deepcopy(NJS_JOB_PARAMS[0])
        params['method'] = 'echo_test.badmethod'
        action = mr.run(self.conf, module_info, params, '1234', fin_q=q)
        self.assertIn('name', action)
        out = q.get(timeout=10)
        self.assertEqual(out[0], 'finished')
        self.assertEqual('1234', out[1])
        result = mr.get_output('1234', subjob=False)
        self.assertIn('error', result)
        self.assertEquals(result['error']['name'], 'Method not found')

    def test_bad_runtime(self):
        cfg = deepcopy(self.cfg)
        cfg['runtime'] = 'bogus'
        with self.assertRaises(OSError):
            MethodRunner(cfg, '1234', logger=MockLogger())
