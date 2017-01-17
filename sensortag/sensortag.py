#!/usr/bin/env python
# Michael Saunby. April 2013
#
# Notes.
# pexpect uses regular expression so characters that have special meaning
# in regular expressions, e.g. [ and ] must be escaped with a backslash.
#
#   Copyright 2013 Michael Saunby
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import pexpect
import sys
import time
from sensor_calcs import *
import json
import select
from tag_commands import readCommand
import atexit

DEBUG = False

tag = None

def debug_print(str):
    if DEBUG:
        print(str)


def floatfromhex(h):
    t = float.fromhex(h)
    if t > float.fromhex('7FFF'):
        t = -(float.fromhex('FFFF') - t)
        pass
    return t

class SensorTag:

    def __init__( self, bluetooth_adr ):
        self.con = pexpect.spawn('gatttool -b ' + bluetooth_adr + ' --interactive')
        self.con.expect('\[LE\]>', timeout=600)
        debug_print("Preparing to connect. You might need to press the side button...")
        self.con.sendline('connect')
        # test for success of connect
        self.con.expect('Connection successful.*\[LE\]>')
        # Earlier versions of gatttool returned a different message.  Use this pattern -
        #self.con.expect('\[CON\].*>')
        self.cb = {}
        return

        self.con.expect('\[CON\].*>')
        self.cb = {}
        return

    def enableSensors( self, sensors ):
        print ("Enabling", sensors)
        global tag
        all = False
        if 'all' in sensors:
            all = True
        if all or 'ir' in sensors:
            # enable IR sensor
            tag.char_write_cmd(0x24, "01")   # IR Temperature Config  RW  Write "01" to start Sensor and Measurements, "00" to put to sleep
            tag.char_write_cmd(0x22, "0100") # Client Characteristic Configuration  RW  Write "01:00" to enable notifications, "00:00" to disable
        if all or 'hum' in sensors:
            # enable humidity
            tag.char_write_cmd(0x2C, "01") # Humidity Config		RW	Write "01" to start measurements, "00" to stop
            tag.char_write_cmd(0x2A,"0100") # Client Characteristic Configuration		RW	Write "01:00" to enable notifications, "00:00" to disable
        if all or 'lux' in sensors:
            # enable lux
            tag.char_write_cmd(0x44, "01") # Luxometer Config		RW	Write "01" to start Sensor and Measurements, "00" to put to sleep
            tag.char_write_cmd(0x42,"0100") # Client Characteristic Configuration		RW	Write "01:00" to enable notifications, "00:00" to disable
        if all or 'baro' in sensors:
            # enable barometer
            tag.char_write_cmd(0x34, "01") # Write "01" to start Sensor and Measurements, "00" to put to sleep, "02" to read calibration values from sensor
            tag.char_write_cmd(0x32, "0100") # Write "01:00" to enable notifications, "00:00" to disable

    def disableSensors( self, sensors ):
        print ("Disabling", sensors)
        global tag
        all = False
        if 'all' in sensors:
            all = True
        if all or 'ir' in sensors:
            # disable IR sensor
            tag.char_write_cmd(0x24, "00")
            tag.char_write_cmd(0x22, "0000")
        if all or 'hum' in sensors:
            # disable humidity sensor
            tag.char_write_cmd(0x2C, "00")
            tag.char_write_cmd(0x2A,"0000")
        if all or 'lux' in sensors:
            # disable lux sensor
            tag.char_write_cmd(0x44, "00")
            tag.char_write_cmd(0x42,"0000")
        if all or 'baro' in sensors:
            # disable barometer sensor
            tag.char_write_cmd(0x34, "00")
            tag.char_write_cmd(0x32, "0000")

    def setInterval( self, hexinterval ):
        tag.char_write_cmd(0x26, hexinterval)
        # humidity
        tag.char_write_cmd(0x2E, hexinterval)
        # lux
        tag.char_write_cmd(0x46, hexinterval)
        # barometer
        tag.char_write_cmd(0x36, hexinterval)


    def char_write_cmd( self, handle, value ):
        # The 0%x for value is VERY naughty!  Fix this!
        cmd = 'char-write-cmd 0x%02x %s' % (handle, value)
        debug_print (cmd)
        self.con.sendline( cmd )
        return

    def char_read_hnd( self, handle ):
        self.con.sendline('char-read-hnd 0x%02x' % handle)
        self.con.expect('descriptor: .*? \r')
        after = self.con.after
        rval = after.split()[1:]
        return [long(float.fromhex(n)) for n in rval]

    # Notification handle = 0x0025 value: 9b ff 54 07
    def notification_loop( self ):
        while True:
            pnum = None
            handle = None
            a = select.select([sys.stdin], [], [], 0)
            if a[0]:
                text = sys.stdin.readline()
                (kind,value) = readCommand(text)
                print (kind, value)
                if kind == "QUIT":
                    sys.exit(0)
                elif kind == "ENABLE":
                    self.enableSensors(value)
                elif kind == "DISABLE":
                    self.disableSensors(value)
                elif kind == "INTERVAL":
                    self.setInterval((value[0]))
            try:
              pnum = self.con.expect('Notification handle = .*? \r', timeout=10)
            except pexpect.TIMEOUT:
              print ("TIMEOUT exception!")
              #break
            if pnum==0:
                after = self.con.after
                hxstr = after.split()[3:]
                handle = int(float.fromhex(hxstr[0].decode("utf-8")))
                self.cb[handle]([int(float.fromhex(n.decode("utf-8"))) for n in hxstr[2:]])
                pass
            else:
              print ("TIMEOUT!!")
        pass

    def register_cb( self, handle, fn ):
        self.cb[handle]=fn;
        return

