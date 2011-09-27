# Mailbox name generator
# Copyright (C) 2002-2011 John Goerzen & contributors
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
from __future__ import with_statement
import os.path
import re                               # for folderfilter
from threading import Lock
from CustomConfig import ConfigHelperMixin


class MBWriter(ConfigHelperMixin):
    """Collects and writes out mailbox names, so that mutt can use them"""
    boxes = {}
    """class-wide dict containing a list of foldernames per accountname"""
    mblock = Lock() #prevent concurrent writes

    @classmethod
    def setup(cls, conf, accts):
        """setup all class variables"""
        cls.config = conf
        cls.accounts = accts
        cls.enabled = cls().getconfboolean("enabled", False)

    @classmethod
    def add(cls, accountname, foldername):
        """Add accountname/foldername to self.boxes"""
        if not cls.enabled: return
        if not accountname in cls.boxes:
            cls.boxes[accountname] = []
        if not foldername in MBWriter.boxes[accountname]:
            cls.boxes[accountname].append(foldername)

    @classmethod
    def write(cls):
        # See if we're ready to write it out.
        if not cls.enabled: return
        if [a for a in cls.accounts if a not in cls.boxes]:
            return # not finished yet...
        with MBWriter.mblock:
            # write out names, lock protect against concurrent writes
            MBWriter().gen_names()

    def getconfig(self):
        return MBWriter.config #needed for CustomConfigMixin

    def getsection(self):
        return "mbnames" #needed for CustomConfigMixin

    def gen_names(self):
        """Writes out the list of accounts/foldernames per mbnames
        configuration. Don't call invoke concurrently."""
        leval = self.getconfig().getlocaleval()
        with open(os.path.expanduser(self.getconf("filename")), "wt") as file:
            file.write(leval.eval(self.getconf("header")))
            # folderfilter is a function or None (for disabled)
            folderfilter = leval.eval(self.getconf("folderfilter", "True"),
                                      {'re': re})
            itemlist = []
            for account, folders in MBWriter.boxes.iteritems():
                for folder in folders:
                 if folderfilter == True or folderfilter(account, folder):
                     itemlist.append(self.getconfig().get(
                             self.getsection(), "peritem", raw=1) % \
                                         {'accountname': account,
                                          'foldername': folder})
            file.write(leval.eval(self.getconf("sep")).join(itemlist))
            file.write(leval.eval(self.getconf("footer")))
