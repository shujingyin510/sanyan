import json
import urllib.request
import urllib.parse
import urllib.error
from collections import namedtuple

Response = namedtuple('Response', ['status_code', 'text', 'json', 'headers'])

def _build_response(resp):
    data = resp.read()
    text = data.decode('utf-8')
    headers = dict(resp.getheaders())
    def json_parser():
        return json.loads(text)
    return Response(
        status_code=resp.getcode(),
        text=text,
        json=json_parser,
        headers=headers
    )

def request(method, url, params=None, data=None, json_data=None, headers=None, timeout=None):
    if params:
        url = url + '?' + urllib.parse.urlencode(params)
    if json_data is not None:
        data = json.dumps(json_data)
        if headers is None:
            headers = {}
        headers['Content-Type'] = 'application/json'
    if data is not None and isinstance(data, str):
        data = data.encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return _build_response(resp)
    except urllib.error.HTTPError as e:
        return _build_response(e)

def get(url, params=None, headers=None, timeout=None):
    return request('GET', url, params=params, headers=headers, timeout=timeout)

def post(url, data=None, json=None, headers=None, timeout=None):
    return request('POST', url, data=data, json_data=json, headers=headers, timeout=timeout)

def put(url, data=None, json=None, headers=None, timeout=None):
    return request('PUT', url, data=data, json_data=json, headers=headers, timeout=timeout)

def delete(url, params=None, headers=None, timeout=None):
    return request('DELETE', url, params=params, headers=headers, timeout=timeout)