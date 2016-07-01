# Copyright 2013 OpenStack Foundation
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


def _proxy(target, attr):
    def get_attr(self):
        return getattr(getattr(self, target), attr)

    def set_attr(self, value):
        return setattr(getattr(self, target), attr, value)

    def del_attr(self):
        return delattr(getattr(self, target), attr)

    return property(get_attr, set_attr, del_attr)


class Helper(object):
    def __init__(self, proxy_class=None, proxy_kwargs=None):
        self.proxy_class = proxy_class
        self.proxy_kwargs = proxy_kwargs or {}

    def proxy(self, obj):
        if obj is None or self.proxy_class is None:
            return obj
        return self.proxy_class(obj, **self.proxy_kwargs)

    def unproxy(self, obj):
        if obj is None or self.proxy_class is None:
            return obj
        return obj.base


class TaskRepo(object):
    def __init__(self, base,
                 task_proxy_class=None, task_proxy_kwargs=None):
        self.base = base
        self.task_proxy_helper = Helper(task_proxy_class, task_proxy_kwargs)

    def get(self, task_id):
        task = self.base.get(task_id)
        return self.task_proxy_helper.proxy(task)

    def add(self, task):
        self.base.add(self.task_proxy_helper.unproxy(task))

    def save(self, task):
        self.base.save(self.task_proxy_helper.unproxy(task))

    def remove(self, task):
        base_task = self.task_proxy_helper.unproxy(task)
        self.base.remove(base_task)


class TaskStubRepo(object):
    def __init__(self, base, task_stub_proxy_class=None,
                 task_stub_proxy_kwargs=None):
        self.base = base
        self.task_stub_proxy_helper = Helper(task_stub_proxy_class,
                                             task_stub_proxy_kwargs)

    def list(self, *args, **kwargs):
        tasks = self.base.list(*args, **kwargs)
        return [self.task_stub_proxy_helper.proxy(task) for task in tasks]


class Repo(object):
    def __init__(self, base, item_proxy_class=None, item_proxy_kwargs=None):
        self.base = base
        self.helper = Helper(item_proxy_class, item_proxy_kwargs)

    def get(self, item_id):
        return self.helper.proxy(self.base.get(item_id))

    def list(self, *args, **kwargs):
        items = self.base.list(*args, **kwargs)
        return [self.helper.proxy(item) for item in items]

    def add(self, item):
        base_item = self.helper.unproxy(item)
        result = self.base.add(base_item)
        return self.helper.proxy(result)

    def save(self, item, from_state=None):
        base_item = self.helper.unproxy(item)
        result = self.base.save(base_item, from_state=from_state)
        return self.helper.proxy(result)

    def remove(self, item):
        base_item = self.helper.unproxy(item)
        result = self.base.remove(base_item)
        return self.helper.proxy(result)


