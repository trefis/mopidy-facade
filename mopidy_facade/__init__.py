from __future__ import unicode_literals

import os

from mopidy import config, ext


__version__ = '0.1.0'


class Extension(ext.Extension):

    dist_name = 'Mopidy-Facade'
    ext_name = 'facade'
    version = __version__

    def get_default_config(self):
        conf_file = os.path.join(os.path.dirname(__file__), 'ext.conf')
        return config.read(conf_file)

    def get_config_schema(self):
        schema = super(Extension, self).get_config_schema()
        schema['hostname'] = config.Hostname()
        schema['port'] = config.Port()
        return schema

    def get_frontend_classes(self):
        from .frontend import Facade
        return [Facade]
