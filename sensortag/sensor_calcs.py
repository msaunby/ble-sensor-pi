#
# Michael Saunby. Jan 2017
#

tosigned = lambda n: float(n-0x10000) if n>0x7fff else float(n)
tosignedbyte = lambda n: float(n-0x100) if n>0x7f else float(n)

# See http://processors.wiki.ti.com/index.php/CC2650_SensorTag_User's_Guide

def calcLux(lux):
    m = lux & 0x0FFF
    e = (lux & 0xF000) >> 12
    return m * (0.01 * pow(2.0,e))

def calcTmpTarget(objT, ambT):

    SCALE_LSB = 0.03125
    objT = tosigned(objT)
    ambT = tosigned(ambT)

    objT = (objT / 4) * SCALE_LSB
    ambT = (ambT / 4) * SCALE_LSB

    return (objT, ambT)

def calcHum(rawT, rawH):
    # -- calculate temperature [deg C]
    t = (tosigned(rawT) / 65536) * 165.0 - 40.0
    # -- calculate relative humidity [%RH]
    rh = (float(rawH) / 65536) * 100.0
    return (t, rh)

def calcBaro(rawT, rawP):
    t = float(rawT) / 100.0
    p = float(rawP) / 100.0
    return (t, p)
