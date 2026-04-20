import WiFi
import utime

# enter your network
SSID = "<<YOUR SSID>>"
PWD = "<<YOUR PASSWORD>>"

# http response
resp = 'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n<h1>Hello PicoW!</h1>\r\n'


print(f'[WiFi] Init (should be True): {WiFi.init(0)}')
print(f'[WiFi] Status (should be 4): {WiFi.status()}')
print(f'[WiFi] Begin (should be 1): {WiFi.begin(SSID, PWD, None)}')

if (WiFi.status() == WiFi.WL_CONNECTED):
    print("[WiFi] Connected to the network")
    print(f'[WiFi] Status (should be {WiFi.WL_CONNECTED}): {WiFi.status()}')
    
    srv = WiFi.Server(80)
    srv.begin()
    
    print("\r\n[WiFi] Http server started")
    print(f'[WiFi] Server status (should be {WiFi.WL_SRV_LISTEN}): {srv.status()}')
    print(f'[WiFi] Use your browser and navigate to:  http://{WiFi.localIp()}/index.html')

    while (True):
        cli = srv.available()
        if (cli != None):
            buf = b''
            while (cli.available()):
                buf = buf + cli.readBuf(cli.available())
                utime.sleep(0.1)
                
            print('\r\nDumping the http request:')
            print(buf.decode())
        
            response = resp + f'Seconds running: {utime.ticks_ms()//1000}'
            print('\r\nSending the http response:')
            print(response)
            cli.print(response)
            cli.flush()
            cli.stop()
            
            print('\r\nConnection closed, to retry, refresh the page in the browser')
