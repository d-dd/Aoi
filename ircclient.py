from ConfigParser import SafeConfigParser
from twisted.internet.protocol import ClientFactory
from twisted.application import service, internet
from twisted.words.protocols import irc
from twisted.internet import reactor
from twisted.logger import Logger

config = SafeConfigParser()
config.read('settings.ini')
cfg = dict(config.items('irc'))
cfg['secure'] = config.getboolean('irc', 'secure')
config = None

class IrcProtocol(irc.IRCClient):
    log = Logger()
    heartbeatInterval = 30
    nickname = cfg['nick']
    
    def signedOn(self):
        self.log.info("Signed onto network!")
        self.factory.con = self
        self.join(cfg['channel'])

    def privmsg(self, user, channel, msg):
        self.log.info("Message from %s in %s: %s" % (user, channel, msg))
        self.factory.service.parent.recIrcMsg(msg)

class IrcFactory(ClientFactory):
    protocol = IrcProtocol

    def __init__(self, service):
        """
        service is the reference of service instance
        """
        self.service = service
        self.con = None
        
class IrcService(service.Service):
    def startService(self):
        if not all ((cfg['network'], cfg['port'], 
                     cfg['nick'], cfg['channel'])):
            print "Config is incomplete.."
            return
        if self.running:
            print "Service is already running!"
            return
        self.running = 1
        if cfg['secure']:
            print "secure port!"
            from twisted.internet.ssl import ClientContextFactory
            self.r = reactor.connectSSL(cfg['network'], int(cfg['port']),
                                    IrcFactory(self), ClientContextFactory())
        else:
            print "non secure port!"
            self.r = reactor.connectTCP(cfg['network'], int(cfg['port']),
                                    IrcFactory(self))
