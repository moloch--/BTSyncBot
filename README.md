BTSyncBot
=========

Share [BTSync](http://labs.bittorrent.com/experiments/sync.html) keys via IRC.


Requirements
==============
 * Python 2.5.x - 2.7.x
 * Python Twisted (pip install twisted)
 * SQL Alchemy (pip install sqlalchemy)

Usage
=============
```
> Commands: BTSync Bot
-------------------------------------
!addshare --name <name> --key <btsync key> --description <description>

!getshare <share name>...................Get a shared key
!search <search term>....................Search shares
!list <username>.........................List all shares by a user
!help....................................Show this helpful message
```
