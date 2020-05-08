import os
from threading import Thread
from subprocess import Popen, PIPE
from time import sleep
from select import select


class SpecialRunner:
    """
    This class provides the interface to run special job types like
    CWL, WDL and HPC.

    """

    def __init__(self, config, job_id, logger=None):
        """
        Inputs: config dictionary, Job ID, and optional logger
        """
        self.config = config
        self.top_job_id = job_id
        self.logger = logger
        self.token = config['token']
        self.workdir = config.get('workdir', '/mnt/awe/condor')
        self.shareddir = os.path.join(self.workdir, 'workdir/tmp')
        self.containers = []
        self.threads = []
        self.allowed_types = ['slurm']

    _POLL = 0.1
    _POLL2 = 0.1

    def run(self, config, data, job_id, callback=None, fin_q=[]):
        # TODO:
        # initialize working space
        # check job type against an allow list
        # submit the job and map the batch jobb to the job id
        # start a thread to monitor progress
        (module, method) = data['method'].split('.')

        if module != 'special':
            err = "Attempting to run the wrong type of module. "
            err += "The module should be 'special'"
            raise ValueError(err)

        if method not in self.allowed_types:
            raise ValueError("Invalid special method type")

        return self._batch_submit(method, config, data, job_id, fin_q)

    def _check_batch_job(self, check, slurm_jobid):
        cmd = [check, slurm_jobid]
        proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
        stdout, stderr = proc.communicate()
        return stdout.decode('utf-8').rstrip()

    def _watch_batch(self, stype, job_id, slurm_jobid,
                     outfile, errfile, queues):
        self.logger.log("Watching Slurm Job ID %s" % (slurm_jobid))
        check = '%s_checkjob' % (stype)
        cont = True
        started = False
        # Wait for job to start out output file to appear
        while cont:
            state = self._check_batch_job(check, slurm_jobid)
            if state == 'Running':
                self.logger.log("Running")
                started = True
            elif state == "Pending":
                self.logger.log("Pending")
            elif state == "Finished":
                cont = False
                self.logger.log("F")

            if started and os.path.exists(outfile):
                cont = False

            sleep(self._POLL)

        # Tail output
        rlist = []
        stdout = None
        stderr = None
        if os.path.exists(outfile):
            stdout = open(outfile)
            rlist.append(stdout)
        else:
            self.logger.error("No output file generated")
        if os.path.exists(errfile):
            stderr = open(errfile)
            rlist.append(stderr)
        else:
            self.logger.error("No error file generated")

        cont = True
        if len(rlist) == 0:
            cont = False
        while cont:
            state = self._check_batch_job(check, slurm_jobid)
            if state != "Running":
                cont = False
            r, w, e = select(rlist, [], [], 10)
            for f in r:
                for line in f:
                    if f == stdout and self.logger:
                        self.logger.log(line)
                    elif f == stderr and self.logger:
                        self.logger.error(line)
            sleep(self._POLL2)
        res = {'result': [{'exit_status': 0}]}
        for q in queues:
            q.put(['finished_special', job_id, res])

    def _batch_submit(self, stype, config, data, job_id, fin_q):
        """
        This subbmits the job to the batch system and starts
        a thread to monitor the progress.

        The assumptions are there is a submit script and the
        batch system will return a job id and log output to
        a specified file.
        """
        params = data['params'][0]
        submit = '%s_submit' % (stype)
        if 'submit_script' not in params:
            raise ValueError("Missing submit script")
        os.chdir(self.shareddir)
        scr = params['submit_script']
        if not os.path.exists(scr):
            raise OSError("Submit script not found at %s" % (scr))
        outfile = '%s.out' % (job_id)
        errfile = '%s.err' % (job_id)
        cmd = [submit, scr, outfile, errfile]
        proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
        stdout, stderr = proc.communicate()
        slurm_jobid = stdout.decode('utf-8').rstrip()
        out = Thread(target=self._watch_batch, args=[stype, job_id,
                                                     slurm_jobid,
                                                     outfile, errfile,
                                                     fin_q])
        self.threads.append(out)
        out.start()
        self.containers.append(proc)
        return proc
