import random
import time
import itertools
import gevent
import urlparse
from ireul.helpers.net import resolve_netloc
from gevent import socket
from mutagen.ogg import OggPage
from mutagen.oggvorbis import OggVorbisInfo, TryNextPage
from mutagen._vorbis import VCommentDict, VComment
from cStringIO import StringIO

compose = lambda *fx: reduce(lambda f, g: lambda *args, **kwargs: f(g(*args, **kwargs)), fx)

def create_metadata_packet(tags):
    vc = VComment()
    vc.extend(tags)
    return "\x03vorbis"+vc.write()

def yield_pages(track_derived):
    fh = track_derived.open()
    yield OggPage(fh)
    tmp = OggPage(fh)
    # replace outgoing tag
    tmp.packets[0] = create_metadata_packet([
        ('title', track_derived.original.title),
        ('artist', track_derived.original.artist),
        ('x-ireul-id', unicode(track_derived.id))])
    yield tmp
    try:
        while True:
            yield OggPage(fh)
    except EOFError:
        pass

def ogg_show_page(input_page_stream):
    for page in input_page_stream:
        print repr(page)
        yield page

def ogg_make_pos_monotonic(input_page_stream):
    track_offset = None
    last_pos = 0
    for page in input_page_stream:
        if page.position == 0: # starting a new track
            track_offset = last_pos
        page.position = last_pos = track_offset + page.position
        yield page

def ogg_make_seq_monotonic(input_page_stream):
    seq_ctr = itertools.count()
    for page in input_page_stream:
        page.sequence = next(seq_ctr)
        yield page

def ogg_make_single_serial(input_page_stream):
    serial = random.randint(0, 2**32)
    for page in input_page_stream:
        page.serial = serial
        yield page

def ogg_fix_header(input_page_stream):
    yield next(input_page_stream)
    for page in input_page_stream:
        page.first = False
        yield page

def monitor_position(input_page_stream):
    page = next(input_page_stream)
    yield page
    t_initial = time.time()
    prev_pos = page.position
    time_sum = 0
    for page in input_page_stream:
        delta = page.position - prev_pos
        time_sum += float(delta)/44100
        wall_clock_delta = time.time() - t_initial - float(page.position)/44100
        print "serial=%d pos=%d time_delta=%.3fs pos_delta = %d samples, %0.3fs"  % (
                page.serial, page.position, wall_clock_delta, delta, float(delta)/44100)
        prev_pos = page.position
        yield page
    print "total position = %d" % prev_pos
    print "total time = %dm:%02.2fs" % divmod(time_sum, 60)

def apply_timing(input_page_stream):
    time_initial = time.time()
    for page in input_page_stream:
        real_time = time.time() - time_initial
        play_time = float(page.position)/44100
        print "sleeping %r" % max(0.0, play_time - real_time)
        gevent.sleep(max(0.0, play_time - real_time))
        yield page

def monitor_info_pages(input_page_stream):
    for page in input_page_stream:
        try:
            ovi = OggVorbisInfo(None, page=page)
            #print "OggVorbisInfo = %r" % ovi
        except TryNextPage: pass
        yield page


def send_stream(url, source_file_iter):
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
    conn.send("SOURCE {mount} HTTP/1.0\r\n".format(mount=parse_result.path))
    conn.send("Authorization: Basic c291cmNlOmNvY2ttZQ==\r\n")
    conn.send("HOST: {hostname}\r\n".format(hostname=hostname))
    conn.send("User-Agent: ireul\r\n")
    conn.send("Content-Type: application/ogg\r\n")
    conn.send("\r\n")

    fileobj = conn.makefile()
    fileobj.readline()
    fileobj.readline()


    ogg_stream_pre = compose(
            ogg_make_seq_monotonic,
            ogg_make_single_serial,
            )

    ogg_stream_post = compose(
            monitor_position,
            apply_timing,
            ogg_show_page,
            # ogg_fix_header,
            ogg_make_pos_monotonic,
            )

    # get all the pages
    def stream_pages():
        for track_derived in source_file_iter:
            for page in ogg_stream_pre(yield_pages(track_derived)):
                yield page

    # apply transforms and write them out
    for page in ogg_stream_post(stream_pages()):
        fileobj.write(page.write())
