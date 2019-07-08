

import sys
import os
from clients.NarrativeJobServiceClient import NarrativeJobService


# TODO: Add a buffer  we may need some flush thread too.

class Logger(object):

    def __init__(self, njs_url, job_id, njs=None):
        self.njs_url = njs_url
        self.threshold = 5
        self.logs_cache = []
        if njs is None:
            self.njs = NarrativeJobService(self.njs_url)
        else:
            self.njs = njs
        self.job_id = job_id
        self.debug = os.environ.get('DEBUG_RUNNER', None)
        print("Logger initialized for %s" % (job_id))

    def flush_logs(self):
        self.njs.add_job_logs(self.job_id, self.logs_cache)
        self.logs_cache = []

    def _log_line(self, line):
        self.logs_cache.append(line)
        if len(self.logs_cache) > self.threshold :
            self.flush_logs()

    def log_lines(self, lines):
        if self.debug:
            for line in lines:
                if line['is_error']:
                    sys.stderr.write(line+'\n')
                else:
                    print(line['line'])
        self.njs.add_job_logs(self.job_id, lines)

    def log(self, line):
        if self.debug:
            print(line, flush=True)
        self._log_line({'line': line, 'is_error': 0})

    def error(self, line):
        if self.debug:
            print(line, flush=True)
        self._log_line({'line': line, 'is_error': 1})
