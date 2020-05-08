import os
from time import sleep as _sleep
from time import time as _time
from .logger import Logger
from clients.NarrativeJobServiceClient import NarrativeJobService as NJS
from clients.authclient import KBaseAuth
from .MethodRunner import MethodRunner
from .SpecialRunner import SpecialRunner
from .callback_server import start_callback_server
from socket import gethostname
from multiprocessing import Process, Queue
from .provenance import Provenance
from queue import Empty
import socket
import signal
from .CatalogCache import CatalogCache
import requests


class JobRunner(object):
    """
    This class provides the mechanisms to launch a KBase job
    on a container runtime.  It handles starting the callback service
    to support subjobs and provenenace calls.
    """

    def __init__(self, config, njs_url, job_id, token, admin_token):
        """
        inputs: config dictionary, NJS URL, Job id, Token, Admin Token
        """
        self.njs = NJS(url=njs_url, timeout=60)
        self.logger = Logger(njs_url, job_id, njs=self.njs)
        self.token = token
        self.client_group = os.environ.get("AWE_CLIENTGROUP", "None")
        self.admin_token = admin_token
        self.config = self._init_config(config, job_id, njs_url)
        self.hostname = gethostname()
        self.auth = KBaseAuth(config.get('auth-service-url'))
        self.job_id = job_id
        self.workdir = config.get('workdir', '/mnt/awe/condor')
        self.jr_queue = Queue()
        self.callback_queue = Queue()
        self.prov = None
        self._init_callback_url()
        self.mr = MethodRunner(self.config, job_id, logger=self.logger)
        self.sr = SpecialRunner(self.config, job_id, logger=self.logger)
        self.cc = CatalogCache(config)
        self.max_task = config.get('max_tasks', 20)
        signal.signal(signal.SIGINT, self.shutdown)

    def _init_config(self, config, job_id, njs_url):
        """
        Initialize config dictionary
        """
        config['hostname'] = gethostname()
        config['job_id'] = job_id
        config['njs_url'] = njs_url
        config['cgroup'] = self._get_cgroup()
        token = self.token
        config['token'] = token
        config['admin_token'] = self.admin_token
        return config

    def _check_job_status(self):
        """
        returns True if the job is still okay to run.
        """
        try:
            status = self.njs.check_job_canceled({'job_id': self.job_id})
        except Exception:
            self.logger.error("Warning: Job cancel check failed.  Continuing")
            return True
        if status.get('finished', False):
            return False
        return True

    def _init_workdir(self):
        # Check to see for existence of /mnt/awe/condor
        if not os.path.exists(self.workdir):
            self.logger.error("Missing workdir")
            raise OSError("Missing Working Directory")

    def _get_cgroup(self):
        pid = os.getpid()
        cfile = "/proc/{}/cgroup".format(pid)
        if not os.path.exists(cfile):
            return None
        with open(cfile) as f:
            for line in f:
                if line.find('htcondor') > 0:
                    items = line.split(':')
                    if len(items) == 3:
                        return items[2]
        return "Unknown"

    def _submit_special(self, config, job_id, data):
        """
        Handler for methods such as CWL, WDL and HPC
        """
        (module, method) = data['method'].split('.')
        self.logger.log("Submit %s as a %s:%s job" % (job_id, module, method))

        self.sr.run(config, data, job_id,
                    callback=self.callback_url,
                    fin_q=[self.jr_queue])

    def _submit(self, config, job_id, data, subjob=True):
        (module, method) = data['method'].split('.')
        version = data.get('service_ver')
        module_info = self.cc.get_module_info(module, version)

        git_url = module_info['git_url']
        git_commit = module_info['git_commit_hash']
        if not module_info['cached']:
            fstr = 'Running module {}: url: {} commit: {}'
            self.logger.log(fstr.format(module, git_url, git_commit))
        else:
            version = module_info['version']
            f = 'WARNING: Module {} was already used once for this job. '
            f += 'Using cached version: url: {} '
            f += 'commit: {} version: {} release: release'
            self.logger.error(f.format(module, git_url, git_commit, version))

        vm = self.cc.get_volume_mounts(module, method, self.client_group)
        config['volume_mounts'] = vm
        action = self.mr.run(config, module_info, data, job_id,
                             callback=self.callback_url, subjob=subjob,
                             fin_q=self.jr_queue)
        self._update_prov(action)

    def _cancel(self):
        self.mr.cleanup_all()

    def shutdown(self, sig, bt):
        print("Recieved an interupt")
        # Send a cancel to the queue
        self.jr_queue.put(['cancel', None, None])

    def _watch(self, config):
        # Run a thread to check for expired token
        # Run a thread for 7 day max job runtime
        cont = True
        ct = 1
        exp_time = self._get_token_lifetime(config) - 600
        while cont:
            try:
                req = self.jr_queue.get(timeout=1)
                if _time() > exp_time:
                    err = "Token has expired"
                    self.logger.error(err)
                    self._cancel()
                    return {'error': err}
                if req[0] == 'submit':
                    if ct > self.max_task:
                        self.logger.error("Too many subtasks")
                        self._cancel()
                        return {'error': 'Canceled or unexpected error'}
                    if req[2].get('method').startswith('special.'):
                        self._submit_special(config, req[1], req[2])
                    else:
                        self._submit(config, req[1], req[2])
                    ct += 1
                elif req[0] == 'finished_special':
                    job_id = req[1]
                    self.callback_queue.put(['output', job_id, req[2]])
                    ct -= 1
                elif req[0] == 'finished':
                    subjob = True
                    job_id = req[1]
                    if job_id == self.job_id:
                        subjob = False
                    output = self.mr.get_output(job_id, subjob=subjob)
                    self.callback_queue.put(['output', job_id, output])
                    ct -= 1
                    if not subjob:
                        if ct > 0:
                            err = "Orphaned containers may be present"
                            self.logger.error(err)
                        return output
                elif req[0] == 'cancel':
                    self._cancel()
                    return {}
            except Empty:
                pass
            if ct == 0:
                print("Count got to 0 without finish")
                # This shouldn't happen
                return
            # Run cancellation / finish job checker
            if not self._check_job_status():
                self.logger.error("Job canceled or unexpected error")
                self._cancel()
                _sleep(5)
                return {'error': 'Canceled or unexpected error'}

    def _init_callback_url(self):
        # Find a free port and Start up callback server
        if os.environ.get('CALLBACK_IP') is not None:
            self.ip = os.environ.get('CALLBACK_IP')
            self.logger.log("Callback IP provided ({})".format(self.ip))
        else:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("gmail.com", 80))
            self.ip = s.getsockname()[0]
            s.close()
        sock = socket.socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', 0))
        self.port = sock.getsockname()[1]
        sock.close()
        url = 'http://{}:{}/'.format(self.ip, self.port)
        self.logger.log("Job runner recieved Callback URL {}".format(url))
        self.callback_url = url

    def _update_prov(self, action):
        self.prov.add_subaction(action)
        self.callback_queue.put(['prov', None, self.prov.get_prov()])

    def _validate_token(self):
        # Validate token and get user name
        try:
            user = self.auth.get_user(self.config['token'])
        except Exception:
            self.logger.error("Token validation failed")
            raise Exception()

        return user

    def _get_token_lifetime(self, config):
        try:
            url = config.get('auth.service.url.v2')
            header = {'Authorization': self.config['token']}
            resp = requests.get(url, headers=header).json()
            return resp['expires']
        except Exception as e:
            self.logger.error("Failed to get token lifetime")
            raise e

    def run(self):
        """
        This method starts the actual run.  This is a blocking operation and
        will not return until the job finishes or encounters and error.
        This method also handles starting up the callback server.
        """
        self.logger.log('Running on {} ({}) in {}'.format(self.hostname,
                                                          self.ip,
                                                          self.workdir))
        self.logger.log('Client group: {}'.format(self.client_group))

        # Check to see if the job was run before or canceled already.
        # If so, log it
        if not self._check_job_status():
            self.logger.error("Job already run or canceled")
            raise OSError("Canceled job")

        # Get job inputs from njs db
        try:
            job_params = self.njs.get_job_params(self.job_id)
        except Exception as e:
            self.logger.error("Failed to get job parameters. Exiting.")
            raise e

        params = job_params[0]
        config = job_params[1]
        config['job_id'] = self.job_id

        server_version = config['ee.server.version']
        fstr = 'Server version of Execution Engine: {}'
        self.logger.log(fstr.format(server_version))

        # Update job as started and log it
        self.njs.update_job({'job_id': self.job_id, 'is_started': 1})

        self._init_workdir()
        config['workdir'] = self.workdir
        config['user'] = self._validate_token()

        self.prov = Provenance(params)

        # Start the callback server
        cb_args = [self.ip, self.port, self.jr_queue, self.callback_queue,
                   self.token]
        cbs = Process(target=start_callback_server, args=cb_args)
        cbs.start()

        # Submit the main job
        self._submit(config, self.job_id, params, subjob=False)

        output = self._watch(config)

        cbs.kill()
        self.logger.log('Job is done')
        self.njs.finish_job(self.job_id, output)
        # TODO: Attempt to clean up any running docker containers
        #       (if something crashed, for example)
        return output

        # Run docker or shifter	and keep a record of container id and
        #  subjob container ids
        # Run a job shutdown hook
