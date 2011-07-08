# Gmail IMAP repository support
# Copyright (C) 2008 Riccardo Murri <riccardo.murri@gmail.com>
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

from offlineimap.imaputil import imapsplit, flagsplit, dequote
from offlineimap.repository.IMAP import IMAPRepository
from offlineimap import folder, OfflineImapError, imaplib2

class GmailRepository(IMAPRepository):
    """Gmail IMAP repository.

    Falls back to hard-coded gmail host name and port, if none were specified:
    http://mail.google.com/support/bin/answer.py?answer=78799&topic=12814
    """
    # Gmail IMAP server hostname
    HOSTNAME = "imap.gmail.com"
    # Gmail IMAP server port
    PORT = 993
    
    def __init__(self, reposname, account):
        """Initialize a GmailRepository object."""
        # Enforce SSL usage
        account.getconfig().set('Repository ' + reposname,
                                'ssl', 'yes')
        self._special_folders = None #fetched on demand, see below
        """when populated, {'Spam':foldername1, 'AllMail':f2, 'Trash':f3}"""
        IMAPRepository.__init__(self, reposname, account)
        self.get_real_delete_folders()

    def gethost(self):
        """Return the server name to connect to.

        Gmail implementation first checks for the usual IMAP settings
        and falls back to imap.gmail.com if not specified."""
        try:
            return super(GmailRepository, self).gethost()
        except OfflineImapError:
            # nothing was configured, cache and return hardcoded one
            self._host = GmailRepository.HOSTNAME
            return self._host

    def getport(self):
        return GmailRepository.PORT

    def getssl(self):
        return 1

    def getpreauthtunnel(self):
        return None

    def getfoldertype(self):
        return folder.Gmail.GmailFolder

    def getrealdelete(self, foldername):
        # XXX: `foldername` is currently ignored - the `realdelete`
        # setting is repository-wide
        return self.getconfboolean('realdelete', 0)

    def get_real_delete_folders(self):
        """Gmail will really delete messages upon EXPUNGE in these folders

        This populates the list of folders on demand, it we must be able
        to acquire an IMAP connection here"""
        if self._special_folders is None:
            self.get_trashfolder() #populates self._sepcial_folders
        folders = [v for (k,v) in self._special_folders.iteritems() \
                       if k in ['Spam','Trash']]
        return folders

    def get_trashfolder(self):
        """Where mail is moved that should be deleted for real

        This fetches spam and trash folder names on first access, it we
        must potentially be able to acquire an IMAP connection here.
        :returns: name of the trashfolder as string, `None` if none was
        returned or an exception."""
        if self._special_folders != None:
            return self._special_folders.get('Trash', None)
        # Fetch trash and spam folder names
        self._special_folders = {}
        imapobj = self.imapserver.acquireconnection()
        try:
            typ, data = imapobj.xatom('XLIST','""','*')
            #returns 'OK' ['Success'], now get list of folders
            data= imapobj._get_untagged_response('XLIST')
            for folder in data:
                flags, sep, name = imapsplit(folder)
                if '\\Trash' in flags:
                    self._special_folders['Trash'] = dequote(name)
                elif '\\Spam' in flags:
                    self._special_folders['Spam'] = dequote(name)
                elif '\\AllMail' in flags:
                    self._special_folders['AllMail'] = dequote(name)
        except Exception, e:
            raise e #TODO raise OfflineImapError here
        finally:
            self.imapserver.releaseconnection(imapobj)
        return self._special_folders.get('Trash', None)

