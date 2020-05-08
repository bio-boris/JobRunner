
# -*- coding: utf-8 -*-
import os
import unittest
from unittest.mock import patch
from JobRunner.DockerRunner import DockerRunner
from mock import MagicMock
import json
from time import sleep as _sleep


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

class DockerRunnerTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pass

    def test_run(self):
        mlog = MockLogger()
        dr = DockerRunner(logger=mlog)
        inp = {
            'method': 'mock_app.bogus'
        }
        with open('/tmp/input.json', 'w') as f:
            f.write(json.dumps(inp))
        vols = {
            '/tmp': {'bind': '/kb/module/work', 'mode': 'rw'}
        }
        of = '/tmp/output.json'
        if os.path.exists(of):
            os.remove(of)
        c = dr.run('1234', 'mock_app', {}, vols, {}, [])
        _sleep(2)
        self.assertTrue(os.path.exists(of))
        self.assertEquals(len(mlog.all), 2)
        dr.remove(c)

    def test_sort(self):
        dr = DockerRunner()
        sout = u'2019-07-08T23:21:32.508696500Z 1\n'
        sout += u'2019-07-08T23:21:32.508896500Z 4\n'
        serr = u'2019-07-08T23:21:32.508797700Z 3\n'
        serr += u'2019-07-08T23:21:32.508797600Z 2\n'
        lines = dr._sort_lines_by_time(sout.encode('utf-8'), serr.encode('utf-8'))
        self.assertEquals(lines[0]['line'],'1')
        self.assertEquals(lines[1]['line'],'2')
        self.assertEquals(lines[2]['line'],'3')
        self.assertEquals(lines[3]['line'],'4')
        self.assertEquals(lines[1]['is_error'],1)
