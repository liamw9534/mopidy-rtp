****************************
Mopidy-RTP
****************************

.. image:: https://pypip.in/version/Mopidy-RTP/badge.png?latest
    :target: https://pypi.python.org/pypi/Mopidy-RTP/
    :alt: Latest PyPI version

.. image:: https://pypip.in/download/Mopidy-RTP/badge.png
    :target: https://pypi.python.org/pypi/Mopidy-RTP/
    :alt: Number of PyPI downloads

.. image:: https://travis-ci.org/liamw9534/mopidy-rtp.png?branch=master
    :target: https://travis-ci.org/liamw9534/mopidy-rtp
    :alt: Travis CI build status

.. image:: https://coveralls.io/repos/liamw9534/mopidy-rtp/badge.png?branch=master
   :target: https://coveralls.io/r/liamw9534/mopidy-rtp?branch=master
   :alt: Test coverage

`Mopidy <http://www.mopidy.com/>`_ Peer-to-peer RTP streaming backend

Installation
============

Install by running::

    pip install Mopidy-RTP

Or, if available, install the Debian/Ubuntu package from `apt.mopidy.com
<http://apt.mopidy.com/>`_.


Introduction
============

Some music players on the market allow a single music source to be streamed throughout the
home by means of either broadcast, multicast or unicast of that source to other music
devices.  This is particularly useful in situations where the music source can only be played
by one user at a time (e.g., a Spotify premium subscription service).

This extension provides peer-to-peer music sharing for Mopidy, whereby any Mopidy music
player can subscribe and listen to whatever is playing on another Mopidy music player.

The concept is much like that of a radio station whereby whatever a Mopidy music player
is playing is simply viewed as a constant stream with occasional pauses between the tracks
that it plays.  To the peer listener, this is just really just like listening to a radio station.

The underpinning technology for this extension is based around using RTP to encapsulate packets
that have been encoded (using SBC codec).  Each packet is transmitted using UDP unicast -
the reason for unicast is because multicast does not work on WiFi networks (owing to limitations
of WiFi in how multicast is handled).


Configuration
=============

Extension
---------

Add the following section to your Mopidy configuration file following installation::

    [rtp]
    enabled = true
    hostname = 192.168.0.1
    port = 7128
    broadcast_port = 46986
    max_subscribers = 8
    station_name = Mopidy RTP Service on %hostname:%port


The ``hostname`` setting should be the IP address of the network interface you wish to designate
for RTP traffic.  For example, if you have two ethernet adapters, say, one wired on ``192.168.1.0/24``
and one wireless on ``192.168.0.0/24`` then select the IP address of the interface on which you wish your
RTP traffic to be streamed and visible to other peers.  All peers should select the same network to
ensure they are visible to one another.

Once the backend has started it will begin to broadcast, periodically, a discovery packet which informs
other peers of its presence (note: a peer is any other Mopidy system running this backend).  These
packets are sent on the port number defined by the property ``broadcast_port``.  The backend will also keep
track of a list of all peers it has discovered by listening on the broadcast port.

The list of available peers can be browsed using the URI ``rtp:stations`` via the backend.  This will
return a list of track references that denote the available stations.  Each station is denoted by
a URI and a station name.  The station name is defined via the ``station_name`` property and the URI is
derived from the ``hostname`` property.  For example, a track reference with a URI of ``rtp:192.168.0.118``
would mean that a peer was discovered from IP address ``192.168.0.118``.

A station on any discovered peer can be played by selecting its URI to play.  The client backend
will firstly subscribe to that station by contacting the peer on its "subscriber" TCP port, which is
defined via the ``port`` property, and requesting that the peer streams to a client allocated UDP
port number.  This port number is randomly assigned by the client, from the list of free ports.  Upon
receiving the request, the peer will begin to stream UDP packets to the client on the requested
UDP port.

The backend permits multiple clients simultaneously.  The property ``max_subscribers`` allows this
to be limited to a sensible number thus avoiding network bandwidth and/or CPU overload.


Project resources
=================

- `Source code <https://github.com/liamw9534/mopidy-rtp>`_
- `Issue tracker <https://github.com/liamw9534/mopidy-rtp/issues>`_
- `Download development snapshot <https://github.com/liamw9534/mopidy-rtp/archive/master.tar.gz#egg=mopidy-rtp-dev>`_


Changelog
=========


v0.1.0 (UNRELEASED)
----------------------------------------

- Initial cut with some limitations:

1) Requires optimization of RTP sink to avoid duplication of entire pipeline for each connected client.
2) If a peer pauses its station and then resumes, listening clients do not resume.
3) It is possible to get into silly situations e.g., two peers subscribing to each other's station.
This is permitted but may result in a nasty feedback loop or no output at all, so apply caution.
