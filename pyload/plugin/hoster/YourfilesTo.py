# -*- coding: utf-8 -*-

import re
import urllib

from pyload.plugin.Hoster import Hoster


class YourfilesTo(Hoster):
    __name    = "YourfilesTo"
    __type    = "hoster"
    __version = "0.22"

    __pattern = r'http://(?:www\.)?yourfiles\.(to|biz)/\?d=\w+'

    __description = """Youfiles.to hoster plugin"""
    __license     = "GPLv3"
    __authors     = [("jeix", "jeix@hasnomail.de"),
                       ("skydancer", "skydancer@hasnomail.de")]


    def process(self, pyfile):
        self.pyfile = pyfile
        self.prepare()
        self.download(self.get_file_url())


    def prepare(self):
        if not self.file_exists():
            self.offline()

        self.pyfile.name = self.get_file_name()

        wait_time = self.get_waiting_time()
        self.setWait(wait_time)
        self.wait()


    def get_waiting_time(self):
        if not self.html:
            self.download_html()

        # var zzipitime = 15;
        m = re.search(r'var zzipitime = (\d+);', self.html)
        if m:
            sec = int(m.group(1))
        else:
            sec = 0

        return sec


    def download_html(self):
        url = self.pyfile.url
        self.html = self.load(url)


    def get_file_url(self):
        """ returns the absolute downloadable filepath
        """
        url = re.search(r"var bla = '(.*?)';", self.html)
        if url:
            url = url.group(1)
            url = urllib.unquote(url.replace("http://http:/http://", "http://").replace("dumdidum", ""))
            return url
        else:
            self.error(_("Absolute filepath not found"))


    def get_file_name(self):
        if not self.html:
            self.download_html()

        return re.search("<title>(.*)</title>", self.html).group(1)


    def file_exists(self):
        """ returns True or False
        """
        if not self.html:
            self.download_html()

        if re.search(r"HTTP Status 404", self.html):
            return False
        else:
            return True
