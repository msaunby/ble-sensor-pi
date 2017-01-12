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
        print("Preparing to connect. You might need to press the side button...")
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

    def char_write_cmd( self, handle, value ):
        # The 0%x for value is VERY naughty!  Fix this!
        cmd = 'char-write-cmd 0x%02x %s' % (handle, value)
        print (cmd)
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
            try:
              pnum = self.con.expect('Notification handle = .*? \r', timeout=4)
            except pexpect.TIMEOUT:
              print ("TIMEOUT exception!")
              break
            if pnum==0:
                after = self.con.after
                hxstr = after.split()[3:]
                handle = int(float.fromhex(hxstr[0].decode("utf-8")))
            	#try:
            if True:
                self.cb[handle]([int(float.fromhex(n.decode("utf-8"))) for n in hxstr[2:]])
            	#except:
                #  print "Error in callback for %x" % handle
                #  print sys.argv[1]
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
        print ("IR %.1f %.1f" % (targetT, ambientT))

    def accel(self,v):
        (xyz,mag) = calcAccel(v[0],v[1],v[2])
        self.data['accl'] = xyz
        print ("ACCL", xyz)

    def humidity(self, v):
        rawT = (v[1]<<8)+v[0]
        rawH = (v[3]<<8)+v[2]
        (t, rh) = calcHum(rawT, rawH)
        self.data['humd'] = [t, rh]
        print ("HUMD %.1f %.1f" % (t, rh))

    def lux(self, v):
        rawL = (v[1]<<8)+v[0]
        lux = calcLux(rawL)
        self.data['lux'] = lux
        print ("LUX %.1f" % lux)

    def baro(self,v):
        rawT = (v[2]<<16)+(v[1]<<8)+v[0]
        rawP = (v[5]<<16)+(v[4]<<8)+v[3]
        (temp, pres) =  calcBaro(rawT, rawP)
        self.data['baro'] = [temp, pres]
        print ("BARO %0.1f %0.1f" % (temp, pres))
        self.data['time'] = int(time.time() * 1000)
        print (self.data)


def main():
    global datalog
    bluetooth_adr = sys.argv[1]
    if len(sys.argv) > 2:
        datalog = open(sys.argv[2], 'w+')

    while True:
     #try:
         #pass

     while True:
      print ("[re]starting..")

      tag = SensorTag(bluetooth_adr)
      cbs = SensorCallbacks(bluetooth_adr)

      # enable TMP006 sensor
      tag.register_cb(0x21,cbs.ir)
      tag.char_write_cmd(0x24, "01")   # IR Temperature Config  RW  Write "01" to start Sensor and Measurements, "00" to put to sleep
      tag.char_write_cmd(0x26, "20") # IR Temperature Period  RW  Period = [Input*10] ms, (lower limit 300 ms), default 1000 ms
      tag.char_write_cmd(0x22, "0100") # Client Characteristic Configuration  RW  Write "01:00" to enable notifications, "00:00" to disable


      # enable humidity
      tag.register_cb(0x29, cbs.humidity)
      tag.char_write_cmd(0x2C, "01") # Humidity Config		RW	Write "01" to start measurements, "00" to stop
      tag.char_write_cmd(0x2E,"40") # Humidity Period		RW	Period = [Input*10] ms, (lower limit 100 ms), default 1000 ms
      tag.char_write_cmd(0x2A,"0100") # Client Characteristic Configuration		RW	Write "01:00" to enable notifications, "00:00" to disable

      # enable lux
      tag.register_cb(0x41, cbs.lux)
      tag.char_write_cmd(0x44, "01") # Luxometer Config		RW	Write "01" to start Sensor and Measurements, "00" to put to sleep
      tag.char_write_cmd(0x46,"80") # Luxometer Period		RW	Period = [Input*10]ms (lower limit 1000ms), default 2000ms
      tag.char_write_cmd(0x42,"0100") # Client Characteristic Configuration		RW	Write "01:00" to enable notifications, "00:00" to disable

      # enable barometer
      tag.register_cb(0x31,cbs.baro)
      tag.char_write_cmd(0x32, "0100") # Write "01:00" to enable notifications, "00:00" to disable
      tag.char_write_cmd(0x34, "01") # Write "01" to start Sensor and Measurements, "00" to put to sleep, "02" to read calibration values from sensor
      tag.char_write_cmd(0x36, "40") # Barometer Period		RW	Period = [Input*10] ms, (lower limit 100 ms), default 1000 ms


      tag.notification_loop()
     #except:
      #pass

if __name__ == "__main__":
    main()
