=========
ChangeLog
=========

Users should ignore this content: **it is draft**.

Contributors should add entries here in the following section, on top of the
others.

`WIP (coming releases)`
=======================

New Features
------------

* When a message upload/download fails, we do not abort the whole folder
  synchronization, but only skip that message, informing the user at the
  end of the sync run.
 
Changes
-------

* Reworked Thread monitoring, simplifying the code. The 'downside', we
  might use up to 0.5 seconds more until we notice that all threads
  finished.

Bug Fixes
---------



Pending for the next major release
==================================

* UIs get shorter and nicer names. (API changing)
