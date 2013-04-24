#!/usr/bin/env python
'''
--------------------
@author: Moloch
@copyright: GPLv3
@version: 0.1
--------------------
'''

import re
import os
import sys
import time
import thread
import logging
import sqlite3
import ConfigParser


from models import dbsession, create_tables, Share
from argparse import ArgumentParser
from string import ascii_letters, digits
from twisted.application import internet
from twisted.words.protocols import irc
from twisted.internet import reactor, protocol


### Channel
class ChannelSettings(object):

    isMuted = False

    def __init__(self, name, password=None, ignore=False):
        if name[0] == '&' or ignore:
            self.name = name
        else: 
            self.name = "#" + name
        if password is None or password.lower() == '__none__':
            self.password = None
        else:
            self.password = password

    def __eq__(self, other):
        return self.name == str(other)

    def __ne__(self, other):
        return not self == other

    def __str__(self):
        return self.name

### Bot
class BTSyncBot(irc.IRCClient):
    '''
    IRC Bot
    '''

    nickname = "btsync"
    realname = "btsync"
    channels = {}
    isMuted = False
    defaults = {
        'level': 'debug',
        'nickname': "btsync",
        'realname': "btsync",
    }
    addShareParser = ArgumentParser()

    def initialize(self):
        ''' 
        Because twisted is fucking stupid and won't let you use super/init 
        '''
        self.public_commands = {
            "!help": self.help,
            "!mute": self.muteBot,
            "!stfu": self.muteBot,
            "!addshare": self.addShare,
            "!search": self.search,
            "!getshare": self.getShare,
            "!search": self.search
        }
        self.addShareParser.add_argument('--name', nargs='*')
        self.addShareParser.add_argument('--key', nargs='?')
        self.addShareParser.add_argument('--description', nargs='*')


    def __dbinit__(self):
        ''' Initializes the SQLite database '''
        logging.info("Initializing SQLite db ...")
        if not os.path.exists('btsyncbot.db'):
            logging.info("Creating SQLite tables")
            dbConn = sqlite3.connect("btsyncbot.db")
            dbConn.close()
            create_tables()

    def config(self, filename="btsyncbot.cfg"):
        ''' Load settings from config file '''
        logging.info('Loading config from: %s' % filename)
        config = ConfigParser.SafeConfigParser(self.defaults)
        config.readfp(open(filename, 'r'))
        self.__logging__(config)
        self.__system__(config)
        self.__channels__(filename)

    def __logging__(self, config):
        ''' Configure logging module '''
        logLevel = config.get("Logging", 'level')
        if logLevel.lower() == 'debug':
            logging.getLogger().setLevel(logging.DEBUG)
        elif logLevel.lower().startswith('warn'):
            logging.getLogger().setLevel(logging.WARNING)
        elif logLevel.lower() == 'error':
            logging.getLogger().setLevel(logging.ERROR)
        elif logLevel.lower() == 'critical':
            logging.getLogger().setLevel(logging.CRITICAL)
        else:
            logging.getLogger().setLevel(logging.INFO)


    def __system__(self, config):
        ''' Configure system settings '''
        self.nickname = config.get("System", 'nickname')
        logging.info('Config system bot nickname (%s)' % self.nickname)
        self.realname = config.get("System", 'realname')
        logging.info('Config system bot realname (%s)' % self.realname)

    def __channels__(self, filename):
        ''' Read channels to join from config file '''
        config = ConfigParser.SafeConfigParser()
        config.readfp(open(filename, 'r'))
        self.channel_pairs = config.items("Channels")

    def connectionMade(self):
        ''' When we make a succesful connection to a server '''
        irc.IRCClient.connectionMade(self)

    def connectionLost(self, reason):
        ''' Auto-reconnect on dropped connections '''
        irc.IRCClient.connectionLost(self, reason)
        logging.warn("Disconnected from server: %s" % str(reason))

    def signedOn(self):
        ''' Called when bot has succesfully signed on to server '''
        self.__dbinit__()
        if not 0 < len(self.channel_pairs):
            logging.warning("No channels to join.")
        for key_pair in self.channel_pairs:
            channel = ChannelSettings(key_pair[0], key_pair[1])
            self.channels[channel.name] = channel
            if channel.password is None:
                self.join(channel.name)
            else:
                self.join(channel.name, channel.password)

    def joined(self, channel):
        ''' Called when the bot joins the channel '''
        logging.info("Joined channel %s" % channel)
        self.display(self.nickname, channel, "My name is %s, I have come to destroy you." % self.nickname)

    def alterCollidedNick(self, nickname):
        ''' Avoids name collisions '''
        logging.info("Nickname collision; chaned to: " + nickname + '^')
        return nickname + '^'

    def privmsg(self, user, channel, msg):
        ''' This will get called when the bot receives a message '''
        user = user.split('!', 1)[0].lower()
        if channel == self.nickname:
            logging.debug("Private message received; response channel is '%s'" % (user,))
            channel = user
        if msg.startswith("!"):
            self.parseCommand(user, channel, msg)
        else:
            logging.debug("[Message]: <User: %s> <Channel: %s> <Msg: %s>" % (user, channel, msg))

    def parseCommand(self, user, channel, msg):
        ''' Call whatever function corisponds to the command '''
        command = msg.split(" ")[0]
        msg = ' '.join(msg.split(' ')[1:])
        if command in self.public_commands:
            logging.debug("[Command]: <User: %s> <Channel: %s> <Msg: %s>" % (user, channel, msg))
            self.public_commands[command](user, channel, msg)

    def addShare(self, user, channel, msg):
        args = self.addShareParser.parse_args(msg.split())
        share = Share(
            name=' '.join(args.name).lower(), 
            private_key=args.key.upper(), 
            description=' '.join(args.description)
        )
        dbsession.add(share)
        dbsession.flush()
        acceptMessage = "Succesfully added new share '%s' to database" % share.name
        self.display(user, channel, acceptMessage)

    def getShare(self, user, channel, msg):
        share = Share.by_name(msg.lower())
        if share is not None:
            self.display(user, channel, " %s: %s" % (share.name, share.private_key))
        else:
            self.display(user, channel, "No share found.")

    def search(self, user, channel, msg):
        logging.info("Searching for '%s'" % msg)
        shares = Share.by_search(msg)
        if shares is None or 0 == len(shares):
            self.display(user, channel, "No results found")
        elif len(shares) <= 5:
            self.display(user, channel, "Found %d results" % len(shares))
            for share in shares:
                self.display(user, channel, " %s: %s" % (share.name, share.description))
        else:
            self.display(user, channel, "Too many results")

    def muteBot(self, user, channel, msg):
        ''' Toggle mute on/off '''
        channelSettings = self.channels.get(channel, None)
        if channelSettings is not None:
            if channelSettings.isMuted:
                channelSettings.isMuted = False
                self.display(user, channel, "Mute: OFF - Responses will be public")
            else:
                self.display(user, channel, "Mute: ON - Responses will be private")
                channelSettings.isMuted = True
        else:
            self.display(user, channel, "Cannot mute this channel.")

    def display(self, user, channel, message, whisper=False):
        ''' Intelligently wraps msg, based on mute setting '''
        channelSettings = self.channels.get(channel, None)
        if whisper or (channelSettings is not None and channelSettings.isMuted):
            displayChannel = user
        else:
            displayChannel = channel
        self.msg(displayChannel, message.encode('ascii', 'ignore'))

    def joinChannel(self, user, channel, msg):
        ''' Admin command to get bot to join channel '''
        joinChan = msg.split(" ")
        if len(joinChan) < 2: joinChan.append(None)
        channel = ChannelSettings(joinChan[0], joinChan[1])
        self.channels[channel.name] = channel
        if channel.password is None:
            self.join(channel.name)
        else:
            self.join(channel.name, channel.password)
        logging.info("Joined channel %s" % channel.name)

    def help(self, user, channel, msg):
        ''' Displays a helpful message '''
        self.display(user, channel, " > Commands: BTSync Bot ", whisper=True)
        self.display(user, channel, "-------------------------------------", whisper=True)



