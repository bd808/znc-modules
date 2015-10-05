bd808's ZNC modules
===================

Modules for [ZNC](http://wiki.znc.in/ZNC)

pong.py
-------

Respond to pings with a canned message. The default configuration looks for
pings that do not include any message of substance (e.g. "ping!") and responds
with a prompt for the sender to go ahead and ask their question.

### Installation
* Copy `pong.py` to ZNC modules directory.
* `/znc LoadMod modpython`
* `/znc LoadMod pong`
* `/msg *pong status`
