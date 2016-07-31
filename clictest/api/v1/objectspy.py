# Copyright 2013 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
/Objectspy endpoint for Clictest v1 API
"""

import copy

from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import encodeutils
from oslo_utils import excutils
from oslo_utils import strutils
import six
from webob.exc import HTTPBadRequest
from webob.exc import HTTPConflict
from webob.exc import HTTPForbidden
from webob.exc import HTTPMethodNotAllowed
from webob.exc import HTTPNotFound
from webob.exc import HTTPRequestEntityTooLarge
from webob.exc import HTTPServiceUnavailable
from webob.exc import HTTPUnauthorized
from webob import Response

from clictest.api import common
from clictest.api import policy
import clictest.api.v1
from clictest.api.v1 import controller
from clictest.common import exception
from clictest.common import wsgi
from clictest.i18n import _, _LE, _LI, _LW
import requests
import urllib

LOG = logging.getLogger(__name__)

CONF = cfg.CONF



class Controller(controller.BaseController):
    """
    WSGI controller for images resource in Glance v1 API

    The images resource API is a RESTful web service for image data. The API
    is as follows::

        GET /images -- Returns a set of brief metadata about images
        GET /images/detail -- Returns a set of detailed metadata about
                              images
        HEAD /images/<ID> -- Return metadata about an image with id <ID>
        GET /images/<ID> -- Return image data for image with id <ID>
        POST /images -- Store image data and return metadata about the
                        newly-stored image
        PUT /images/<ID> -- Update image metadata and/or upload image
                            data for a previously-reserved image
        DELETE /images/<ID> -- Delete the image with id <ID>
    """

    def __init__(self):
        pass

    def _enforce(self, req, action, target=None):
        pass

    def show(self, req,userid,prjid,browser,url,chvr):
        
        orgUrl = "http://"+url
        LOG.debug("Original URL = %s" % orgUrl)
        url = 'http://81.134.193.73:8080/ObjectSpyWeb/services/objectspy/getObjectspyFile?userid=%s&projid=%s&browser=%s&url=%s&chvr=%s' % (userid,prjid,browser,orgUrl,chvr)
        
        response = requests.get(url)
        LOG.debug("*********** response captured in clictest service *********************")
        LOG.debug(response)
        
        resp = urllib.quote(response.text)
        return resp 

def create_resource():
    return wsgi.Resource(Controller())

