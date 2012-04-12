from sqlalchemy.ext.hybrid import hybrid_property
import datetime, json, pickle
import audiotools
from .filesystem import cont_addr

class _unspecified(object):
    def __repr__(self):
        return "unspecified"

unspecified = _unspecified()


class Blob(object):
    def __init__(self, cont_addr, mime_type, added_at=unspecified):
        """
        added_at is now if unspecified
        """
        self._cont_addr = cont_addr
        self._mime_type = mime_type
        if added_at is unspecified:
            added_at = datetime.datetime.now()
        self._added_at = added_at

    @hybrid_property
    def cont_addr(self):
        return self._cont_addr

    def __repr__(self):
        return "%s.%s(%r, %r, %r)" % (
            type(self).__module__,
            type(self).__name__,
            self._cont_addr,
            self._mime_type,
            self._added_at)


class TrackOriginal(object):
    def __init__(self, blob, metadata=None, artist=None, title=None):
        self._blob = blob
        self.metadata = metadata
        self._artist = artist
        self._title = title

    def __repr__(self):
        return "%s.%s(%r, %r, %r, %r)" % (
            type(self).__module__,
            type(self).__name__,
            self._blob,
            self._metadata,
            self._artist,
            self._title)

    @hybrid_property
    def blob(self):
        return self._blob

    @property
    def metadata(self):
        return pickle.loads(self._metadata)

    @metadata.setter
    def metadata(self, val):
        self._metadata = pickle.dumps(val)

    def open(self):
        return cont_addr.open(self.blob.cont_addr)

    def open_audiotools(self):
        return audiotools.open(cont_addr.addr_to_path(self.blob.cont_addr))



class TrackDerived(object):
    def __init__(self, original, blob, codec,
                 compression_params, added_at=unspecified):
        self.original = original
        self._blob = blob
        self._codec = codec
        self.compression_params = compression_params
        if added_at is unspecified:
            added_at = datetime.datetime.now()
        self._added_at = added_at

    def __repr__(self):
        return "%s.%s(%r, %r, %r, %r, %r)" % (
            type(self).__module__,
            type(self).__name__,
            self.original,
            self._blob,
            self._codec,
            self._compression_params,
            self._added_at)

    @hybrid_property
    def blob(self):
        return self._blob

    @property
    def compression_params(self):
        return json.loads(self._compression_params)

    @compression_params.setter
    def compression_params(self, val):
        self._compression_params = json.dumps(val)

    def open(self):
        return cont_addr.open(self.blob.cont_addr)

    def open_audiotools(self):
        return audiotools.open(cont_addr.addr_to_path(self.blob.cont_addr))


from . import tables

from sqlalchemy.orm import mapper, relationship

mapper(Blob, tables.blob,
       column_prefix="_",
       properties={})

mapper(TrackOriginal, tables.track_orig,
       column_prefix="_",
       properties={
           '_blob': relationship(Blob),
           'derivatives': relationship(TrackDerived, lazy='dynamic'),
       })

mapper(TrackDerived, tables.track_derived,
       column_prefix="_",
       properties={
           '_blob': relationship(Blob),
           'original': relationship(TrackOriginal),
       })
