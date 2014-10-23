from __future__ import unicode_literals

import os

from mopidy import config, ext, exceptions

__version__ = '0.1.0'


class Extension(ext.Extension):

    dist_name = 'Mopidy-RTP'
    ext_name = 'rtp'
    version = __version__

    def get_default_config(self):
        conf_file = os.path.join(os.path.dirname(__file__), 'ext.conf')
        return config.read(conf_file)

    def get_config_schema(self):
        schema = super(Extension, self).get_config_schema()
        schema['hostname'] = config.String()
        schema['port'] = config.Integer(minimum=1, maximum=65535)
        schema['broadcast_port'] = config.Integer(minimum=1, maximum=65535)
        schema['max_subscribers'] = config.Integer(minimum=1)
        schema['station_name'] = config.String()
        schema['caps'] = config.String()
        schema['encoder'] = config.String()
        schema['decoder'] = config.String()
        return schema

    def validate_environment(self):
        pass

    def setup(self, registry):
        from .actor import RtpBackend
        registry.add('backend', RtpBackend)
