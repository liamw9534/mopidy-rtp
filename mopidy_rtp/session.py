from __future__ import unicode_literals

import logging

from mopidy.utils import formatting, network

logger = logging.getLogger(__name__)

VERSION = '0.0.1'


class RtpClientSession(network.LineProtocol):
    """
    The RTP client session. Keeps track of a single client session.
    Owing to the simplicity of the protocol, it is also terminated
    in this class.  Supported commands are:
    * subscribe <udp_port> - client wishes to subscribe to service
        to its own IP address on <udp_port> using unicast
    * unsubscribe <udp_port> - client wishes to unsubscribe from service
        being received on <udp_port> using unicast
    """

    terminator = '\n'
    encoding = 'UTF-8'
    delimiter = r'\r?\n'

    def __init__(self, connection, backend=None):
        super(RtpClientSession, self).__init__(connection)
        self.backend = backend

    def on_start(self):
        logger.info('New RTP connection from [%s]:%s', self.host, self.port)
        self.send_lines(['OK RTP %s' % VERSION])

    def on_line_received(self, line):
        logger.info('Request from [%s]:%s: %s', self.host, self.port, line)

        tokens = line.split(' ')
        response = None
        if (len(tokens) == 2 and tokens[0] == 'subscribe'):
            port = int(tokens[1])
            host = self.host.split(':')[-1]
            ret = self.backend._start_rtp_session(host, port)
            if (not ret):
                response = 'error subscriber_limit_reached'
        elif (len(tokens) == 2 and tokens[0] == 'unsubscribe'):
            port = int(tokens[1])
            self.backend._stop_rtp_session(self.host, port)
        else:
            response = 'error unrecognized_command'

        if not response:
            return

        logger.debug(
            'Response to [%s]:%s: %s', self.host, self.port,
            formatting.indent(self.terminator.join(response)))

        self.send_lines(response)

    def decode(self, line):
        try:
            return super(RtpClientSession, self).decode(line)
        except ValueError:
            logger.warning(
                'Stopping actor due to unescaping error, data '
                'supplied by client was not valid.')
            self.stop()

    def close(self):
        self.stop()
