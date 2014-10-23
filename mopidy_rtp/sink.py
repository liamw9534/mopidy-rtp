from __future__ import unicode_literals

import pygst
pygst.require('0.10')
import gst  # noqa

from mopidy.audio import output
import logging

logger = logging.getLogger(__name__)

# This variable is a global that is set by the Backend
# during initialization from the extension properties
encoder = 'identity'


class RtpSink(gst.Bin):
    def __init__(self):
        super(RtpSink, self).__init__()
        # These elements are 'always on' even if nobody is
        # subscribed to listen.  It streamlines the process
        # of adding/removing listeners.
        queue = gst.element_factory_make('queue')
        rate = gst.element_factory_make('audiorate')
        enc = gst.element_factory_make(encoder)
        pay = gst.element_factory_make('rtpgstpay')
        # Re-use of the audio output bin which handles
        # dynamic element addition/removal nicely
        self.tee = output.AudioOutput()
        self.add_many(queue, rate, enc, pay, self.tee)
        gst.element_link_many(queue, rate, enc, pay, self.tee)
        pad = queue.get_pad('sink')
        ghost_pad = gst.GhostPad('sink', pad)
        self.add_pad(ghost_pad)

    def add(self, host, port):
        b = gst.Bin()
        queue = gst.element_factory_make('queue')
        udpsink = gst.element_factory_make('udpsink')
        udpsink.set_property('host', host)
        udpsink.set_property('port', port)
        # Both async and sync must be true to avoid seek
        # timestamp sync problems
        udpsink.set_property('sync', True)    
        udpsink.set_property('async', True)
        b.add_many(queue, udpsink)
        gst.element_link_many(queue, udpsink)
        pad = queue.get_pad('sink')
        ghost_pad = gst.GhostPad('sink', pad)
        b.add_pad(ghost_pad)
        ident = str(port) + '@' + host
        self.tee.add_sink(ident, b)

    def remove(self, host, port):
        ident = str(port) + '@' + host
        self.tee.remove_sink(ident)
