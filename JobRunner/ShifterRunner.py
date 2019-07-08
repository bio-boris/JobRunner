import docker
import os
import json
from threading import Thread
from time import time as _time
from time import sleep as _sleep
from subprocess import Popen, PIPE
import sys
from select import select


class ShifterRunner:
    """
    This class provides the container interface for Docker.

    """

    def __init__(self, logger=None):
        """
        Inputs: config dictionary, Job ID, and optional logger
        """
        self.logger = logger
        self.containers = []
        self.threads = []

    def _readio(self, p, job_id, queues):
        cont = True
        last = False
        while cont:
            rlist = [p.stdout, p.stderr]
            x = select(rlist, [], [], 1)[0]
            for f in x:
                if f == p.stderr:
                    error = True
                else:
                    error = False
                l = f.readline().decode('utf-8')
                if len(l) > 0:
                    self.logger.log_lines([{'line': l, 'error': error}])
            if last:
                cont = False
            if p.poll() is not None:
                last = True
        for q in queues:
            q.put(['finished', job_id, None])

    def get_image(self, image):
        # Do a shifterimg images
        lookcmd = ['shifterimg', 'lookup', image]
        proc = Popen(lookcmd, stdout=PIPE, stderr=PIPE)
        stdout, stderr = proc.communicate()
        id = stdout.decode('utf-8').rsplit()
        if id == '':
            cmd = ['shifterimg', 'pull', image]
            proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
            stdout, stderr = proc.communicate()
            proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
            stdout, stderr = proc.communicate()
            id = stdout.decode('utf-8').rsplit()

        return id

    def run(self, job_id, image, env, vols, labels, subjob, queues):
        cmd = [
            'shifter',
            '--image=%s' % (image)
            ]
        # TODO: Do somehting with the labels
        newenv = os.environ
        for e in env.keys():
            newenv[e] = env[e]
        proc = Popen(cmd, bufsize=0, stdout=PIPE, stderr=PIPE, env=newenv)
        out = Thread(target=self._readio, args=[proc, job_id, queues])
        self.threads.append(out)
        out.start()
        self.containers.append(proc)
        if self.logger:
            self.logger.flush_logs()
        return proc

    def remove(self, c):
        # TODO
        pass
