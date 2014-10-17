from __future__ import unicode_literals

import pygst
pygst.require('0.10')
import gst  # noqa

from mopidy.audio import output


class RtpSink(gst.Bin):
    def __init__(self):
        super(RtpSink, self).__init__()
        queue = gst.element_factory_make('queue')
        enc = gst.element_factory_make('flacenc')
        pay = gst.element_factory_make('rtpgstpay')
        self.tee = output.AudioOutput()
        self.add_many(queue, enc, pay, self.tee)
        gst.element_link_many(queue, enc, pay, self.tee)
        pad = queue.get_pad('sink')
        ghost_pad = gst.GhostPad('sink', pad)
        self.add_pad(ghost_pad)

    def add(self, host, port):
        b = gst.Bin()
        queue = gst.element_factory_make('queue')
        udpsink = gst.element_factory_make('udpsink')
        udpsink.set_property('host', host)
        udpsink.set_property('port', port)
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
