# -*- coding: utf-8 -*-
# @author: RaNaN

from __future__ import with_statement

import logging
import os
import shutil
import time

import pycurl

from pyload.network.HTTPChunk import ChunkInfo, HTTPChunk
from pyload.network.HTTPRequest import BadHeader
from pyload.plugin.Plugin import Abort
from pyload.utils import fs_join, fs_encode


class HTTPDownload(object):
    """ loads a url http + ftp """

    def __init__(self, url, filename, get={}, post={}, referer=None, cj=None, bucket=None,
                 options={}, progress=None, disposition=False):
        self.url = url
        self.filename = filename  #: complete file destination, not only name
        self.get = get
        self.post = post
        self.referer = referer
        self.cj = cj  #: cookiejar if cookies are needed
        self.bucket = bucket
        self.options = options
        self.disposition = disposition
        # all arguments

        self.abort = False
        self.size = 0
        self.nameDisposition = None  #: will be parsed from content disposition

        self.chunks = []

        self.log = logging.getLogger("log")

        try:
            self.info = ChunkInfo.load(filename)
            self.info.resume = True  #: resume is only possible with valid info file
            self.size = self.info.size
            self.infoSaved = True
        except IOError:
            self.info = ChunkInfo(filename)

        self.chunkSupport = True
        self.m = pycurl.CurlMulti()

        # needed for speed calculation
        self.lastArrived = []
        self.speeds = []
        self.lastSpeeds = [0, 0]

        self.progress = progress


    @property
    def speed(self):
        last = [sum(x) for x in self.lastSpeeds if x]
        return (sum(self.speeds) + sum(last)) / (1 + len(last))


    @property
    def arrived(self):
        return sum([c.arrived for c in self.chunks])


    @property
    def percent(self):
        return (self.arrived * 100) / self.size if self.size else 0

    def _copyChunks(self):
        init = fs_encode(self.info.getChunkName(0))  #: initial chunk name

        if self.info.getCount() > 1:
            with open(init, "rb+") as fo:  #: first chunkfile
                for i in xrange(1, self.info.getCount()):
                    # input file
                    fo.seek(
                        self.info.getChunkRange(i - 1)[1] + 1)  #: seek to beginning of chunk, to get rid of overlapping chunks
                    fname = fs_encode("%s.chunk%d" % (self.filename, i))
                    with open(fname, "rb") as fi:
                        buf = 32 * 1024
                        while True:  #: copy in chunks, consumes less memory
                            data = fi.read(buf)
                            if not data:
                                break
                            fo.write(data)
                    if fo.tell() < self.info.getChunkRange(i)[1]:
                        reshutil.move(init)
                        self.info.remove()  #: there are probably invalid chunks
                        raise Exception("Downloaded content was smaller than expected. Try to reduce download connections.")
                    reshutil.move(fname)  #: remove chunk

        if self.nameDisposition and self.disposition:
            self.filename = fs_join(os.path.dirname(self.filename), self.nameDisposition)

        shutil.move(init, fs_encode(self.filename))
        self.info.remove()  #: remove info file


    def download(self, chunks=1, resume=False):
        """ returns new filename or None """

        chunks = max(1, chunks)
        resume = self.info.resume and resume

        try:
            self._download(chunks, resume)
        except pycurl.error, e:
            # code 33 - no resume
            code = e.args[0]
            if resume is True and code == 33:
                # try again without resume
                self.log.debug("Errno 33 -> Restart without resume")

                # remove old handles
                for chunk in self.chunks:
                    self.closeChunk(chunk)

                return self._download(chunks, False)
            else:
                raise
        finally:
            self.close()

        if self.nameDisposition and self.disposition:
            return self.nameDisposition
        return None


    def _download(self, chunks, resume):
        if not resume:
            self.info.clear()
            self.info.addChunk("%s.chunk0" % self.filename, (0, 0))  #: create an initial entry
            self.info.save()

        self.chunks = []

        init = HTTPChunk(0, self, None, resume)  #: initial chunk that will load complete file (if needed)

        self.chunks.append(init)
        self.m.add_handle(init.getHandle())

        lastFinishCheck = 0
        lastTimeCheck = 0
        chunksDone = set()  #: list of curl handles that are finished
        chunksCreated = False
        done = False
        if self.info.getCount() is 0:  #: This is a resume, if we were chunked originally assume still can
            self.chunkSupport = False

        while 1:
            # need to create chunks
            if not chunksCreated and self.chunkSupport and self.size:  #: will be setted later by first chunk

                if not resume:
                    self.info.setSize(self.size)
                    self.info.createChunks(chunks)
                    self.info.save()

                chunks = self.info.getCount()

                init.setRange(self.info.getChunkRange(0))

                for i in xrange(1, chunks):
                    c = HTTPChunk(i, self, self.info.getChunkRange(i), resume)

                    handle = c.getHandle()
                    if handle:
                        self.chunks.append(c)
                        self.m.add_handle(handle)
                    else:
                        # close immediatly
                        self.log.debug("Invalid curl handle -> closed")
                        c.close()

                chunksCreated = True

            while 1:
                ret, num_handles = self.m.perform()
                if ret != pycurl.E_CALL_MULTI_PERFORM:
                    break

            t = time.time()

            # reduce these calls
            while lastFinishCheck + 0.5 < t:
                # list of failed curl handles
                failed = []
                ex = None  #: save only last exception, we can only raise one anyway

                num_q, ok_list, err_list = self.m.info_read()
                for c in ok_list:
                    chunk = self.findChunk(c)
                    try:  #: check if the header implies success, else add it to failed list
                        chunk.verifyHeader()
                    except BadHeader, e:
                        self.log.debug("Chunk %d failed: %s" % (chunk.id + 1, str(e)))
                        failed.append(chunk)
                        ex = e
                    else:
                        chunksDone.add(c)

                for c in err_list:
                    curl, errno, msg = c
                    chunk = self.findChunk(curl)
                    # test if chunk was finished
                    if errno != 23 or "0 !=" not in msg:
                        failed.append(chunk)
                        ex = pycurl.error(errno, msg)
                        self.log.debug("Chunk %d failed: %s" % (chunk.id + 1, str(ex)))
                        continue

                    try:  #: check if the header implies success, else add it to failed list
                        chunk.verifyHeader()
                    except BadHeader, e:
                        self.log.debug("Chunk %d failed: %s" % (chunk.id + 1, str(e)))
                        failed.append(chunk)
                        ex = e
                    else:
                        chunksDone.add(curl)
                if not num_q:  #: no more infos to get

                    # check if init is not finished so we reset download connections
                    # note that other chunks are closed and downloaded with init too
                    if failed and init not in failed and init.c not in chunksDone:
                        self.log.error(_("Download chunks failed, fallback to single connection | %s" % (str(ex))))

                        # list of chunks to clean and remove
                        to_clean = filter(lambda x: x is not init, self.chunks)
                        for chunk in to_clean:
                            self.closeChunk(chunk)
                            self.chunks.remove(chunk)
                            reshutil.move(fs_encode(self.info.getChunkName(chunk.id)))

                        # let first chunk load the rest and update the info file
                        init.resetRange()
                        self.info.clear()
                        self.info.addChunk("%s.chunk0" % self.filename, (0, self.size))
                        self.info.save()
                    elif failed:
                        raise ex

                    lastFinishCheck = t

                    if len(chunksDone) >= len(self.chunks):
                        if len(chunksDone) > len(self.chunks):
                            self.log.warning("Finished download chunks size incorrect, please report bug.")
                        done = True  #: all chunks loaded

                    break

            if done:
                break  #: all chunks loaded

            # calc speed once per second, averaging over 3 seconds
            if lastTimeCheck + 1 < t:
                diff = [c.arrived - (self.lastArrived[i] if len(self.lastArrived) > i else 0) for i, c in
                        enumerate(self.chunks)]

                self.lastSpeeds[1] = self.lastSpeeds[0]
                self.lastSpeeds[0] = self.speeds
                self.speeds = [float(a) / (t - lastTimeCheck) for a in diff]
                self.lastArrived = [c.arrived for c in self.chunks]
                lastTimeCheck = t
                self.updateProgress()

            if self.abort:
                raise Abort

            # time.sleep(0.003)  #: supress busy waiting - limits dl speed to (1 / x) * buffersize
            self.m.select(1)

        for chunk in self.chunks:
            chunk.flushFile()  #: make sure downloads are written to disk

        self._copyChunks()


    def updateProgress(self):
        if self.progress:
            self.progress(self.percent)


    def findChunk(self, handle):
        """ linear search to find a chunk (should be ok since chunk size is usually low) """
        for chunk in self.chunks:
            if chunk.c == handle:
                return chunk


    def closeChunk(self, chunk):
        try:
            self.m.remove_handle(chunk.c)
        except pycurl.error, e:
            self.log.debug("Error removing chunk: %s" % str(e))
        finally:
            chunk.close()


    def close(self):
        """ cleanup """
        for chunk in self.chunks:
            self.closeChunk(chunk)

        self.chunks = []
        if hasattr(self, "m"):
            self.m.close()
            del self.m
        if hasattr(self, "cj"):
            del self.cj
        if hasattr(self, "info"):
            del self.info