### Factory
class BTSyncBotFactory(protocol.ClientFactory):
    '''
    Twisted IRC bot factory
    '''

    def buildProtocol(self, addr):
        ''' Creates factory '''
        bot = BTSyncBot()
        bot.initialize()
        bot.config(self.configFilename)
        logging.info("BTSync IRC Bot Starting...")
        bot.factory = self
        return bot

    def clientConnectionLost(self, connector, reason):
        ''' If we get disconnected, reconnect to server. '''
        connector.connect()

    def clientConnectionFailed(self, connector, reason):
        ''' When connection fails '''
        logging.warn("Connection failed: " + str(reason))
        reactor.stop()

### Main
if __name__ == '__main__':
    logging.basicConfig(
        format = '\r\033[1m[%(levelname)s]\033[0m %(asctime)s - %(message)s', 
        level=logging.INFO)
    factory = BTSyncBotFactory()
    if 1 < len(sys.argv):
        parser = ArgumentParser(
            description="BTSync key sharing IRC bot.")
        parser.add_argument("server",
            metavar="SERVER",
            help="IRC server to connect to.")
        parser.add_argument("-p", "--port",
            type=int,
            default=6667,
            dest='port',
            help="Port number to connect to.")
        parser.add_argument("-c", "--config",
            metavar="CONFIG",
            default="btsyncbot.cfg",
            dest="configFilename",
            help="Path to config file.")
        args = parser.parse_args()   
        factory.configFilename = args.configFilename
        reactor.connectTCP(args.server, args.port, factory)
    elif os.path.exists("btsyncbot.cfg"):
        config = ConfigParser.SafeConfigParser({'port': '6667'})
        config.readfp(open("btsyncbot.cfg", 'r'))
        factory.configFilename = "btsyncbot.cfg"
        server = config.get("Server", 'domain')
        port = config.getint("Server", 'port')
        reactor.connectTCP(server, port, factory)
    else:
        print 'No config file or args; see --help'
        os._exit(1)
    reactor.run()
