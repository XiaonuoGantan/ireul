import urlparse
from hanyuu2.helpers.net import resolve_netloc
from gevent import socket
from mutagen._vorbis import error # FIXME? private import
from mutagen.oggvorbis import (
    OggVorbisInfo,
    OggVCommentDict,
)

class VorbisMetaData(object):
    def __init__(self, data):
        self._data = data

    @property
    def raw(self):
        return self._data

    def find_tag(self, name):
        for key, val in self._data:
            if key == name:
                return val
        raise KeyError

    def __unicode__(self):
        return u'%s - %s' % (
            self.find_tag('artist'),
            self.find_tag('title'))


def _yield_metainfo(fh):
    while True:
        try:
            info = OggVorbisInfo(fh)
            yield VorbisMetaData(OggVCommentDict(fh, info))
        except error:
            pass


def get_metadata(url):
    """Returns an iterable yielding the ICY metadata"""
    parse_result = urlparse.urlparse(url)
    hostname, addresses = resolve_netloc(parse_result.netloc)
    conn = None
    for af, address in addresses:
        conn = socket.socket(af, socket.SOCK_STREAM)
        try:
            conn.connect(address)
            break
        except socket.error:
            continue
    conn.send("GET {mount} HTTP/1.1\r\n".format(mount=parse_result.path))
    conn.send("HOST: {hostname}\r\n".format(hostname=hostname))
    conn.send("User-Agent: BrohoofX\r\n")
    conn.send("Icy-MetaData: 1\r\n")
    conn.send("\r\n")

    fileobj = conn.makefile()
    while True:
        buf = fileobj.readline()
        if buf == "\r\n": break
    return _yield_metainfo(fileobj)

