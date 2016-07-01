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


class TaskProxy(NotificationProxy, domain_proxy.Task):
    def get_super_class(self):
        return domain_proxy.Task

    def get_payload(self, obj):
        return format_task_notification(obj)

    def begin_processing(self):
        super(TaskProxy, self).begin_processing()
        self.send_notification('task.processing', self.repo)

    def succeed(self, result):
        super(TaskProxy, self).succeed(result)
        self.send_notification('task.success', self.repo)

    def fail(self, message):
        super(TaskProxy, self).fail(message)
        self.send_notification('task.failure', self.repo)

    def run(self, executor):
        super(TaskProxy, self).run(executor)
        self.send_notification('task.run', self.repo)


class TaskFactoryProxy(NotificationFactoryProxy, domain_proxy.TaskFactory):
    def get_super_class(self):
        return domain_proxy.TaskFactory

    def get_proxy_class(self):
        return TaskProxy


class TaskRepoProxy(NotificationRepoProxy, domain_proxy.TaskRepo):
    def get_super_class(self):
        return domain_proxy.TaskRepo

    def get_proxy_class(self):
        return TaskProxy

    def get_payload(self, obj):
        return format_task_notification(obj)

    def add(self, task):
        result = super(TaskRepoProxy, self).add(task)
        self.send_notification('task.create', task)
        return result

    def remove(self, task):
        result = super(TaskRepoProxy, self).remove(task)
        self.send_notification('task.delete', task, extra_payload={
            'deleted': True, 'deleted_at': timeutils.isotime()
        })
        return result


class TaskStubProxy(NotificationProxy, domain_proxy.TaskStub):
    def get_super_class(self):
        return domain_proxy.TaskStub


class TaskStubRepoProxy(NotificationRepoProxy, domain_proxy.TaskStubRepo):
    def get_super_class(self):
        return domain_proxy.TaskStubRepo

    def get_proxy_class(self):
        return TaskStubProxy


class MetadefNamespaceProxy(NotificationProxy, domain_proxy.MetadefNamespace):
    def get_super_class(self):
        return domain_proxy.MetadefNamespace


class MetadefNamespaceFactoryProxy(NotificationFactoryProxy,
                                   domain_proxy.MetadefNamespaceFactory):
    def get_super_class(self):
        return domain_proxy.MetadefNamespaceFactory

    def get_proxy_class(self):
        return MetadefNamespaceProxy


class MetadefNamespaceRepoProxy(NotificationRepoProxy,
                                domain_proxy.MetadefNamespaceRepo):
    def get_super_class(self):
        return domain_proxy.MetadefNamespaceRepo

    def get_proxy_class(self):
        return MetadefNamespaceProxy

    def get_payload(self, obj):
        return format_metadef_namespace_notification(obj)

    def save(self, metadef_namespace):
        name = getattr(metadef_namespace, '_old_namespace',
                       metadef_namespace.namespace)
        result = super(MetadefNamespaceRepoProxy, self).save(metadef_namespace)
        self.send_notification(
            'metadef_namespace.update', metadef_namespace,
            extra_payload={
                'namespace_old': name,
            })
        return result

    def add(self, metadef_namespace):
        result = super(MetadefNamespaceRepoProxy, self).add(metadef_namespace)
        self.send_notification('metadef_namespace.create', metadef_namespace)
        return result

    def remove(self, metadef_namespace):
        result = super(MetadefNamespaceRepoProxy, self).remove(
            metadef_namespace)
        self.send_notification(
            'metadef_namespace.delete', metadef_namespace,
            extra_payload={'deleted': True, 'deleted_at': timeutils.isotime()}
        )
        return result

    def remove_objects(self, metadef_namespace):
        result = super(MetadefNamespaceRepoProxy, self).remove_objects(
            metadef_namespace)
        self.send_notification('metadef_namespace.delete_objects',
                               metadef_namespace)
        return result

    def remove_properties(self, metadef_namespace):
        result = super(MetadefNamespaceRepoProxy, self).remove_properties(
            metadef_namespace)
        self.send_notification('metadef_namespace.delete_properties',
                               metadef_namespace)
        return result

    def remove_tags(self, metadef_namespace):
        result = super(MetadefNamespaceRepoProxy, self).remove_tags(
            metadef_namespace)
        self.send_notification('metadef_namespace.delete_tags',
                               metadef_namespace)
        return result


class MetadefObjectProxy(NotificationProxy, domain_proxy.MetadefObject):
    def get_super_class(self):
        return domain_proxy.MetadefObject


class MetadefObjectFactoryProxy(NotificationFactoryProxy,
                                domain_proxy.MetadefObjectFactory):
    def get_super_class(self):
        return domain_proxy.MetadefObjectFactory

    def get_proxy_class(self):
        return MetadefObjectProxy


class MetadefObjectRepoProxy(NotificationRepoProxy,
                             domain_proxy.MetadefObjectRepo):
    def get_super_class(self):
        return domain_proxy.MetadefObjectRepo

    def get_proxy_class(self):
        return MetadefObjectProxy

    def get_payload(self, obj):
        return format_metadef_object_notification(obj)

    def save(self, metadef_object):
        name = getattr(metadef_object, '_old_name', metadef_object.name)
        result = super(MetadefObjectRepoProxy, self).save(metadef_object)
        self.send_notification(
            'metadef_object.update', metadef_object,
            extra_payload={
                'namespace': metadef_object.namespace.namespace,
                'name_old': name,
            })
        return result

    def add(self, metadef_object):
        result = super(MetadefObjectRepoProxy, self).add(metadef_object)
        self.send_notification('metadef_object.create', metadef_object)
        return result

    def remove(self, metadef_object):
        result = super(MetadefObjectRepoProxy, self).remove(metadef_object)
        self.send_notification(
            'metadef_object.delete', metadef_object,
            extra_payload={
                'deleted': True,
                'deleted_at': timeutils.isotime(),
                'namespace': metadef_object.namespace.namespace
            }
        )
        return result


