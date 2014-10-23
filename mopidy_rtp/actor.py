from __future__ import unicode_literals

import logging
import pykka
import gobject
import socket

from mopidy import backend
from mopidy import exceptions
from mopidy import models
from . import sink
from session import RtpClientSession
from . import source

from mopidy.utils import encoding, network, process

logger = logging.getLogger(__name__)

RTP_SERVICE_NAME = 'rtp'


def parse_uri(uri):
    """
    URIs will take the form "rtp:ip_addr" so we just take the "ip_addr" part of the
    URI and return it
    """
    return uri.split(':')[-1]


def make_uri(addr):
    """
    Performs the inverse operation of :meth:`parse_uri`
    """
    return 'rtp:' + addr


class RtpLibraryProvider(backend.LibraryProvider):
    """
    Live RTP streams are discovered by the backend and stored
    under the 'services' dictionary.  RtpLibraryProvider is
    merely accessing the dictionary of services in order to
    provide a list of available live streams.  There are two
    ways of getting hold of a live stream URI.  One is to use
    the :meth:`browse` method which will provide a list of
    :class:`Track` instances for all live streams.
    Alternatively, :meth:`lookup` can be used with a known
    track URI.  If the services has already been discovered,
    then we return the :class:`Track` to the user.
    """
    root_directory = models.Ref.directory(uri='rtp:', name='RTP')

    def browse(self, uri):
        return [models.Ref.track(uri=make_uri(a), name=self.backend.services[a]) for a in self.backend.services.keys()]

    def lookup(self, uri):
        addr = parse_uri(uri)
        if (addr in self.backend.services.keys()):
            return [models.Track(uri=uri, name=self.backend.services[addr])]
        return []


class RtpPlaybackProvider(backend.PlaybackProvider):
    """
    RtpPlaybackProvider is a wrapper for directing playbin2
    to the correct URIHandler instance for "rtp://" based
    streams.  The implementation for the URIHandler is
    part of this extension under :class:`RtpSource`.
    Since all streams from this provider are "live" streams,
    it is not possible to seek, pause or resume so these
    operations will all return negatively.
    """
    def __init__(self, audio, backend):
        super(RtpPlaybackProvider, self).__init__(audio, backend)
        self.uri = None
        self.host = None
        self.port = None
        self.subscribe_port = self.backend.config['port']

    def _rtp_subscribe(self, host):
        try:
            # This should allocate a random free client port
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.bind((self.backend.hostname, 0))
            port = s.getsockname()[1]
            s.close()
            # Connect to server to subscribe to stream on our alloc'd port
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((host, self.subscribe_port))
            resp = s.recv(1024)
            logger.debug('Connection Reply: %s', resp)
            msg = 'SUBSCRIBE %d\n' % port
            s.send(msg)
            resp = s.recv(1024)
            logger.debug('Subscribe Reply: %s', resp)
            s.close()
            if (resp.rstrip() == 'ERROR_OK'):
                return port
        except:
            pass

    def _rtp_unsubscribe(self, host, port):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((host, self.subscribe_port))
            resp = s.recv(1024)
            logger.debug('Connection Reply: %s', resp)
            msg = 'UNSUBSCRIBE %d\n' % port
            s.send(msg)
            resp = s.recv(1024)
            logger.debug('Unsubscribe Reply: %s', resp)
            s.close()
            if (resp.rstrip() == 'ERROR_OK'):
                return True
        except:
            pass

        return False

    def change_track(self, track):
        if (track.uri != self.uri):
            host = parse_uri(track.uri)
            port = self._rtp_subscribe(host)
            if (port):
                self.uri = track.uri
                self.host = host
                self.port = port
                self.audio.set_uri('rtp://' + str(port)).get()
                return True
            else:
                return False
        return True

    def stop(self):
        if (self.host and self.port):
            if (self.audio.stop_playback().get() and
                self._rtp_unsubscribe(self.host, self.port)):
                self.uri = self.host = self.port = None
                return True
        return False

    def seek(self, time_position):
        return False

    def pause(self):
        return False

    def resume(self):
        return False

    def get_time_position(self):
        return 0


