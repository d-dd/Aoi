# Aoi (unfinished)
[unfinished][in progress] Cytube bot written in Python (Twisted)

yuk.py is a `twistd` application file.  
See [documentation](https://twistedmatrix.com/documents/current/core/howto/application.html#core-howto-application-twistd) for more information.

Usage exampe:  

To start in shell without daemonizing:  
````
twistd -noy yuk.py
`````
With log file output:  
````
twistd -noy yuk.py --logfile log.log
````

## Depenencies
Twisted  
Autobahn  
(below for SSL)  
Cryptography    
pyOpenSSL  
service-identity


## Manhole
````
telnet localhost 8181
````
Username/Password is defined in pw.txt  
The top parent service is `service`.  

Example usage to disconnect cytube service.
````
>>>service.getServiceNamed('cy').f.con.sendClose()
````
`f` is WsFactory instance  
`con` is the protocol instance  

