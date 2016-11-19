import json
import time
from twisted.application import service
from twisted.logger import Logger
from ConfigParser import SafeConfigParser
from twisted.internet.protocol import ReconnectingClientFactory
from autobahn.twisted.websocket import WebSocketClientProtocol,\
                                WebSocketClientFactory

config = SafeConfigParser()
config.read('settings.ini')
cfg = dict(config.items('cytube'))
config = None

class CyProtocol(WebSocketClientProtocol):
    log = Logger()
    def __init__(self):
        super(WebSocketClientProtocol, self).__init__()
        self.lastPulse = time.time()
        self.isLoggedIn = False
        self.isInRoom = False
        self.rank = -1

    def heartbeat(self):
        """Send a heartbeat to the server.
        The server will reply with a '3'."""
        self.sendMessage("2")
        # check for last pulse - if interval is larger than specified,
        # assume connection is lost.
        if time.time() - self.lastPulse > 30:
            self.log.warning("No pulse from server... dropping connection")
            self.dropConnection()

    def receivedPulse(self):
        self.lastPulse = time.time()
        #self.log.debug("Received pulse at %s" % self.lastPulse)

    def onOpen(self):
        self.factory.con = self
        self.factory.service.parent.cy = True
        from twisted.internet import reactor
        from twisted.internet import task
        print "handshake okay"
        self.pulse = task.LoopingCall(self.heartbeat)
        self.pulse.start(10.0)

    def onConnect(self, response):
        pass

    def onMessage(self, msg_s, binary):
        #self.log.debug(u"{msg_s}", msg_s=msg_s)
        #print type(msg_s)
        msg = msg_s.decode('utf8')
        #self.log.debug(u"{msg!r}", msg=msg)
        if msg == "3":
            self.receivedPulse()
            return
        elif msg.startswith("42"):
            try:
                msg = json.loads(msg[2:])
            except(ValueError):
                self.log.error("Received non-json frame!")
                return
        fname = msg[0]
        if len(msg) > 1:
            fargs = msg[1]
        else:
            fargs = None
        self.processFrame(fname, fargs)

    def processFrame(self, fname, fargs):
        """
        Send cytube frames to their corresponding methods.
        E.g. method `_cy_chatMsg` is called when receving
        chatMsg frame
        """
        cycall = '_cy_{}'.format(fname)
        thunk = getattr(self, cycall, None)
        if thunk is not None:
            thunk(fname, fargs)
        else:
            self.log.info("Unhandled {fname!r}:{fargs!r}",fname=fname, fargs=fargs)

    def login(self):#, user, pw):
        print "let's log in..."
        user = cfg['username']
        pw = cfg['pw']
        self.sendf({"name": "login",
                    "args": {"name": user, "pw": pw}})
        self.sendf({'name': 'joinChannel', 'args': {'name':'teto'}})
       # self.sendf({'name': 'initUserPLCallbacks', 'args': {}})
       # self.sendf({'name': 'listPlaylists', 'args': {}})

    def sendf(self, fdict):
        fname = json.dumps(fdict["name"])
        fdata = json.dumps(fdict["args"])
        frame = "42[%s, %s]" % (fname, fdata)
        print frame
        self.sendMessage(frame)

    def dropConnection(self):
        """ Clean up Cytube instance and drops the connection.
        Use when you want factory to reconnect. """
        self.sendClose()
        
    def shutdown(self):
        self.sendClose()
        self.factory.service.parent.doneCleanup('cy')
        # Disable Factory from reconnecting
        self.factory.maxRetries = 0

    def connectionLost(self, reason):
        print "~~~~~~~~~~~~~~~~~~CONNECTION LOST~~~~~~~~~~~~~~~~~~~~~~~~~~"
        self.factory.service.checkChannelConfig(self.factory.ws)

    def _cy_chatMsg(self, fname, fargs):
        username = fargs['username'].encode('utf8')
        msg = fargs['msg'].encode('utf8')
        #self.log.debug("[{}] {}: {}".format(fname, username, msg))
        self.log.info("{name!r}:{msg!r}",name=username, msg=msg)

    def _cy_rank(self, fname, fargs):
        self.rank = fargs
        self.log.debug("Set rank to %i" % fargs)
        if not self.isLoggedIn and fargs == -1:
            self.login()

    def _cy_login(self, fname, fargs):
        if fargs['success']:
            self.isLoggedIn = True
            self.log.debug("Successfully logged %s on cytube" % fargs['name'])

    def _cy_addUser(self, fname, fargs):
        self.userlist.append(fargs)

    def _cy_emoteList(self, fname, fargs):
        pass

    def _cy_setPermissions(self, fname, fargs):
        pass

    def _cy_channelCSSJS(self, fname, fargs):
        pass
    
    def _cy_channelOpts(self, fname, fargs):
        pass

    def _cy_setMotd(self, fname, fargs):
        pass

    def _cy_userlist(self, fname, fargs):
        # Use userlist frame to determine if bot is in the room or not.
        self.isInRoom = True
        self.userlist = fargs

    def _cy_drinkCount(self, fname, fargs):
        pass

    def _cy_setPlaylistLocked(self, fname, fargs):
        pass
    
    def _cy_setPlaylistMeta(self, fname, fargs):
        pass