datalog = sys.stdout

class SensorCallbacks:

    data = {}

    def __init__(self,addr):
        self.data['addr'] = addr

    def ir(self,v):
        objT = (v[1]<<8)+v[0]
        ambT = (v[3]<<8)+v[2]
        (targetT, ambientT) = calcTmpTarget(objT, ambT)
        self.data['ir'] = [targetT, ambientT]
        debug_print ("IR %.1f %.1f" % (targetT, ambientT))

    def accel(self,v):
        (xyz,mag) = calcAccel(v[0],v[1],v[2])
        self.data['accl'] = xyz
        debug_print ("ACCL", xyz)

    def humidity(self, v):
        rawT = (v[1]<<8)+v[0]
        rawH = (v[3]<<8)+v[2]
        (t, rh) = calcHum(rawT, rawH)
        self.data['humd'] = [t, rh]
        debug_print ("HUMD %.1f %.1f" % (t, rh))

    def lux(self, v):
        rawL = (v[1]<<8)+v[0]
        lux = calcLux(rawL)
        self.data['lux'] = lux
        debug_print ("LUX %.1f" % lux)

    def baro(self,v):
        global datalog
        rawT = (v[2]<<16)+(v[1]<<8)+v[0]
        rawP = (v[5]<<16)+(v[4]<<8)+v[3]
        (temp, pres) =  calcBaro(rawT, rawP)
        self.data['baro'] = [temp, pres]
        debug_print ("BARO %0.1f %0.1f" % (temp, pres))
        self.data['time'] = int(time.time() * 1000)
        datalog.write(str(self.data) + "\n")


def main():
    global datalog, tag
    bluetooth_adr = sys.argv[1]
    if len(sys.argv) > 2:
        datalog = open(sys.argv[2], 'a+')
    else:
        datalog = sys.stdout

    while True:
      debug_print ("[re]starting..")

      tag = SensorTag(bluetooth_adr)
      tag.cbs = SensorCallbacks(bluetooth_adr)
      #tag.setInterval("0010")
      tag.register_cb(0x21, tag.cbs.ir)
      tag.register_cb(0x29, tag.cbs.humidity)
      tag.register_cb(0x41, tag.cbs.lux)
      tag.register_cb(0x31, tag.cbs.baro)
      #tag.setInterval("0010")
      tag.enableSensors(["all"])
      tag.setInterval("0100")
      try:
          tag.notification_loop()
      except KeyboardInterrupt:
          sys.exit()

def cleanup():
    global datalog
    if datalog != sys.stdout:
        datalog.close()
    print ("Goodbye!")

if __name__ == "__main__":
    atexit.register(cleanup)
    main()
