# network.py
#
# MicroPython network module compatibility layer for ESP8285-based Pico W clones.
# Wraps WiFi.py / EspAtDrv.py to expose the standard network.WLAN API.

import WiFi

STA_IF = 0
AP_IF = 1

STAT_IDLE = 0
STAT_CONNECTING = 1
STAT_WRONG_PASSWORD = -3
STAT_NO_AP_FOUND = -2
STAT_CONNECT_FAIL = -1
STAT_GOT_IP = 3


class WLAN:
    def __init__(self, interface):
        self._if = interface
        self._active = False

    def active(self, state=None):
        if state is None:
            return self._active
        if state:
            self._active = WiFi.init(0)
        else:
            self._active = False
        return self._active

    def connect(self, ssid, key=None, *, bssid=None):
        if self._if == AP_IF:
            WiFi.beginAP(ssid, key)
        else:
            WiFi.begin(ssid, key, bssid)

    def disconnect(self):
        if self._if == AP_IF:
            WiFi.endAP()
        else:
            WiFi.disconnect(False)

    def isconnected(self):
        s = WiFi.status()
        if self._if == AP_IF:
            return s in (WiFi.WL_AP_LISTENING, WiFi.WL_AP_CONNECTED)
        return s == WiFi.WL_CONNECTED

    def status(self, param=None):
        if param == 'rssi':
            return WiFi.rssi()
        if param is not None:
            raise ValueError("unknown status param")
        s = WiFi.status()
        if s == WiFi.WL_CONNECTED:
            return STAT_GOT_IP
        if s == WiFi.WL_CONNECT_FAILED:
            return STAT_CONNECT_FAIL
        if s == WiFi.WL_CONNECTION_LOST:
            return STAT_CONNECT_FAIL
        return STAT_IDLE

    def ifconfig(self, config=None):
        if config is not None:
            ip, subnet, gw, dns = config
            WiFi.config(ip, dns, gw, subnet)
            return
        # fetch IP info in one AT command instead of three
        import EspAtDrv
        q = EspAtDrv.staIpQuery()
        ip = q[0] if q else '0.0.0.0'
        subnet = q[2] if q else '0.0.0.0'
        gw = q[1] if q else '0.0.0.0'
        dns = WiFi.dnsIp(1) or '0.0.0.0'
        return (ip, subnet, gw, dns)

    def config(self, *args, **kwargs):
        if args:
            param = args[0]
            if param == 'channel':
                return WiFi.channel()
            if param == 'rssi':
                return WiFi.rssi()
            if param == 'mac':
                mac_str = WiFi.macAddress()
                if mac_str:
                    return bytes(int(x, 16) for x in mac_str.split(':'))
                return None
            if param == 'ssid':
                return WiFi.ssid()
            if param == 'hostname':
                return WiFi.hostName()
        if 'hostname' in kwargs:
            WiFi.hostName(kwargs['hostname'])
            return
        if 'channel' in kwargs:
            pass  # channel set only during AP begin
        raise ValueError("unknown config param")

    def scan(self):
        results = WiFi.scanNetworks()
        # Return format: [(ssid, bssid_bytes, channel, rssi, security, hidden), ...]
        out = []
        for ssid, mac, ch, rssi, ecn in results:
            try:
                bssid = bytes(int(x, 16) for x in mac.split(':'))
            except:
                bssid = b'\x00' * 6
            out.append((ssid, bssid, ch, rssi, ecn, False))
        return out
