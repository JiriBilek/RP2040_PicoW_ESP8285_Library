# socket.py
#
# MicroPython socket module compatibility layer for ESP8285-based Pico W clones.
# Wraps WiFi.py / EspAtDrv.py to expose the standard socket API.

import WiFi
import EspAtDrv
import utime

AF_INET = 2
SOCK_STREAM = 1
SOCK_DGRAM = 2
IPPROTO_TCP = 6
IPPROTO_UDP = 17
SOL_SOCKET = 1
SO_REUSEADDR = 2


def getaddrinfo(host, port, af=0, type=0, proto=0, flags=0):
    # ESP8285 handles DNS resolution internally in AT+CIPSTART,
    # so we pass the hostname through as-is.
    if type == SOCK_DGRAM:
        return [(AF_INET, SOCK_DGRAM, IPPROTO_UDP, '', (host, port))]
    return [(AF_INET, SOCK_STREAM, IPPROTO_TCP, '', (host, port))]


class socket:
    def __init__(self, af=AF_INET, type=SOCK_STREAM, proto=0):
        self._client = WiFi.Client()
        self._type = type
        self._host = None
        self._port = None
        self._ssl = False
        self._connected = False
        self._timeout = None  # None = blocking
        self._server = None   # WiFi.Server for listening sockets
        self._bind_port = 0
        self._udp_linkId = EspAtDrv.NO_LINK

    def connect(self, address):
        host, port = address
        self._host = host
        self._port = port
        self._do_connect()

    def _do_connect(self):
        if self._connected:
            return
        if self._type == SOCK_DGRAM:
            linkId = EspAtDrv.connectUDP(self._host, self._port, self._bind_port)
            if linkId == EspAtDrv.NO_LINK:
                raise OSError("UDP connection failed")
            self._udp_linkId = linkId
            self._client.linkId = linkId
            self._client.assigned = True
            self._connected = True
        elif self._ssl:
            ok = self._client.connectSSL(self._host, self._port)
            if not ok:
                raise OSError("SSL connection failed")
            self._connected = True
        else:
            ok = self._client.connect(self._host, self._port)
            if not ok:
                raise OSError("Connection failed")
            self._connected = True

    def bind(self, address):
        _, port = address
        self._bind_port = port

    def listen(self, backlog=1):
        if self._type != SOCK_STREAM:
            raise OSError("listen only supported on TCP sockets")
        self._server = WiFi.Server(self._bind_port)
        self._server.begin()

    def accept(self):
        if self._server is None:
            raise OSError("Socket not listening")
        start = utime.ticks_ms()
        while True:
            cli = self._server.available()
            if cli is not None:
                cs = socket()
                cs._client = cli
                cs._connected = True
                cs._type = SOCK_STREAM
                # Query remote address
                info = EspAtDrv.cipStatusQuery(cli.linkId)
                addr = (info[0], info[1]) if info else ('0.0.0.0', 0)
                return (cs, addr)
            if self._timeout is not None:
                if self._timeout == 0:
                    raise OSError(11)  # EAGAIN
                if utime.ticks_diff(utime.ticks_ms(), start) > int(self._timeout * 1000):
                    raise OSError(110)  # ETIMEDOUT
            utime.sleep_ms(50)

    def setsockopt(self, level, optname, value):
        pass  # silently accept, no real implementation possible

    def send(self, data):
        if isinstance(data, str):
            data = data.encode()
        if self._type == SOCK_DGRAM:
            if self._udp_linkId == EspAtDrv.NO_LINK:
                raise OSError("Not connected")
            return EspAtDrv.sendDataUDP(self._udp_linkId, data)
        if not self._connected:
            raise OSError("Not connected")
        self._client.txBuffer += data
        self._client.flush()
        return len(data)

    def sendto(self, data, address):
        if isinstance(data, str):
            data = data.encode()
        host, port = address
        if self._udp_linkId == EspAtDrv.NO_LINK:
            # Auto-connect for UDP sendto
            self._host = host
            self._port = port
            self._do_connect()
        return EspAtDrv.sendDataUDP(self._udp_linkId, data, host, port)

    def sendall(self, data):
        self.send(data)

    def write(self, data):
        return self.send(data)

    def recv(self, bufsize):
        if self._type == SOCK_DGRAM:
            return self._udp_recv(bufsize)
        if not self._connected:
            raise OSError("Not connected")
        start = utime.ticks_ms()
        while self._client.available() == 0:
            if not self._client.connected():
                self._connected = False
                return b''
            if self._timeout is not None:
                if self._timeout == 0:
                    return b''
                if utime.ticks_diff(utime.ticks_ms(), start) > int(self._timeout * 1000):
                    raise OSError(110)  # ETIMEDOUT
            utime.sleep_ms(10)
        data = self._client.readBuf(bufsize)
        if not data and not self._client.connected():
            self._connected = False
        return data

    def recvfrom(self, bufsize):
        data = self.recv(bufsize)
        return (data, (self._host or '0.0.0.0', self._port or 0))

    def _udp_recv(self, bufsize):
        if self._udp_linkId == EspAtDrv.NO_LINK:
            raise OSError("Not connected")
        start = utime.ticks_ms()
        while EspAtDrv.availData(self._udp_linkId) == 0:
            if self._timeout is not None:
                if self._timeout == 0:
                    return b''
                if utime.ticks_diff(utime.ticks_ms(), start) > int(self._timeout * 1000):
                    raise OSError(110)  # ETIMEDOUT
            utime.sleep_ms(10)
        return EspAtDrv.recvData(self._udp_linkId, bufsize)

    def read(self, size=-1):
        if size == -1 or size is None:
            result = b''
            while True:
                chunk = self.recv(1024)
                if not chunk:
                    break
                result += chunk
            return result
        return self.recv(size)

    def readline(self):
        line = b''
        while True:
            ch = self.recv(1)
            if not ch:
                break
            line += ch
            if ch == b'\n':
                break
        return line

    def readinto(self, buf, nbytes=None):
        if nbytes is None:
            nbytes = len(buf)
        data = self.recv(nbytes)
        n = len(data)
        buf[:n] = data
        return n

    def close(self):
        if self._server is not None:
            self._server.end()
            self._server = None
        if self._type == SOCK_DGRAM and self._udp_linkId != EspAtDrv.NO_LINK:
            EspAtDrv.close(self._udp_linkId, True)
            self._udp_linkId = EspAtDrv.NO_LINK
        elif self._connected:
            self._client.stop()
        self._connected = False

    def settimeout(self, value):
        self._timeout = value

    def setblocking(self, flag):
        self._timeout = None if flag else 0

    def makefile(self, mode="rb", buffering=0):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
