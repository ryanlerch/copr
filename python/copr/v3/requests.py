from __future__ import absolute_import

import os
import json
import requests
from munch import Munch
from requests_toolbelt.multipart.encoder import MultipartEncoder, MultipartEncoderMonitor
from .helpers import List
from .exceptions import CoprRequestException, CoprNoResultException


GET = "GET"
POST = "POST"


class Request(object):
    # This should be a replacement of the _fetch method from APIv1
    # We can have Request, FileRequest, AuthRequest/UnAuthRequest, ...

    def __init__(self, endpoint, api_base_url=None, method=None, data=None, params=None, auth=None):
        """
        :param endpoint:
        :param api_base_url:
        :param method:
        :param data: dict
        :param params: dict for constructing query params in URL (e.g. ?key1=val1)
        :param auth: tuple (login, token)

        @TODO maybe don't have both params and data, but rather only one variable
        @TODO and send it as data on POST and as params on GET
        """
        self.endpoint = endpoint
        self.api_base_url = api_base_url
        self._method = method or GET
        self.data = data
        self.params = params
        self.auth = auth
        self.headers = None

    @property
    def endpoint_url(self):
        return os.path.join(self.api_base_url, self.endpoint.strip("/"))

    @property
    def method(self):
        return self._method.upper()

    def send(self):
        response = requests.request(**self._request_params)
        handle_errors(response)
        return Response(headers=response.headers, data=response.json(), request=self)

    @property
    def _request_params(self):
        return {
            "url": self.endpoint_url,
            "auth": self.auth,
            "json": self.data,
            "method": self.method,
            "params": self.params,
            "headers": self.headers,
        }


class FileRequest(Request):
    def __init__(self, endpoint, files=None, progress_callback=None, **kwargs):
        super(FileRequest, self).__init__(endpoint, **kwargs)
        self.files = files
        self.progress_callback = progress_callback

    @property
    def _request_params(self):
        params = super(FileRequest, self)._request_params

        data = self.files or {}
        data["json"] = ("json", json.dumps(self.data), "application/json")

        callback = self.progress_callback or (lambda x: x)
        m = MultipartEncoder(data)
        params["json"] = None
        params["data"] = MultipartEncoderMonitor(m, callback)
        params["headers"] = {'Content-Type': params["data"].content_type}
        return params


class Response(object):
    def __init__(self, headers=None, data=None, request=None):
        self.headers = headers or {}
        self.data = data or {}
        self.request = request

    def munchify(self):
        if "items" in self.data:
            # @TODO add test case for being a list
            return List(items=[Munch(obj) for obj in self.data["items"]],
                        meta=Munch(self.data["meta"]), response=self)
        return Munch(self.data, __response__=self)


def handle_errors(response):
    response_json = response.json()
    if "error" in response_json and response.status_code == 404:
        raise CoprNoResultException(response_json["error"])
    if "error" in response_json:
        raise CoprRequestException(response_json["error"])
