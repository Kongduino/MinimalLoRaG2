import network, time, maes, binascii, random, sh1107, gc
from sx1262 import SX1262
from machine import SPI, Pin, I2C
from hexdump import hexDump
from xcrc32 import xcrc32
from umqtt.simple import MQTTClient
from mySettings import *

py = 32
friends = {}
i2c0 = I2C(0, scl = Pin(6), sda = Pin(5), freq=800000)
display = sh1107.SH1107_I2C(64, 128, i2c0, address = 0x3c, rotate = 270)
display.fill(0)

f = open("friends.txt", "r")
for s in f:
    t = s.strip().split("\t")
    t[0] = t[0].lower()
    friends[t[0]] = t[1]
    print(f"{t[0]} = {t[1]}")

def printLine(txt):
    global py
    display.fill_rect(0, py, 128, 16, 0)
    display.text(txt, 10, py, 1)
    display.show()
    print(txt)
    py += 8
    if py > 63:
        py = 0
    gc.collect()

printLine('Minimal LoRa')

d = i2c0.scan()
hasAMG = (0x69 in d)
if hasAMG:
    import AMG8833
    amg = AMG8833.AMG8833(i2c0, addr=0x69)
    printLine("* AMG8833")
printLine('* WiFi')
wlan = network.WLAN(network.STA_IF)
wlan.active(False)
time.sleep(0.5)
wlan.active(True)
wlan.connect(SSID, PWD)
b = wlan.isconnected()
while wlan.isconnected() == False:
    pass
print('network config:', wlan.ipconfig('addr4'))
printLine('* MQTT')

printLine('* LoRa')
sx = SX1262(1, clk = Pin(12), mosi = Pin(13), miso = Pin(14), cs = Pin(11), irq = Pin(48), rst = Pin(21), gpio = Pin(47))
# LoRa
sx.begin(freq = 868.125, bw = 125.0, sf = 12, cr = 5, syncWord = 0x12,
         power = 22, currentLimit = 140.0, preambleLength = 8, 
         implicit = False, implicitLen = 0xFF, 
         crcOn = True, txIq = False, rxIq = False, 
         tcxoVoltage = 1.8, useRegulatorLDO = False, blocking = True)

printLine('* AES')
pingCount = 0

print("LoRa init done!")
printLine('* Done!')

def publish(txt):
    global BTN_TOPIC, BROKER_ADDR
    try:
        printLine('MQTT Publish.')
        mqttc = MQTTClient(CLIENT_NAME, BROKER_ADDR, keepalive = 60)
        printLine('MQTT connect')
        b = mqttc.connect()
        print(f'mqttc.connect() = {b}')
        printLine('MQTT Publish')
        mqttc.publish(BTN_TOPIC, txt)
        time.sleep(2)
        printLine('MQTT Published')
        mqttc.disconnect()
        time.sleep(1)
        printLine('MQTT disconnect')
        mqttc = None
    except Exception as inst:
        printLine('MQTT Error')
        print(type(inst)) # the exception type
        print(inst.args) # arguments stored in .args
        print(inst)
        mqttc = None

def sendPing():
    global sx, myUUID, pingCount, pKey, display
    printLine('* Prepare PING')
    cnt = pingCount.to_bytes(2, 'little')
    pingCount += 1
    packet = myUUID + b'P' + cnt
    crc = xcrc32(packet, 9, 0xffffffff)
    packet += crc.to_bytes(4, 'little') + b'\x03\x03\x03'
    printLine('* Encryption')
    pIV = bytearray(16)
    for i in range(0, 16):
        pIV[i] = random.randint(0, 255)
    cryptor = maes.new(pKey, maes.MODE_CBC, IV = pIV)
    ciphertext = cryptor.encrypt(packet)
    msg = bytes(ciphertext + pIV)
    hexDump(msg)
    printLine('* Sending...')
    display.show()
    sx.send(msg)

def cb(events):
    global lastPing, amIbusy, pKey, sx, display, py, pingCount, myUUIDtext
    if events & SX1262.RX_DONE:
        printLine('* Incoming!')
        display.show()
        msg, err = sx.recv()
        error = SX1262.STATUS[err]
        if error != 'ERR_NONE':
            errmsg = f' * Error: {error}'
            print(errmsg)
            printLine(errmsg)
            return
        #hexDump(msg)
        RSSI = sx.getRSSI()
        SNR = sx.getSNR()
        print(f'Incoming. RSSI = {RSSI}, SNR = {SNR}')
        printLine(f'* RSSI: {RSSI}')
        printLine(f'* SNR: {SNR}')
        printLine('* Decryption')
        pIV = msg[-16:]
        ciphertext = msg[:-16]
        decryptor = maes.new(pKey, maes.MODE_CBC, IV = pIV)
        decrypted = bytes(decryptor.decrypt(ciphertext))
        hexDump(decrypted)
        if decrypted[6] == 0x50:
            # PING
            cnt = decrypted[7] + decrypted[8] * 256
            UUID = binascii.hexlify(decrypted[0:6]).decode('ascii').lower()
            nm = friends.get(UUID)
            if nm != None:
                UUID = nm
            print(f'From {UUID} PING #0x{cnt:04x}')
            printLine(f'> {UUID}')
            printLine(f'PING #0x{cnt:04x}')
            pkt = binascii.hexlify(decrypted).decode('ascii')
            publish(f'{pkt},{RSSI},{SNR},{tmp:.2f}')
        else:
            printLine(f'Unknown code: 0x{decrypted[6]:02x}')
    elif events & SX1262.TX_DONE:
        print('TX done.')
        py -= 8
        printLine('* Packet sent!')
        print(f'myUUID = {myUUIDtext}')
        pc = pingCount-1
        publish(f'{myUUIDtext}:PING #{pc:04x}:{tmp:.2f}')
        py -= 8
        lastPing = time.time()
        amIbusy = False

sx.setBlockingCallback(False, cb)

def button_change(x):
    global pir
    while pir.value() == 0:
        pass
    sendPing()

lastPing = time.time() - 150
lastTemp = time.time() - 15
amIbusy = False
pir = Pin(38, Pin.IN)
pir.irq(trigger=Pin.IRQ_RISING, handler = button_change)

while True:
    if time.time() - lastPing > 150 and amIbusy == False:
        print('Sending...')
        amIbusy = True
        lastPing = time.time()
        sendPing()
        gc.collect()
    if time.time() - lastTemp > 15 and hasAMG:
        data = amg.pixel()
        tmp = amg.temperature()
        printLine(f'* Temp {tmp:.2f}')
        lastTemp = time.time()
