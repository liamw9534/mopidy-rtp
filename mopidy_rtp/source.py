import pygst                                                           
pygst.require('0.10')
import gst
import gobject

gobject.threads_init ()

import logging

logger = logging.getLogger(__name__)

# These variables are globals that is set by the Backend
# during initialization from the extension properties
caps_string = 'YXVkaW8veC1yYXctaW50LCBlbmRpYW5uZXNzPShpbnQpMTIzNCwgc2lnbmVkPShib29sZWFuKXRydWUsIHdpZHRoPShpbnQpMTYsIGRlcHRoPShpbnQpMTYsIHJhdGU9KGludCk0NDEwMCwgY2hhbm5lbHM9KGludCky,' 
decoder = 'identity'


class RTPSource(gst.Bin, gst.URIHandler):
    __gstdetails__ = ('RTPSource',
                      'Source',
                      'RTP peer-to-peer audio streaming URIHandler element',
                      'Liam Wickins')

    @staticmethod
    def _parse_uri(uri):
        """The URI takes the form rtp://port and we grab the port from here"""
        return int(uri.split('/')[-1])

    def _launch_rtp_bin(self, port):
        # The capstring is a configured property of the extension
        caps = '''application/x-rtp,
            media=(string)application,
            clock-rate=(int)90000,
            encoding-name=(string)X-GST,
            caps=(string)'''
        # Append the actual caps string configured
        caps += str(caps_string)
        logger.debug('Using caps: %s', caps)
        logger.debug('Using decoder: %s', decoder)
        udpsrc = gst.element_factory_make('udpsrc')
        jitbuf = gst.element_factory_make('gstrtpjitterbuffer')
        depay = gst.element_factory_make('rtpgstdepay')
        dec = gst.element_factory_make(decoder)
        udpsrc.set_property('port', port)
        udpsrc.set_property('caps', gst.Caps(caps))
        jitbuf.set_property('mode', 0)
        self.add_many(udpsrc, jitbuf, depay, dec)
        gst.element_link_many(udpsrc, jitbuf, depay, dec)
        pad = dec.get_pad('src')
        ghost_pad = gst.GhostPad('src', pad)
        self.add_pad(ghost_pad)

    def set_property(self, name, value):
        if name == 'uri':
            self.do_set_uri(value)

    @classmethod                                                  
    def do_get_type_full(cls):
        return gst.URI_SRC
                                                                
    @classmethod                                             
    def do_get_protocols_full(cls):
        return ['rtp']

    def do_set_uri(self, uri):
        if not uri.startswith('rtp://'):
            return False
        self.uri = uri
        port = RTPSource._parse_uri(uri)
        self._launch_rtp_bin(port)
        return True

    def do_get_uri(self):
        return self.uri


# We must register the plugin to ensure it is found
# when playbin wants to stream URIs of the form rtp://
gobject.type_register(RTPSource)                   
gst.element_register(RTPSource, 'rtpsrc', gst.RANK_MARGINAL)
