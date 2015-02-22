# -*- coding: utf-8 -*-

import re

from pyload.plugin.internal.CaptchaService import ReCaptcha
from pyload.plugin.internal.SimpleHoster import SimpleHoster


class ZippyshareCom(SimpleHoster):
    __name    = "ZippyshareCom"
    __type    = "hoster"
    __version = "0.73"

    __pattern = r'http://www\d{0,2}\.zippyshare\.com/v(/|iew\.jsp.*key=)(?P<KEY>[\w^_]+)'

    __description = """Zippyshare.com hoster plugin"""
    __license     = "GPLv3"
    __authors     = [("Walter Purcaro", "vuolter@gmail.com")]


    COOKIES = [("zippyshare.com", "ziplocale", "en")]

    NAME_PATTERN    = r'("\d{6,}/"[ ]*\+.+?"/|<title>Zippyshare.com - )(?P<N>.+?)("|</title>)'
    SIZE_PATTERN    = r'>Size:.+?">(?P<S>[\d.,]+) (?P<U>[\w^_]+)'
    OFFLINE_PATTERN = r'>File does not exist on this server'

    LINK_PREMIUM_PATTERN = r'document.location = \'(.+?)\''


    def setup(self):
        self.chunkLimit     = -1
        self.multiDL        = True
        self.resumeDownload = True


    def handleFree(self, pyfile):
        recaptcha   = ReCaptcha(self)
        captcha_key = recaptcha.detect_key()

        if captcha_key:
            try:
                self.link = re.search(self.LINK_PREMIUM_PATTERN, self.html)
                recaptcha.challenge()

            except Exception, e:
                self.error(e)

        else:
            self.link = '/'.join(("d", self.info['pattern']['KEY'], str(self.get_checksum()), self.pyfile.name))


    def get_checksum(self):
        try:
            b1 = eval(re.search(r'\.omg = (.+?);', self.html).group(1))
            b2 = eval(re.search(r'\* \((.+?)\)', self.html).group(1))
            checksum = b1 * b2 + 18

        except Exception:
            self.error(_("Unable to calculate checksum"))

        else:
            return checksum