class MetadefPropertyProxy(NotificationProxy, domain_proxy.MetadefProperty):
    def get_super_class(self):
        return domain_proxy.MetadefProperty


class MetadefPropertyFactoryProxy(NotificationFactoryProxy,
                                  domain_proxy.MetadefPropertyFactory):
    def get_super_class(self):
        return domain_proxy.MetadefPropertyFactory

    def get_proxy_class(self):
        return MetadefPropertyProxy


class MetadefPropertyRepoProxy(NotificationRepoProxy,
                               domain_proxy.MetadefPropertyRepo):
    def get_super_class(self):
        return domain_proxy.MetadefPropertyRepo

    def get_proxy_class(self):
        return MetadefPropertyProxy

    def get_payload(self, obj):
        return format_metadef_property_notification(obj)

    def save(self, metadef_property):
        name = getattr(metadef_property, '_old_name', metadef_property.name)
        result = super(MetadefPropertyRepoProxy, self).save(metadef_property)
        self.send_notification(
            'metadef_property.update', metadef_property,
            extra_payload={
                'namespace': metadef_property.namespace.namespace,
                'name_old': name,
            })
        return result

    def add(self, metadef_property):
        result = super(MetadefPropertyRepoProxy, self).add(metadef_property)
        self.send_notification('metadef_property.create', metadef_property)
        return result

    def remove(self, metadef_property):
        result = super(MetadefPropertyRepoProxy, self).remove(metadef_property)
        self.send_notification(
            'metadef_property.delete', metadef_property,
            extra_payload={
                'deleted': True,
                'deleted_at': timeutils.isotime(),
                'namespace': metadef_property.namespace.namespace
            }
        )
        return result


class MetadefResourceTypeProxy(NotificationProxy,
                               domain_proxy.MetadefResourceType):
    def get_super_class(self):
        return domain_proxy.MetadefResourceType


class MetadefResourceTypeFactoryProxy(NotificationFactoryProxy,
                                      domain_proxy.MetadefResourceTypeFactory):
    def get_super_class(self):
        return domain_proxy.MetadefResourceTypeFactory

    def get_proxy_class(self):
        return MetadefResourceTypeProxy


class MetadefResourceTypeRepoProxy(NotificationRepoProxy,
                                   domain_proxy.MetadefResourceTypeRepo):
    def get_super_class(self):
        return domain_proxy.MetadefResourceTypeRepo

    def get_proxy_class(self):
        return MetadefResourceTypeProxy

    def get_payload(self, obj):
        return format_metadef_resource_type_notification(obj)

    def add(self, md_resource_type):
        result = super(MetadefResourceTypeRepoProxy, self).add(
            md_resource_type)
        self.send_notification('metadef_resource_type.create',
                               md_resource_type)
        return result

    def remove(self, md_resource_type):
        result = super(MetadefResourceTypeRepoProxy, self).remove(
            md_resource_type)
        self.send_notification(
            'metadef_resource_type.delete', md_resource_type,
            extra_payload={
                'deleted': True,
                'deleted_at': timeutils.isotime(),
                'namespace': md_resource_type.namespace.namespace
            }
        )
        return result


class MetadefTagProxy(NotificationProxy, domain_proxy.MetadefTag):
    def get_super_class(self):
        return domain_proxy.MetadefTag


class MetadefTagFactoryProxy(NotificationFactoryProxy,
                             domain_proxy.MetadefTagFactory):
    def get_super_class(self):
        return domain_proxy.MetadefTagFactory

    def get_proxy_class(self):
        return MetadefTagProxy


class MetadefTagRepoProxy(NotificationRepoProxy, domain_proxy.MetadefTagRepo):
    def get_super_class(self):
        return domain_proxy.MetadefTagRepo

    def get_proxy_class(self):
        return MetadefTagProxy

    def get_payload(self, obj):
        return format_metadef_tag_notification(obj)

    def save(self, metadef_tag):
        name = getattr(metadef_tag, '_old_name', metadef_tag.name)
        result = super(MetadefTagRepoProxy, self).save(metadef_tag)
        self.send_notification(
            'metadef_tag.update', metadef_tag,
            extra_payload={
                'namespace': metadef_tag.namespace.namespace,
                'name_old': name,
            })
        return result

    def add(self, metadef_tag):
        result = super(MetadefTagRepoProxy, self).add(metadef_tag)
        self.send_notification('metadef_tag.create', metadef_tag)
        return result

    def add_tags(self, metadef_tags):
        result = super(MetadefTagRepoProxy, self).add_tags(metadef_tags)
        for metadef_tag in metadef_tags:
            self.send_notification('metadef_tag.create', metadef_tag)

        return result

    def remove(self, metadef_tag):
        result = super(MetadefTagRepoProxy, self).remove(metadef_tag)
        self.send_notification(
            'metadef_tag.delete', metadef_tag,
            extra_payload={
                'deleted': True,
                'deleted_at': timeutils.isotime(),
                'namespace': metadef_tag.namespace.namespace
            }
        )
        return result