class WsFactory(WebSocketClientFactory, ReconnectingClientFactory):
    """
    Websocket Factory with auto-reconnect.
    There is a chance that cytube could have moved servers.
    If so, the Factory will keep trying to connect to the old server,
    so it is also necessary to check channel.json.
    """

    protocol = CyProtocol
    initialDelay = 0
    maxDelay = 60 * 3
    
    def __init__(self, ws, service):
        super(WsFactory, self).__init__(ws)
        self.ws = ws
        self.con = None
        self.service = service

    def startedConnecting(self, connector):
        print "!!!!!!!!!!!!!Started to connect to Cytube..."

    def connectionLost(self, connector, reason):
        print "~~~~~~~~~~~~~~~~~~CONNECTION LOST~~~~~~~~~~~~~~~~~~~~~~~~~~"
        self.service.checkChannelConfig(self.ws)

class WSService(service.Service):
    log = Logger()
    def errCatch(self, err):
        self.log.error(err.getBriefTraceback())

    def checkChannelConfig(self, currentWsUrl):
        d = self.getWsUrl()
        d.addCallbacks(self.cbGetWsUrl, self.errCatch)
        d.addCallbacks(self.cbMakeWsUrl, self.errCatch)
        d.addCallback(self.cbCompareWsUrls, currentWsUrl)

    def cbCompareWsUrls(self, newWsUrl, currentWsUrl):
        """
        Comapres the ws url currently used by factory,
        to the one served at channel.json.
        If they are different, we restart the factory.
        Otherwise, if they are the same, or no response
        from the server, do nothing and let 
        ReconnectingClientFactory try to reconnect.
        """

        self.log.info("comparing WSURLS!")
        if newWsUrl != currentWsUrl and newWsUrl is not None:
            self.log.info("The ws changed to %s!" % newWsUrl)
            self.f.maxRetries = 0
            self.f.stopTrying()
            self.f = None
            self.connectCy(newWsUrl)
        elif newWsUrl is None:
            self.log.info("Failed to retrieve servers from channel.json")
        else:
            self.log.info("The ws didn't change!")

    def startService(self):
        if self.running:
            self.log.error("Service is already running. Only one instance allowed.")
            return
        self.running = 1
        d = self.getchannelurl()
        d.addCallbacks(self.connectCy, self.errCatch)

    def getchannelurl(self):
        d = self.getWsUrl()
        d.addCallbacks(self.cbGetWsUrl, self.errCatch)
        d.addCallbacks(self.cbMakeWsUrl, self.errCatch)
        return d

    def connectCy(self, ws):
        self.log.info("the websocket address is %s" % ws)
        from autobahn.twisted.websocket import connectWS
        wsFactory = WsFactory(ws, self)
        self.f = wsFactory
        connectWS(wsFactory)

    def stopService(self):
        self.running = 0

    def getWsUrl(self):
        url = "https://{}/socketconfig/{}.json".format(cfg['hostname'], cfg['channel'])
        self.log.info("Sending GET for ws servers url: " + url)
        from twisted.web.client import Agent, readBody
        from twisted.internet import reactor
        agent = Agent(reactor)
        d = agent.request('GET', url)
        return d

    def cbGetWsUrl(self, response):
        from twisted.web.client import readBody
        if response.code == 200:
            self.log.debug('200 response')
            return readBody(response)

    def cbMakeWsUrl(self, response, secure=True):
        """
         response : string json list of servers
          secure: Boolean, wss or ws
        """
        if not response:
            return

        servers = json.loads(response)
        wsurl = None
        for server in servers.get('servers'):
            if server.get('secure') is secure:
                wsurl = server.get('url')
                wsurl = wsurl.replace('http', 'ws', 1)
                wsurl += "/socket.io/?transport=websocket"
                break
        return wsurl
