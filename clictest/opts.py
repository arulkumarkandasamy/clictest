# Copyright (c) 2014 OpenStack Foundation.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

__all__ = [
    'list_api_opts'
]

import copy
import itertools

import clictest.api.middleware.context
import clictest.api.versions
import clictest.common.config
import clictest.common.location_strategy
import clictest.common.location_strategy.store_type
import clictest.common.property_utils
import clictest.common.rpc
import clictest.common.wsgi



_api_opts = [
    (None, list(itertools.chain(
        clictest.api.middleware.context.context_opts,
        clictest.api.versions.versions_opts,
        clictest.common.config.common_opts,
        clictest.common.location_strategy.location_strategy_opts,
        clictest.common.property_utils.property_opts,
        clictest.common.rpc.rpc_opts,
        clictest.common.wsgi.bind_opts,
        clictest.common.wsgi.eventlet_opts,
        clictest.common.wsgi.socket_opts))),
    ('image_format', clictest.common.config.image_format_opts),
    ('task', clictest.common.config.task_opts),
    ('profiler', clictest.common.wsgi.profiler_opts),
    ('paste_deploy', clictest.common.config.paste_deploy_opts)
]


def list_api_opts():
    """Return a list of oslo_config options available in Clictest API service.

    Each element of the list is a tuple. The first element is the name of the
    group under which the list of elements in the second element will be
    registered. A group name of None corresponds to the [DEFAULT] group in
    config files.

    This function is also discoverable via the 'clictest.api' entry point
    under the 'oslo_config.opts' namespace.

    The purpose of this is to allow tools like the Oslo sample config file
    generator to discover the options exposed to users by Clictest.

    :returns: a list of (group_name, opts) tuples
    """

    return [(g, copy.deepcopy(o)) for g, o in _api_opts]


