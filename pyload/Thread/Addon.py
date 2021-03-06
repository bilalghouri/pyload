# -*- coding: utf-8 -*-
# @author: RaNaN

import Queue
import copy
import os
import sys
import time
import traceback

from pyload.Thread.Plugin import PluginThread


class AddonThread(PluginThread):
    """thread for addons"""

    def __init__(self, m, function, args, kwargs):
        """Constructor"""
        PluginThread.__init__(self, m)

        self.f = function
        self.args = args
        self.kwargs = kwargs

        self.active = []

        m.localThreads.append(self)

        self.start()


    def getActiveFiles(self):
        return self.active


    def addActive(self, pyfile):
        """ Adds a pyfile to active list and thus will be displayed on overview"""
        if pyfile not in self.active:
            self.active.append(pyfile)


    def finishFile(self, pyfile):
        if pyfile in self.active:
            self.active.remove(pyfile)

        pyfile.finishIfDone()


    def run(self):
        try:
            try:
                self.kwargs['thread'] = self
                self.f(*self.args, **self.kwargs)
            except TypeError, e:
                # dirty method to filter out exceptions
                if "unexpected keyword argument 'thread'" not in e.args[0]:
                    raise

                del self.kwargs['thread']
                self.f(*self.args, **self.kwargs)
        finally:
            local = copy.copy(self.active)
            for x in local:
                self.finishFile(x)

            self.m.localThreads.remove(self)
