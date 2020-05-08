# -*- coding: utf-8 -*-
import os
import unittest

from JobRunner.SpecialRunner import SpecialRunner
from nose.plugins.attrib import attr
from queue import Queue
from time import sleep


class MockLogger(object):
    def __init__(self):
        self.lines = []
        self.errors = []
        self.all = []

    def log_lines(self, lines):
        self.all.extend(lines)

    def log(self, line):
        self.lines.append(line)
        self.all.append([line, 0])

    def error(self, line):
        self.errors.append(line)
        self.all.append([line, 1])


class SpecialRunnerTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.logger = MockLogger()
        cls.config = {
            'token': 'bogus',
            'workdir': '/tmp/'
        }
        cls.sr = SpecialRunner(cls.config, '123', logger=cls.logger)

    def test_run(self):
        config = {}
        data = {
            'method': 'special.slurm',
            'params': [{'submit_script': 'submit.sl'}]
        }
        job_id = '1234'
        if not os.path.exists('/tmp/workdir/tmp'):
            os.makedirs('/tmp/workdir/tmp/')
        with open('/tmp/workdir/tmp/submit.sl', 'w') as f:
            f.write('#!/bin/sh')
            f.write('echo Hello')
        q = Queue()
        self.sr.run(config, data, job_id, fin_q=[q])
        result = q.get(timeout=10)
        self.assertEquals(result[0], 'finished_special')
        self.assertEquals(len(result), 3)
        self.assertIn(['line1\n', 0], self.logger.all)
        self.assertIn(['line2\n', 1], self.logger.all)
        self.assertIn(['line3\n', 0], self.logger.all)
