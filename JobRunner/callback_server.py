from sanic import Sanic
from sanic.response import json
from sanic.exceptions import abort
import uuid
from queue import Empty
import asyncio

app = Sanic()
outputs = dict()
prov = None


def _check_finished():
    global prov
    in_q = app.config['in_q']
    try:
        # Flush the queue
        while True:
            [mtype, fjob_id, output] = in_q.get(block=False)
            if mtype == 'output':
                outputs[fjob_id] = output
            elif mtype == 'prov':
                prov = output
    except Empty:
        pass


async def _process_rpc(data, token):
    (module, method) = data['method'].split('.')
    # async submi job
    if method.startswith('_') and method.endswith('_submit'):
        if token != app.config.get('token'):
            abort(401)
        job_id = str(uuid.uuid1())
        data['method'] = '%s.%s' % (module, method[1:-7])
        app.config['out_q'].put(['submit',  job_id, data])
        return {'result': job_id}
    # check job
    elif method.startswith('_check_job'):
        if 'params' not in data:
            abort(404)
        job_id = data['params'][0]
        _check_finished()
        resp = {'finished': False}
        if job_id in outputs:
            resp = outputs[job_id]
            resp['finished'] = True
        return {'result': [resp]}
    # Provenance
    elif method.startswith('get_provenance'):
        _check_finished()
        return {'result': [prov]}
    else:
        if token != app.config.get('token'):
            abort(401)
        job_id = str(uuid.uuid1())
        data['method'] = '%s.%s' % (module, method[1:-7])
        app.config['out_q'].put(['submit',  job_id, data])
        try:
            while True:
                _check_finished()
                if job_id in outputs:
                    resp = outputs[job_id]
                    resp['finished'] = True
                    return resp
                await asyncio.sleep(1)
        except Exception:
            return {'error': 'Timeout'}


@app.route("/", methods=['GET', 'POST'])
async def root(request):
    data = request.json
    if request.method == 'POST' and data is not None and 'method' in data:
        token = request.headers.get('Authorization')
        return json(await _process_rpc(data, token))
    return json({})


def start_callback_server(ip, port, out_queue, in_queue, token):
    conf = {
        'token': token,
        'out_q': out_queue,
        'in_q': in_queue
    }
    app.config.update(conf)
    app.run(host=ip, port=port, debug=False, access_log=False)
