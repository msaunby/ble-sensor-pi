import sys
import select
import time
import re

#
# Command
# list
# enable [sensor,sensor...] or 'enable all'
# disable [sensor,sensor...] or 'disable all'
# interval [ms]
# quit





sensors = ['ir','hum','baro','lux','all']
sensors_re = '|'.join('[ ,]+%s' % sensor for sensor in sensors)

token_specification = [
        ('LIST',    r'list'),
        ('ENABLE',  r'enable(' + sensors_re + ')+'),
        ('DISABLE', r'disable(' + sensors_re + ')+'),
        ('INTERVAL',r'interval [0-9]+'),
        ('QUIT',    r'quit'),
        ('HELP',    r'help'),
        ('MISMATCH',r'.*'),
    ]

tok_regex = '|'.join('(?P<%s>%s)' % pair for pair in token_specification)

def readCommand( line ):
    for mo in re.finditer(tok_regex, line):
        kind = mo.lastgroup
        value = mo.group(kind)
        value = value.replace(",", " ")
        value = value.split()[1:]
        if kind == 'LIST':
            return (kind, sensors)
        elif kind == 'MISMATCH':
            return (None,None)
        else:
            return (kind, value)


if __name__ == "__main__":

    test = '''
list
interval 1000
enable ir,hum baro, lux
disable all
interewww
help
'''

    for line in test.split('\n'):
        ret = read_command(line)
        print (ret)

    while True:
        a = select.select([sys.stdin], [], [], 0)
        if a[0]:
            text = sys.stdin.readline()
            (kind,value) = read_command(text)
            print (kind, value)
