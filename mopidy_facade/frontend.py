from __future__ import unicode_literals

import logging

import SocketServer
import gobject
import json

import subprocess
import pykka

logger = logging.getLogger('mopidy.frontends.facade')

class MyServer(SocketServer.TCPServer):
    def __init__(self, srv_addr, Handler, bind_and_activate=True, core=None):
        self.allow_reuse_address = True
        self.core = core
        SocketServer.TCPServer.__init__(self, srv_addr, Handler, bind_and_activate)

def artist_to_dict(artist):
    return {'uri': artist.uri , 'name': artist.name }

def album_to_dict(album):
    artists = map(artist_to_dict, album.artists)
    return {'uri':album.uri, 'name':album.name, 'artists':artists }

def track_to_dict(track):
    artists = map(artist_to_dict, track.artists)
    album   = album_to_dict(track.album)
    return {'uri':track.uri, 'name':track.name, 'album':album, 'artists':artists }

def serializable_search_result(result):
    def aux(r):
        artists = map(artist_to_dict, r.artists)
        albums = map(album_to_dict, r.albums)
        tracks = map(track_to_dict, r.tracks)
        return {'uri':r.uri, 'tracks':tracks, 'artists':artists, 'albums':albums}

    return map(aux, list(result))

class RequestHandler(SocketServer.StreamRequestHandler):
    def search(self, query):
        logger.info("Facade.searching...")
        result = self.server.core.library.search(query=query).get()
        if result == []:
            logger.info("   ... no result")
            answer = ["error", "Not found"]
        else:
            answer = ["ok", serializable_search_result(result)]
        json.dump(answer, self.wfile)

    def get_album(self, query):
        if query["uri"]is None or query["name"] is None:
            answer = ["error", "expected uri & album name"]
        else:
            results = self.server.core.library.search(album=query["name"]).get()
            results = map(lambda x: x.tracks, results)
            results = reduce(lambda x, y: x + y, results)
            results = filter(lambda x: x.album.uri == query["uri"], results)
            answer  = ["ok", map(track_to_dict, results)]
        json.dump(answer, self.wfile)

    def _queue(self, uri):
        tl_track = self.server.core.tracklist.filter(uri=uri).get()
        if tl_track == [] or tl_track is None:
            logger.info("Facade: adding '%s' to playlist" % uri)
            tl_track = self.server.core.tracklist.add(uri=uri).get()
        if tl_track == [] or tl_track is None:
            logger.info("Facade: uri %s doesn't exist" % uri)
        return tl_track

    def queue(self, uri):
        tl_track = self._queue(uri)
        if tl_track == [] or tl_track is None:
            answer = ["error", "uri '%s' doesn't exist" % uri]
        else:
            answer = ["ok"]
        json.dump(answer, self.wfile)

    def play(self, uri):
        tl_track = self._queue(uri)
        if tl_track == [] or tl_track is None:
            answer = ["error", "uri '%s' doesn't exist" % uri]
        else:
            logger.info("Facade: playing %s" % uri)
            self.server.core.playback.play(tl_track[0])
            answer = ["ok"]
        json.dump(answer, self.wfile)

    def error(self, name):
        error_msg = "unknown query '%s'" % name
        logger.error("Facade: %s" % error_msg)
        json_dump(["error", error_msg], self.wfile)

    def handle(self):
        if self.server.core is None:
            json.dump(["error", "no access to core"], self.wfile)
            return

        handlers = { 
            'search': self.search,
            'play': self.play,
            'queue': self.queue,
            'get_album': self.get_album,
        }

        self.data = self.rfile.readline()
        request = json.loads(self.data)

        handler = handlers.get(request[0], lambda x: error(request[0]))
        handler(request[1])


class Facade(pykka.ThreadingActor):
    def __init__(self, config, core):
        super(Facade, self).__init__()
        self.config = config
        self.core = core
        host = config['facade']['hostname']
        port = config['facade']['port']
        self.server = MyServer((host, port), RequestHandler, core=core)

        gobject.io_add_watch(self.server.fileno(), gobject.IO_IN, self.handle)
        logger.info("Facade server launched")

    def handle(self, fd, flags):
        self.server.handle_request()
        return True

    def on_stop(self):
        pass
