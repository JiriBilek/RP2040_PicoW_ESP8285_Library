# Wifi.py
#
# Based on source: https://github.com/jandrassy/WiFiEspAT
#
# Version:
#  0.1.0: initial version

from micropython import const
import EspAtDrv

WL_NO_SHIELD = const(255)
WL_NO_MODULE = WL_NO_SHIELD
WL_IDLE_STATUS = const(0)
WL_CONNECTED = const(1)
WL_CONNECT_FAILED = const(2)
WL_CONNECTION_LOST = const(3)
WL_DISCONNECTED = const(4)
WL_AP_LISTENING = const(5)
WL_AP_CONNECTED = const(6)
WL_AP_FAILED = const(7)

###################################

class Client:
    def __init__(self):
        self.linkId  = EspAtDrv.NO_LINK
        self.port = 0
        self.assigned = False
        self.rxBuffer = b''
        self.txBuffer = b''

    def connect(self, host: str, port: int) -> int:
        return self.connectInternal("TCP", host, port)

    def connectSSL(self, host: str, port: int) -> int:
        return self.connectInternal("SSL", host, port)

    def connectInternal(self, protocol: str, host: str, port: int) -> int:
        global clientPool
        
        linkId = EspAtDrv.connect(protocol, host, port)
        if (linkId == EspAtDrv.NO_LINK):
            return False;

        self.linkId = linkId
        self.port = port
        self.assigned = True
        clientPool[linkId] = self

        EspAtDrv.LOG_INFO_PRINT();
        EspAtDrv.LOG_INFO_PRINT(f'Connected {host} at port {port} and client\'s linkId {linkId}\r\n')

        return True

    def connected(self) -> int:
        if (self.linkId == EspAtDrv.NO_LINK):
            return False
        if (EspAtDrv.connected(self.linkId) or self.available()):  # Arduino WiFi library examples expect connected true while data are available
            return True

        # link is closed and all data from stream are read
        _clientFree(self)
        return False

    def stop(self):
        self.flush()
        self.abort()

    def flush(self):
        if (self.linkId != EspAtDrv.NO_LINK):
            if (self.txBuffer):
                EspAtDrv.sendData(self.linkId, self.txBuffer)
                # TODO: check all the data has been sent
        self.txBuffer = b''

    def abort(self):
        if (self.linkId != EspAtDrv.NO_LINK):
            EspAtDrv.close(self.linkId, True)  # close abort

        _clientFree(self)
        
    def print(self, data: str) -> int:
        if (self.linkId == EspAtDrv.NO_LINK):
            return 0

        if (len(data) == 0):
            return 0

        self.txBuffer += data.encode()  # copy data to internal buffer - only utf-8 supported
        return len(self.txBuffer)

    def available(self) -> int:
        avail = len(self.rxBuffer)
        if (self.linkId == EspAtDrv.NO_LINK):
            return avail;

        if (avail == 0):
            avail = EspAtDrv.availData(self.linkId)

        if (avail == 0):
            self.flush()  # maybe sketch is waiting for response without flushing the request

        return avail

    def read(self) -> int:
        if (self.linkId == EspAtDrv.NO_LINK):
            return -1
        if (self.available() == 0):
            return -1;

        b = self.readBuf(1)
        if (len(b) < 1):
            return -1

        return b[0]

    def readBuf(self, size: int) -> bytes:
        if (size == 0 or self.available() == 0):
            return b''

        # copy from internal buffer
        if (len(self.rxBuffer) == 0):
            self.rxBuffer = EspAtDrv.recvData(self.linkId)  # TODO: max buffer size

        b = self.rxBuffer[:size]
        self.rxBuffer = self.rxBuffer[size:]

        if (len(b) >= size):  # the buffer was filled
            return b
        
        return b + self.readBuf(size - len(b))  # handle the rest of provided buffer

    def peek(self) -> int:
        if (self.linkId == EspAtDrv.NO_LINK or self.available() == 0):
            return -1

        # copy from internal buffer
        if (len(self.rxBuffer) == 0):
            self.rxBuffer = EspAtDrv.recvData(self.linkId)  # TODO: max buffer size

        return self.rxBuffer[0]

        
# TODO
#    def status(self) -> int:
#    def remoteIp(self):
#    def remotePort(self):
#    def localPort(self):
        
###################################

class Server:
    def __init__(self, port: int):
        self._port = port
        self._started = False
    
    def begin(self, timeout: int = 30):
        if (EspAtDrv.startServer(self._port, timeout)):
            self._started = True
    
    def end(self):
        if (self._started):
            EspAtDrv.stopServer()
            self._started = False
    
    def setTimeout(self, timeout: int):
        EspAtDrv.serverTimeout(timeout)
    
    def available(self) -> Client:
        linkId = EspAtDrv.getIncomingLinkId()
        if (linkId == EspAtDrv.NO_LINK):
            return None
        cli = Client()
        cli.linkId = linkId
        cli.assigned = True
        clientPool[linkId] = cli
        return cli

