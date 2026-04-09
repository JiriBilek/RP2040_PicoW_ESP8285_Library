# ssl.py
#
# MicroPython ssl module compatibility layer for ESP8285-based Pico W clones.
# The ESP8285 AT firmware handles TLS natively via AT+CIPSTART with "SSL" type,
# so this module simply flags the socket to use SSL and (re)connects if needed.


def wrap_socket(sock, server_hostname=None, **kwargs):
    if server_hostname:
        sock._host = server_hostname
    if sock._connected:
        # Already connected via TCP — disconnect and reconnect as SSL
        host = server_hostname or sock._host
        port = sock._port
        sock._client.stop()
        sock._connected = False
        sock._ssl = True
        sock._host = host
        sock._port = port
        sock._do_connect()
    else:
        # Not yet connected — just mark as SSL for when connect() is called
        sock._ssl = True
    return sock
