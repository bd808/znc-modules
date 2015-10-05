#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# ZNC pong module
# Copyright (c) 2015 Bryan Davis and contributors.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

import collections
import re
import shlex
import time
import znc


class CmdHandler(object):
    """Helper for ZNC OnModCommand message handling.

    Inspired by:
    - https://github.com/crocket/PyZeroMsgSend/blob/master/ZeroMsgSend.py
    """
    class _Cmd(object):
        """A registered command."""
        def __init__(self, callback, args, desc):
            self.callback = callback
            self.args = args
            self.desc = desc

    def __init__(self, module):
        self._mod = module
        self._cmds = collections.OrderedDict()
        self._cmds['help'] = self._Cmd(self._cmdHelp, '', '')

    def _showHelp(self, name):
        if name in self._cmds:
            cmd = self._cmds[name]
            self._mod.PutModule('{} {}'.format(name, cmd.args))
            self._mod.PutModule(cmd.desc)
        else:
            self._mod.PutModule('Unknown command "{}".'.format(name))

    def _cmdHelp(self, args):
        if len(args) > 0:
            self._showHelp(args[0])
            return

        for name in self._cmds.keys():
            if name == 'help':
                continue
            self._showHelp(name)
            self._mod.PutModule('------------------------------')

    def addCmd(self, name, callback, args, desc):
        self._cmds[name] = self._Cmd(callback, args, desc)

    def __call__(self, args):
        parsed = shlex.split(args)
        cmd = parsed[0]
        if cmd in self._cmds:
            self._cmds[cmd].callback(parsed[1:])
        else:
            self._mod.PutModule('Unknown command "{}".'.format(cmd))


class pong(znc.Module):
    """Ping auto-responder

    Check irc messages to see if they match a configured regular expression.
    When matching messages are found, respond with a canned message.

    The default regex looks for messages like:
    - {own_nick}: ping
    - {own_nick}, ping?
    - {own_nick}, around?
    - {own_nick}, yt?
    - {own_nick}, are you there

    It responds with:
    PRIVMSG {channel} {nick}: Please ask your question and I will respond when
    I am around or maybe somebody else can help.

    Inspired by:
    - http://err.no/src/contentless_ping.pl
    - https://github.com/maxandersen/znc-modules/blob/master/antiping.py
    """
    description = "Ping answering machine"

    CHANNEL_RE = r'{own_nick}[,:] (ping|around|yt|((are )?you)? there)[!?.]?$'
    PRIVATE_RE = r'(ping|around|yt|((are )?you )?there)[!?.]?$'
    CHANNEL_ACTION = (
            'PRIVMSG {channel} :{nick}: Please ask your question and '
            'I will respond when I am around or maybe somebody else can help.'
        )
    PRIVATE_ACTION = (
            'PRIVMSG {nick} :Please ask your question and '
            'I will respond when I am around or maybe somebody else can help.'
        )

    def OnLoad(self, arg, msg):
        self._limits = {}
        self._cmdHandler = CmdHandler(self)
        self._cmdHandler.addCmd(
            'channel_re', self._cmdChannelRe, 'REGEX',
            'Set regex to treat as a ping in active channels')
        self._cmdHandler.addCmd(
            'chanel_action', self._cmdChannelAction, 'FORMAT',
            'Set format string to use to generate channel ping response')
        self._cmdHandler.addCmd(
            'private_re', self._cmdPrivateRe, 'REGEX',
            'Set regex to treat as a ping in private message')
        self._cmdHandler.addCmd(
            'private_action', self._cmdPrivateAction, 'FORMAT',
            'Set format string to use to generate private ping response')
        self._cmdHandler.addCmd(
            'status', self._cmdStatus, '',
            'Show current settings')
        return True

    def OnModCommand(self, cmd):
        self._cmdHandler(cmd)

    def OnChanMsg(self, message):
        self._handleMsg(
            message.GetNick().GetNick(),
            message.GetChan().GetName(),
            message.GetText().s,
            self._getChannelRe(),
            self._getChannelAction())
        return znc.CONTINUE

    def OnPrivMsg(self, nick, message):
        self._handleMsg(
            message.GetNick().GetNick(),
            message.GetNick().GetNick(),
            message.GetText().s,
            self._getPrivateRe(),
            self._getPrivateAction())
        return znc.CONTINUE

    def _cmdChannelRe(self, args):
        if len(args) > 0:
            self.nv['channel_re'] = args[0]

    def _getChannelRe(self):
        if 'channel_re' not in self.nv:
            self.nv['channel_re'] = self.CHANNEL_RE
        return self.nv['channel_re']

    def _cmdPrivateRe(self, args):
        if len(args) > 0:
            self.nv['private_re'] = args[0]

    def _getPrivateRe(self):
        if 'private_re' not in self.nv:
            self.nv['private_re'] = self.PRIVATE_RE
        return self.nv['private_re']

    def _cmdChannelAction(self, args):
        if len(args) > 0:
            self.nv['channel_action'] = args[0]

    def _getChannelAction(self):
        if 'channel_action' not in self.nv:
            self.nv['channel_action'] = self.CHANNEL_ACTION
        return self.nv['channel_action']

    def _cmdPrivateAction(self, args):
        if len(args) > 0:
            self.nv['private_action'] = args[0]

    def _getPrivateAction(self):
        if 'private_action' not in self.nv:
            self.nv['private_action'] = self.PRIVATE_ACTION
        return self.nv['private_action']

    def _cmdStatus(self, args):
        fmt = '{:<15} : {}'
        self.PutModule(fmt.format('channel_re', self._getChannelRe()))
        self.PutModule(fmt.format('channel_action', self._getChannelAction()))
        self.PutModule(fmt.format('private_re', self._getPrivateRe()))
        self.PutModule(fmt.format('private_action', self._getPrivateAction()))

    def _handleMsg(self, nick, channel, message, regex, action):
        subs = {
                'nick': re.escape(nick),
                'channel': re.escape(channel),
                'own_nick': re.escape(self.GetNetwork().GetCurNick()),
            }

        if re.match(regex.format(**subs), message, re.I|re.M):
            now = time.time()
            limit = now - 300
            if nick not in self._limits or self._limits[nick] < limit:
                self.PutIRC(action.format(**subs))
                self._limits[nick] = now

            for k, v in self._limits.items():
                if v < limit:
                    del self._limits[k]