###################################

clientPool = []
state = WL_NO_MODULE
    
def init(resetType: int = EspAtDrv.WIFI_SOFT_RESET) -> int:
    global clientPool, state
    
    for i in range(EspAtDrv.LINKS_COUNT):
        clientPool.append(Client())
        
    ok = EspAtDrv.init(resetType)
    state = WL_NO_MODULE if ok == False else WL_IDLE_STATUS
    return ok
        
def _clientFree(cli: Client):
    cli.linkId = EspAtDrv.NO_LINK
    cli.assigned = False
    cli.port = 0
    cli.rxBuffer = b''
    cli.txBuffer = b''

def status() -> int:
    global state
    
    if (state == WL_NO_MODULE):
        return state
    
    res = EspAtDrv.staStatus()
    if (res == -1):
        if (EspAtDrv.getLastErrorCode() in
            (EspAtDrv.Error_NOT_INITIALIZED, EspAtDrv.Error_AT_NOT_RESPONDING)):
            state = WL_NO_MODULE
        else:  # some temporary error?
            pass  # no change
    elif (res in (2, 3, 4)):
        state = WL_CONNECTED;
    elif (res in (0, 1, 5)):  # inactive, idle, STA disconnected
        if (state == WL_CONNECT_FAILED):
            pass  # no change
        elif (state == WL_CONNECTED):
            state = WL_CONNECTION_LOST
        else:
            state = WL_DISCONNECTED
            
    return state;

def begin(ssid: str, passphrase: str, bssid: bytearray = None):
    global state
    
    ok = EspAtDrv.joinAP(ssid, passphrase, bssid)
    state = WL_CONNECTED if ok else WL_CONNECT_FAILED
    return state

def disconnect(persistent: int) -> int:
    global state
    
    if (EspAtDrv.quitAP(persistent)):
        state = WL_DISCONNECTED
    return state

def setPersistent(persistent: int) -> int:
    return EspAtDrv.sysPersistent(persistent)

def rssi() -> int:
    q = EspAtDrv.apQuery()
    if (not q):
        return None
    return int(q[3])

def channel() -> int:
    q = EspAtDrv.apQuery()
    if (not q):
        return None
    return int(q[2])

def localIp() -> str:
    q = EspAtDrv.staIpQuery()
    if (not q):
        return None
    return q[0]

def gatewayIp() -> str:
    q = EspAtDrv.staIpQuery()
    if (not q):
        return None
    return q[1]

def subnetMask() -> str:
    q = EspAtDrv.staIpQuery()
    if (not q):
        return None
    return q[2]

def dnsIp(n: int = None):
    q = EspAtDrv.dnsQuery()
    if (not q):
        return None
    if (not n):
        return q
    return q[n-1]

def autoConnect(autoconnect: int) -> int:
    return EspAtDrv.autoConnect(autoconnect)

def config(localIp: str, dnsServer: str = None, gateway: str = None, subnet: str = None):
    if (localIp):
        EspAtDrv.setStaticIp(localIp, gateway, subnet)
    if (dnsServer):
        EspAtDrv.setDns(dnsServer)

def setDns(dnsServer1: str, dnsServer2: str = None):
    return EspAtDrv.setDns(dnsServer1, dnsServer2)

def hostName(name: str = None) -> str:
    if (name):
        EspAtDrv.setHostname(name)
        return name
    return EspAtDrv.getHostname()

def macAddress() -> str:
    return EspAtDrv.staMacQuery()

def dhcpIsEnabled() -> int:
    # AT firmware doesn't provide a query for this; assume enabled by default
    return True

def ssid() -> str:
    return EspAtDrv.ssidQuery()

def bssid() -> str:
    return EspAtDrv.bssidQuery()

def scanNetworks() -> list:
    return EspAtDrv.scanAP()

def beginAP(ssid: str, password: str = None, channel: int = 1, enc: int = 0) -> int:
    global state
    if (password and enc == 0):
        enc = 4  # WPA2_PSK
    ok = EspAtDrv.beginAP(ssid, password, channel, enc)
    state = WL_AP_LISTENING if ok else WL_AP_FAILED
    return state

def endAP(persistent: int = False):
    global state
    if (EspAtDrv.setWifiMode(EspAtDrv.WIFI_MODE_STA, persistent)):
        state = WL_DISCONNECTED