class RtpBackend(pykka.ThreadingActor, backend.Backend):
    """
    RtpBackend provides a peer-to-peer RTP based streaming backend.
    The basic principle of operation is as follows:
    * The currently playing stream is advertised as a live stream for an RTP
      client whom may choose to listen to it.  This information is
      broadcast over a selected network to any clients whom wish to
      discover new RTP services.
    * A client may subscribe to the currently playing live stream by
      contacting the backend and requesting which UDP port they wish
      the RTP stream to be sent on.
    :note: Each stream is setup as a unicast UDP session, even when
        multiple clients are subscribing.  This uses more bandwidth
        over the network but is more reliable than trying to
        multicast which is notoriously problematic on WiFi networks.
    """
    broadcast_period = 1.0
    max_broadcast_packet = 1470

    def __init__(self, config, audio):
        super(RtpBackend, self).__init__()
        self.name = RTP_SERVICE_NAME
        self.public = True
        self.config = config['rtp']
        self.audio = audio
        self.library = RtpLibraryProvider(backend=self)
        self.playback = RtpPlaybackProvider(audio=audio, backend=self)
        self.uri_schemes = ['rtp']
        self.hostname = network.format_hostname(self.config['hostname'])
        self.port = self.config['port']
        self.sock = None
        self.services = {}
        self.event_sources = {}
        self.subscribers = []
        source.decoder = self.config['decoder']
        source.caps_string = self.config['caps']
        sink.encoder = self.config['encoder']

    @staticmethod
    def _audio_sink_name(host, port):
        return RTP_SERVICE_NAME + ':audio:' + str(port) + '@' + host

    def _start_rtp_session(self, host, port):
        if (len(self.subscribers) < self.config['max_subscribers']):
            self.subscribers.append((host, port))
            self.sink.add(host, port)
            return True
        else:
            return False

    def _stop_rtp_session(self, host, port):
        host = host.split(':')[-1]
        if ((host, port) in self.subscribers):
            self.subscribers.remove((host, port))
            self.sink.remove(host, port)
        else:
            logger.warn('Subscriber %s:%s can not be removed - not in subscriber list', host, port)

    def _broadcast_service_info(self):
        broadcast_addr = self.config['hostname'].split('.')
        broadcast_addr[3] = '255'
        broadcast_addr = '.'.join(broadcast_addr)
        if (not self.sock):
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.sock.bind((broadcast_addr, self.config['broadcast_port']))
            tag = gobject.io_add_watch(self.sock.fileno(), gobject.IO_IN,
                                       self._receive_service_info,
                                       None)
            self.event_sources['service'] = tag
            logger.info('RTP broadcast running on [%s]:%s', broadcast_addr,
                        self.config['broadcast_port'])
        msg = self.config['station_name'].replace('%hostname', self.config['hostname'])
        msg = msg.replace('%port', str(self.config['port']))
        self.sock.sendto(msg, (broadcast_addr, self.config['broadcast_port']))
        tag = gobject.timeout_add(int(self.broadcast_period * 1000),
                                  self._broadcast_service_info)
        self.event_sources['broadcast'] = tag
        return False

    def _receive_service_info(self, source=None, cb_condition=None, cb_arg=None):
        try:
            (data, addr) = self.sock.recvfrom(self.max_broadcast_packet)
            if (data):
                logger.debug('Received broadcast packet %s from %s', data, addr)
                if (addr[0] != self.config['hostname']):
                    self.services[addr[0]] = data
        except:
            logger.error('No broadcast packet found')
        return True

    def _start_rtp_client_server(self):
        try:
            network.Server(
                self.hostname,
                self.port,
                protocol=RtpClientSession,
                protocol_kwargs={
                    'backend': self,
                },
                max_connections=self.config['max_subscribers'])
        except IOError as error:
            raise exceptions.BackendError(
                'RTP server startup failed: %s' %
                encoding.locale_decode(error))
        logger.info('RTP server running at [%s]:%s', self.hostname, self.port)

    def _stop_rtp_client_server(self):
        process.stop_actors_by_class(RtpClientSession)

    def _deregister_event_source(self, source):
        tag = self.event_sources.pop(source, None)
        if (tag is not None):
            gobject.source_remove(tag)

    def _deregister_event_sources(self):
        for source in self.event_sources.keys():
            self._deregister_event_source(source)

    def on_start(self):
        if (self.sock is None):
            self.sink = sink.RtpSink()
            self.audio.add_sink('rtp:sink', self.sink)
            self._start_rtp_client_server()
            self._broadcast_service_info()

    def on_stop(self):
        if (self.sock is not None):
            self._deregister_event_sources()
            self._stop_rtp_client_server()
            for s in self.subscribers:
                self._stop_rtp_session(s[0], s[1])
            self.audio.remove_sink('rtp:sink')
            self.sock = None
            self.services = {}
            self.sink = None
