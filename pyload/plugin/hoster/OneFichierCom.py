# -*- coding: utf-8 -*-

from pyload.plugin.internal.SimpleHoster import SimpleHoster


class OneFichierCom(SimpleHoster):
    __name    = "OneFichierCom"
    __type    = "hoster"
    __version = "0.84"

    __pattern = r'https?://(?:www\.)?(?:(?P<ID1>\w+)\.)?(?P<HOST>1fichier\.com|alterupload\.com|cjoint\.net|d(es)?fichiers\.com|dl4free\.com|megadl\.fr|mesfichiers\.org|piecejointe\.net|pjointe\.com|tenvoi\.com)(?:/\?(?P<ID2>\w+))?'
    __config  = [("use_premium", "bool", "Use premium account if available", True)]

    __description = """1fichier.com hoster plugin"""
    __license     = "GPLv3"
    __authors     = [("fragonib", "fragonib[AT]yahoo[DOT]es"),
                       ("the-razer", "daniel_ AT gmx DOT net"),
                       ("zoidberg", "zoidberg@mujmail.cz"),
                       ("imclem", ""),
                       ("stickell", "l.stickell@yahoo.it"),
                       ("Elrick69", "elrick69[AT]rocketmail[DOT]com"),
                       ("Walter Purcaro", "vuolter@gmail.com"),
                       ("Ludovic Lehmann", "ludo.lehmann@gmail.com")]


    COOKIES     = [("1fichier.com", "LG", "en")]
    DISPOSITION = False  #: Remove in 0.4.10

    NAME_PATTERN    = r'>FileName :</td>\s*<td.*>(?P<N>.+?)<'
    SIZE_PATTERN    = r'>Size :</td>\s*<td.*>(?P<S>[\d.,]+) (?P<U>[\w^_]+)'
    OFFLINE_PATTERN = r'File not found !\s*<'

    WAIT_PATTERN = r'>You must wait \d+ minutes'


    def setup(self):
        self.multiDL        = self.premium
        self.resumeDownload = True


    def handle_free(self, pyfile):
        id = self.info['pattern']['ID1'] or self.info['pattern']['ID2']
        url, inputs = self.parseHtmlForm('action="https://1fichier.com/\?%s' % id)

        if not url:
            self.fail(_("Download link not found"))

        if "pass" in inputs:
            inputs['pass'] = self.getPassword()

        inputs['submit'] = "Download"

        self.download(url, post=inputs)


    def handle_premium(self, pyfile):
        self.download(pyfile.url, post={'dl': "Download", 'did': 0})
