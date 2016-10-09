import json
from twisted.application import service
from twisted.logger import Logger
from ConfigParser import SafeConfigParser
from twisted.internet.protocol import ReconnectingClientFactory
from autobahn.twisted.websocket import WebSocketClientProtocol,\
                                WebSocketClientFactory

config = SafeConfigParser()
config.read('settings.ini')
cfg = dict(config.items('cytube'))
#cfg['secure'] = config.getboolean('irc', 'secure')
config = None

class CyProtocol(WebSocketClientProtocol):
    log = Logger()
    def __init__(self):
        super(WebSocketClientProtocol, self).__init__()

    def heartbeat(self):
        self.sendMessage("2")

    def onOpen(self):
        self.factory.con = self
        self.factory.service.parent.cy = True
        from twisted.internet import reactor
        from twisted.internet import task
        print "handshake okay"
        self.pulse = task.LoopingCall(self.heartbeat)
        self.pulse.start(10.0)
        self.sendMessage("2probe")
        self.sendMessage("5")
        reactor.callLater(2, self.login)# {)"scale", "cdefgab")

    def onMessage(self, msg, binary):
        print msg

    def login(self):#, user, pw):
        print "let's log in..."
        user = cfg['username']
        pw = cfg['pw']
        self.sendf({"name": "login",
                    "args": {"name": user, "pw": pw}})
        self.sendf({'name': 'joinChannel', 'args': {'name':'teto'}})
        self.sendf({'name': 'initUserPLCallbacks', 'args': {}})
        self.sendf({'name': 'listPlaylists', 'args': {}})


    def sendf(self, fdict):
        fname = json.dumps(fdict["name"])
        fdata = json.dumps(fdict["args"])
        frame = "42[%s, %s]" % (fname, fdata)
        print frame
        self.sendMessage(frame)

    def shutdown(self):
        self.sendClose()
        self.factory.service.parent.doneCleanup('cy')
        # Disable Factory from reconnecting
        self.factory.maxRetries = 0

class WsFactory(WebSocketClientFactory, ReconnectingClientFactory):
    """
    Websocket Factory with auto-reconnect.
    There is a chance that server could have moved servers.
    If so, the Factory will keep trying to connect to the old server,
    so it is also necessary to check channel.json.
    """

    protocol = CyProtocol
    
    def __init__(self, ws, service):
        super(WsFactory, self).__init__(ws)
        self.ws = ws
        self.con = None
        self.service = service

    def startedConnecting(self, connector):
        print "!!!!!!!!!!!!!Started to connect to Cytube..."

class WSService(service.Service):
    log = Logger()
    def errCatch(self, err):
        self.log.error(err.getBriefTraceback())

    def startService(self):
        if self.running:
            self.log.error("Service is already running. Only one instance allowed.")
            return
        self.running = 1
        d = self.getWsUrl()
        d.addCallbacks(self.cbGetWsUrl, self.errCatch)
        d.addCallbacks(self.cbMakeWsUrl, self.errCatch)
        d.addCallbacks(self.connectCy, self.errCatch)

    def connectCy(self, ws):
        self.log.info("the websocket address is %s" % ws)
        from autobahn.twisted.websocket import connectWS
        wsFactory = WsFactory(ws, self)
        self.f = wsFactory
        self.r = connectWS(wsFactory)

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
        servers = json.loads(response)
        wsurl = None
        for server in servers.get('servers'):
            if server.get('secure') is secure:
                wsurl = server.get('url')
                wsurl = wsurl.replace('http', 'ws', 1)
                wsurl += "/socket.io/?transport=websocket"
                break
        return wsurl
    
