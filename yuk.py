#
# home directory not added to sys.path when run with twistd for some reason
# so we add it explicitly here
import os, sys
sys.path.append(os.getcwd())

from ircclient import IrcService
from cyclient import WSService
from twisted.application import service, internet
from twisted.web import static, server
from twisted.internet.defer import Deferred
cwd = os.getcwd()

# Create MultiService, and hook up WebService and Manhole server to it
class BotService(service.MultiService):
        def __init__(self):
            super(BotService, self).__init__()
            self.irc = None
            self.cy = None

        def recIrcMsg(self, msg):
            print "received IRC message to relay"

        def cleanup(self):
            """
            Prepares for shutdown.
            Twisted will wait before exiting due to SystemEventTrigger.
            First, disconnect from services (except manhole)
            Let each service handle their own cleanup.
            The `done` deferred will be fired when everyone is done.
            """
            self.done = Deferred()
            self.getServiceNamed('cy').f.con.shutdown()

            return self.done

        def doneCleanup(self, con):
            """
            Called by services to notify that it is done with its own
            clean up. When everyone is done, we fired the deferred.
            """
            if con == 'irc':
                self.irc = None
            elif con == 'cy':
                self.cy = None
            if not self.irc and not self.cy:
                self.done.callback(None)


topService = BotService()

def getWebService():
    fileServer = server.Site(static.File(os.getcwd()))
    return internet.TCPServer(8080, fileServer)

#application = service.Application("Demo Application")
#web_service = getWebService()
#web_service.setName("webservice")
#web_service.setServiceParent(topService)


ws_service = WSService()
ws_service.setName("cy")
ws_service.setServiceParent(topService)

# Create application
application = service.Application("Yuk Yuk Top")
# Connect MultiService "topService" to the application
topService.setServiceParent(application)

### IRC
irc_service = IrcService()
irc_service.setName("irc")
irc_service.setServiceParent(topService)

## manhole
from twisted.conch import manhole_tap
manhole_service = manhole_tap.makeService({
    "telnetPort": "tcp:8181",
        "sshPort": None,
        "namespace": {"service": topService},
        "passwd": "pw.txt",
        })
manhole_service.setName("manhole")
manhole_service.setServiceParent(topService)
from twisted.internet import reactor
reactor.addSystemEventTrigger('before', 'shutdown', topService.cleanup)
