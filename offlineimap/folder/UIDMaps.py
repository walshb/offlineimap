# Base folder support
# Copyright (C) 2002 John Goerzen
# <jgoerzen@complete.org>
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
from __future__ import with_statement # needed for python 2.5
from threading import Lock
from IMAP import IMAPFolder
from offlineimap import OfflineImapError
import os.path
try: # python 2.6 has set() built in
    set
except NameError:
    from sets import Set as set


class MappedIMAPFolder(IMAPFolder):
    """IMAP class to map between Folder() instances where both side assign a uid

    This Folder is used on the local side, while the remote side should
    be an IMAPFolder.

    If new functions are added to the IMAPFolder backend, this backend
    also needs to add new functions translating calls to the RUID to use
    the LUID instead.

    Instance variables (self.): r2l: dict mapping message uids:
      self.r2l[remoteuid]=localuid"""

    def __init__(self, *args, **kwargs):
        super(MappedIMAPFolder, self).__init__(*args, **kwargs)
        self.maplock = Lock() # protect mapping file

    def _getmapfilename(self):
        """Absolute path of where we store the UID mapping file"""
        return os.path.join(self.repository.getmapdir(),
                            self.getfolderbasename())
        
    def _loadmaps(self):
        """Load the mapping file and return a R2L UID mapping dict

        :returns: Dict with {RUID:LUID, RUID2:LUID2,...} or raises
            OfflineImapError at servity REPO (if e.g the Mapping file
            could not be found)"""
        r2l = {}
        severity = OfflineImapError.ERROR.REPO
        with self.maplock:
            mapfilename = self._getmapfilename()
            if not os.path.exists(mapfilename):
                raise OfflineImapError("UID Mapping file for folder '%s', repos"
                    "itory '%s' not found." % (self, self.repository),
                                       severity)
            with open(mapfilename, 'rt') as file:
                for line in file:
                    line = line.strip()
                    if not len(line):
                        break #skip empty lines
                    try:
                        (Luid, Ruid) = map(long, line.split(':'))
                    except ValueError:
                        raise OfflineImapError("Corrupt line '%s' in UID mappin"
                            "g file, folder '%s' (repository '%s')" %
                                           (line, folder, self.repository),
                                           severity)
                    r2l[Ruid] = Luid
        return r2l

    def _savemaps(self):
        mapfilename = self._getmapfilename()
        self.maplock.acquire()
        try:
            with open(mapfilename + ".tmp", 'wt') as file:
                for ruid, luid in self.r2l.iteritems():
                    if ruid > 0: # only write out already synced mappings
                        file.write("%d:%d\n" % (ruid, luid))
            os.rename(mapfilename + '.tmp', mapfilename)
        finally:
            self.maplock.release()

    def ruids_to_luids(self, Ruidlist):
        """Given a list of remote UIDs, returns a list of local UIDs"""
        return [self.r2l[Ruid] for Ruid in Ruidlist]

    def cachemessagelist(self):
        """While cachmessagelist operates, the self.r2l is not stable
        and should not yet be accessed by other threads."""
        # populate self.messagelist{'uid':{'uid','flags','time'},...}, with uid
        # being the local uid, but still missing out the remote UID
        super(MappedIMAPFolder, self).cachemessagelist()
        self.r2l = self._loadmaps()
        # assign negative rUIDs to new local items without known remote UID.
        nextneg = -1
        for luid in set(self.messagelist.keys()) - set(self.r2l.values()):
            # exists locally but no know remote ID:
            ruid = nextneg
            nextneg -= 1
            self.r2l[ruid] = luid

        # delete entries where local items have disappeared, ie mapping
        # exists but local IMAP has no entry
        for ruid, luid in self.r2l.items():
            #not using  iterator so we can delete keys while iterating
            if luid not in self.messagelist:
                # exists in r2l but not locally, delete
                del self.r2l[ruid]

    def uidexists(self, ruid):
        """Checks if the (remote) UID exists in this Folder"""
        # This implementation overrides the one in BaseFolder, as it is
        # much more efficient for the mapped case.
        return ruid in self.r2l

    def getmessageuidlist(self):
        """Gets a list of (remote) UIDs.
        You may have to call cachemessagelist() before calling this function!"""
        # This implementation overrides the one in BaseFolder, as it is
        # much more efficient for the mapped case.
        return self.r2l.keys()

    def getmessagecount(self):
        """Gets the number of messages in this folder.
        You may have to call cachemessagelist() before calling this function!"""
        # This implementation overrides the one in BaseFolder, as it is
        # much more efficient for the mapped case.
        return len(self.r2l)

    def getmessagelist(self):
        """Gets the current message list. This function's implementation
        is quite expensive for the mapped UID case.  You must call
        cachemessagelist() before calling this function!"""

        retval = {}
        self.maplock.acquire()
        try:
            for luid, value in localhash.iteritems():
                value = value.copy()
                value['uid'] = self.l2r[value['uid']]
                retval[key] = value
        finally:
            self.maplock.release()
        return retval

    def getmessage(self, ruid):
        """Returns the content of the specified message."""
        return super(MappedIMAPFolder, self).getmessage(self.r2l[ruid])

    def savemessage(self, ruid, content, flags, rtime):
        """Writes a new message, with the specified uid.

        The UIDMaps class will not return a newly assigned uid, as it
        internally maps different uids between IMAP servers. So a
        successful savemessage() invocation will return the same uid it
        has been invoked with. As it maps between 2 IMAP servers which
        means the source message must already have an uid, it requires a
        positive uid to be passed in. Passing in a message with a
        negative uid will do nothing and return the negative uid.

        If the uid is > 0, the backend should set the uid to this, if it can.
        If it cannot set the uid to that, it will save it anyway.
        It will return the uid assigned in any case.
        """
        # Mapped UID instances require the source to already have a
        # positive UID, so simply return here.
        if ruid < 0:
            return ruid

        #if msg uid already exists, just modify the flags
        if self.uidexists(ruid):
            self.savemessageflags(ruid, flags)
            return ruid

        newluid = super(MappedIMAPFolder, self)\
            .savemessage(-1, content, flags, rtime)
        if newluid < 1:
            #TODO Offlineimaperror, better make IMAPFolder throw an error
            raise ValueError("Backend could not find uid for message")
        self.r2l[ruid] = newluid
        self._savemaps()
        return ruid

    def getmessageflags(self, ruid):
        return super(MappedIMAPFolder, self).getmessageflags(self.r2l[ruid])

    def getmessagetime(self, ruid):
        return self.messagelist[self.r2l[ruid]]['time']

    def savemessageflags(self, ruid, flags):
        return super(MappedIMAPFolder, self).savemessageflags(self.r2l[ruid],
                                                              flags)
    def addmessageflags(self, ruid, flags):
        return super(MappedIMAPFolder, self).addmessageflags(self.r2l[ruid],
                                                              flags)
    def addmessagesflags(self, ruidlist, flags):
        return super(MappedIMAPFolder, self).addmessagesflags(
            self.ruids_to_luids(ruidlist), flags)

    def _delete_mapping(self, ruidlist):
        """Delete mapping of a bunch of remote UIDS"""
        needssave = 0
        for ruid in uidlist:
            del self.r2l[ruid]
            if ruid > 0:
                # modified our mapping file, save!
                needssave = 1
        if needssave:
            self._savemaps()

    def deletemessageflags(self, ruid, flags):
        return super(MappedIMAPFolder, self).deletemessageflags(self.r2l[ruid],
                                                                flags)

    def deletemessagesflags(self, ruidlist, flags):
        return super(MappedIMAPFolder, self).deletemessagesflags(
            self.ruids_to_luids(ruidlist), flags)

    def processmessagesflags(self, operation, ruidlist, flags):
        return super(MappedIMAPFolder, self).processmessagesflags(
            operation, self.ruids_to_luids(ruidlist), flags)

    def deletemessage(self, ruid):
        return super(MappedIMAPFolder, self).deletemessage(self.r2l[ruid])
        self._delete_mapping([ruid])

    def deletemessages(self, ruidlist):
        return super(MappedIMAPFolder, self).deletemessages(
            self.ruids_to_luids(ruidlist))
        self._delete_mapping(uidlist)
