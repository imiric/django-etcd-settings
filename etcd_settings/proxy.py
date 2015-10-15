from importlib import import_module
from django.conf import settings as django_settings
from .manager import EtcdConfigManager
from .utils import attrs_to_dir, dict_rec_update


class EtcdSettingsProxy(object):

    def __init__(self):
        env = django_settings.DJES_ENV
        dev_params = django_settings.DJES_DEV_PARAMS
        etcd_details = django_settings.DJES_ETCD_DETAILS
        self._request_getter_module = \
            django_settings.DJES_REQUEST_GETTER_MODULE
        if etcd_details is not None:
            self._etcd_mgr = EtcdConfigManager(
                dev_params, **etcd_details)
            self._config_sets = self._etcd_mgr.get_config_sets()
            self._env_defaults = self._etcd_mgr.get_env_defaults(env)
        else:
            self._etcd_mgr = None
            self._config_sets = dict()
            self._env_defaults = EtcdConfigManager.get_dev_params(dev_params)

    def _parse_req_config_sets(self):
        sets = []
        if self._request_getter_module is not None:
            req_getter = import_module(
                django_settings.REQUEST_GETTER_MODULE).get_current_request
            request = req_getter()
            if request and getattr(request, "META", None):
                sets = request.META.get('HTTP_X_DYNAMIC_SETTING', '').split()
        return sets

    def start_monitors(self):
        if self._etcd_mgr is not None:
            self._env_defaults = self.monitor_env_defaults(self.env)
            self._config_sets = self.monitor_config_sets()

    def __getattr__(self, attr):
        try:
            dj_value = getattr(django_settings, attr)
            dj_value_exists = True
        except AttributeError:
            dj_value_exists = False
            dj_value = None
        try:
            value = self._env_defaults[attr]
            value_exists = True
        except KeyError:
            value_exists = dj_value_exists
            value = dj_value

        for override_set in self._parse_req_config_sets():
            new_value = self._config_sets.get(override_set, {}).get(attr)
            if new_value:
                if isinstance(value, dict) and isinstance(new_value, dict):
                    dict_rec_update(value, new_value)
                else:
                    value = new_value
        if value or value_exists:
            return value
        else:
            raise AttributeError(attr)

    def as_dict(self):
        items = attrs_to_dir(django_settings)
        items.update(self._env_defaults)
        return items


proxy = EtcdSettingsProxy()
