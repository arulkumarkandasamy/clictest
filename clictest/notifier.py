# Copyright 2011, OpenStack Foundation
# Copyright 2012, Red Hat, Inc.
# Copyright 2013 IBM Corp.
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

import abc

from oslo_config import cfg
from oslo_log import log as logging
import oslo_messaging
from oslo_utils import encodeutils
from oslo_utils import excutils
import six
import webob

from clictest.common import exception
from clictest.common import timeutils
from clictest.domain import proxy as domain_proxy
from clictest.i18n import _, _LE


CONF = cfg.CONF

LOG = logging.getLogger(__name__)

_ALIASES = {
    'clictest.openstack.common.rpc.impl_kombu': 'rabbit',
    'clictest.openstack.common.rpc.impl_qpid': 'qpid',
    'clictest.openstack.common.rpc.impl_zmq': 'zmq',
}


def set_defaults(control_exchange='clictest'):
    oslo_messaging.set_transport_defaults(control_exchange)


def get_transport():
    return oslo_messaging.get_notification_transport(CONF, aliases=_ALIASES)


class Notifier(object):
    """Uses a notification strategy to send out messages about events."""

    def __init__(self):
        publisher_id = CONF.default_publisher_id
        self._transport = get_transport()
        self._notifier = oslo_messaging.Notifier(self._transport,
                                                 publisher_id=publisher_id)

    def warn(self, event_type, payload):
        self._notifier.warn({}, event_type, payload)

    def info(self, event_type, payload):
        self._notifier.info({}, event_type, payload)

    def error(self, event_type, payload):
        self._notifier.error({}, event_type, payload)


def _get_notification_group(notification):
    return notification.split('.', 1)[0]


def _is_notification_enabled(notification):
    disabled_notifications = CONF.disabled_notifications
    notification_group = _get_notification_group(notification)

    notifications = (notification, notification_group)
    for disabled_notification in disabled_notifications:
        if disabled_notification in notifications:
            return False

    return True


def _send_notification(notify, notification_type, payload):
    if _is_notification_enabled(notification_type):
        notify(notification_type, payload)


class NotificationBase(object):
    def get_payload(self, obj):
        return {}

    def send_notification(self, notification_id, obj, extra_payload=None):
        payload = self.get_payload(obj)
        if extra_payload is not None:
            payload.update(extra_payload)

        _send_notification(self.notifier.info, notification_id, payload)


@six.add_metaclass(abc.ABCMeta)
class NotificationProxy(NotificationBase):
    def __init__(self, repo, context, notifier):
        self.repo = repo
        self.context = context
        self.notifier = notifier

        super_class = self.get_super_class()
        super_class.__init__(self, repo)

    @abc.abstractmethod
    def get_super_class(self):
        pass


@six.add_metaclass(abc.ABCMeta)
class NotificationRepoProxy(NotificationBase):
    def __init__(self, repo, context, notifier):
        self.repo = repo
        self.context = context
        self.notifier = notifier
        proxy_kwargs = {'context': self.context, 'notifier': self.notifier}

        proxy_class = self.get_proxy_class()
        super_class = self.get_super_class()
        super_class.__init__(self, repo, proxy_class, proxy_kwargs)

    @abc.abstractmethod
    def get_super_class(self):
        pass

    @abc.abstractmethod
    def get_proxy_class(self):
        pass


@six.add_metaclass(abc.ABCMeta)
class NotificationFactoryProxy(object):
    def __init__(self, factory, context, notifier):
        kwargs = {'context': context, 'notifier': notifier}

        proxy_class = self.get_proxy_class()
        super_class = self.get_super_class()
        super_class.__init__(self, factory, proxy_class, kwargs)

    @abc.abstractmethod
    def get_super_class(self):
        pass

    @abc.abstractmethod
    def get_proxy_class(self):
        pass


