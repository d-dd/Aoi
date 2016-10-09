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
