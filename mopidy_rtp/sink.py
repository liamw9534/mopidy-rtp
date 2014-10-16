from __future__ import unicode_literals

import pygst
pygst.require('0.10')
import gst  # noqa


class RtpSink(gst.Bin):
    def __init__(self, addr, port):
        super(RtpSink, self).__init__()
        queue = gst.element_factory_make('queue')
        enc = gst.element_factory_make('sbcenc')
        pay = gst.element_factory_make('rtpgstpay')
        udpsink = gst.element_factory_make('udpsink')
        udpsink.set_property('host', addr)
        udpsink.set_property('port', port)
        self.add_many(queue, enc, pay, udpsink)
        gst.element_link_many(queue, enc, pay, udpsink)
        pad = queue.get_pad('sink')
        ghost_pad = gst.GhostPad('sink', pad)
        self.add_pad(ghost_pad)
