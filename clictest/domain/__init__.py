# Copyright 2012 OpenStack Foundation
# Copyright 2013 IBM Corp.
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

import collections
import datetime
import uuid

from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import excutils
from oslo_utils import importutils
import six

from clictest.common import exception
from clictest.common import timeutils
from clictest.i18n import _, _LE, _LI, _LW

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


_delayed_delete_imported = False


class ExtraProperties(collections.MutableMapping, dict):

    def __getitem__(self, key):
        return dict.__getitem__(self, key)

    def __setitem__(self, key, value):
        return dict.__setitem__(self, key, value)

    def __delitem__(self, key):
        return dict.__delitem__(self, key)

    def __eq__(self, other):
        if isinstance(other, ExtraProperties):
            return dict(self).__eq__(dict(other))
        elif isinstance(other, dict):
            return dict(self).__eq__(other)
        else:
            return False

    def __len__(self):
        return dict(self).__len__()

    def keys(self):
        return dict(self).keys()


class Task(object):
    _supported_task_type = ('import',)

    _supported_task_status = ('pending', 'processing', 'success', 'failure')

    def __init__(self, task_id, task_type, status, owner,
                 expires_at, created_at, updated_at,
                 task_input, result, message):

        if task_type not in self._supported_task_type:
            raise exception.InvalidTaskType(task_type)

        if status not in self._supported_task_status:
            raise exception.InvalidTaskStatus(status)

        self.task_id = task_id
        self._status = status
        self.type = task_type
        self.owner = owner
        self.expires_at = expires_at
        # NOTE(nikhil): We use '_time_to_live' to determine how long a
        # task should live from the time it succeeds or fails.
        task_time_to_live = CONF.task.task_time_to_live
        self._time_to_live = datetime.timedelta(hours=task_time_to_live)
        self.created_at = created_at
        self.updated_at = updated_at
        self.task_input = task_input
        self.result = result
        self.message = message

    @property
    def status(self):
        return self._status

    @property
    def message(self):
        return self._message

    @message.setter
    def message(self, message):
        if message:
            self._message = six.text_type(message)
        else:
            self._message = six.text_type('')

    def _validate_task_status_transition(self, cur_status, new_status):
        valid_transitions = {
            'pending': ['processing', 'failure'],
            'processing': ['success', 'failure'],
            'success': [],
            'failure': [],
        }

        if new_status in valid_transitions[cur_status]:
            return True
        else:
            return False

    def _set_task_status(self, new_status):
        if self._validate_task_status_transition(self.status, new_status):
            self._status = new_status
            LOG.info(_LI("Task [%(task_id)s] status changing from "
                         "%(cur_status)s to %(new_status)s"),
                     {'task_id': self.task_id, 'cur_status': self.status,
                      'new_status': new_status})
            self._status = new_status
        else:
            LOG.error(_LE("Task [%(task_id)s] status failed to change from "
                          "%(cur_status)s to %(new_status)s"),
                      {'task_id': self.task_id, 'cur_status': self.status,
                       'new_status': new_status})
            raise exception.InvalidTaskStatusTransition(
                cur_status=self.status,
                new_status=new_status
            )

    def begin_processing(self):
        new_status = 'processing'
        self._set_task_status(new_status)

    def succeed(self, result):
        new_status = 'success'
        self.result = result
        self._set_task_status(new_status)
        self.expires_at = timeutils.utcnow() + self._time_to_live

    def fail(self, message):
        new_status = 'failure'
        self.message = message
        self._set_task_status(new_status)
        self.expires_at = timeutils.utcnow() + self._time_to_live

    def run(self, executor):
        executor.begin_processing(self.task_id)


class TaskStub(object):

    def __init__(self, task_id, task_type, status, owner,
                 expires_at, created_at, updated_at):
        self.task_id = task_id
        self._status = status
        self.type = task_type
        self.owner = owner
        self.expires_at = expires_at
        self.created_at = created_at
        self.updated_at = updated_at

    @property
    def status(self):
        return self._status


class TaskFactory(object):

    def new_task(self, task_type, owner,
                 task_input=None, **kwargs):
        task_id = str(uuid.uuid4())
        status = 'pending'
        # Note(nikhil): expires_at would be set on the task, only when it
        # succeeds or fails.
        expires_at = None
        created_at = timeutils.utcnow()
        updated_at = created_at
        return Task(
            task_id,
            task_type,
            status,
            owner,
            expires_at,
            created_at,
            updated_at,
            task_input,
            kwargs.get('result'),
            kwargs.get('message')
        )


