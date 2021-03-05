#!/usr/bin/env python3

import sys, json 
import urllib.request
from subprocess import call,STDOUT
import time
import os
import configparser
import argparse

LOG_FILE = "/var/log/ecofreq.log"
CPU_PATH = "/sys/devices/system/cpu/cpu0/cpufreq/"

def read_value(fname):
    with open(fname) as f:
      return f.readline()

def read_int_value(fname):
  return int(read_value(fname))

class EcoFreqConfig(object):
  def __init__(self, args=None):
     self.timeout = 900
     self.freq_round = -3
     self.debug = False
     self.detect_freq()

     self.homedir = os.path.dirname(os.path.abspath(__file__))
#     self.epac_home = os.path.abspath(os.path.join(self.basepath, os.pardir)) + "/"
     if args and args.cfg_file:
       self.cfg_file = args.cfg_file
     else:
       self.cfg_file = os.path.join(self.homedir, "ecofreq.cfg")

     self.read_from_file()

     if not args:
       return

     if args.co2token:
       self.co2token = args.co2token

     if not self.co2token:
       print ("ERROR: Please specify CO2Signal API token!")
       sys.exit(-1)

  def detect_freq(self):
    driver = read_value(CPU_PATH + "scaling_driver")
    self.fmin = read_int_value(CPU_PATH + "cpuinfo_min_freq")
    self.fmax = read_int_value(CPU_PATH + "cpuinfo_max_freq")
    self.fstart = read_int_value(CPU_PATH + "scaling_max_freq")
    print ("Detected driver: ", driver, "  fmin: ", self.fmin, "  fmax: ", self.fmax)

  def read_from_file(self):
    if not os.path.exists(self.cfg_file):
      print("ERROR: Config file not found: ", self.cfg_file)
      sys.exit(-1)

    parser = configparser.ConfigParser()
    parser.read(self.cfg_file)
    co2 = parser["co2"]
    if co2:
      self.co2country = co2.get("Country")
      self.co2token = co2.get("Token")
      self.co2min = int(co2.get("Min"))
      self.co2max = int(co2.get("Max"))
#    print ("config: ", self.co2country, self.co2token, self.co2min, self.co2max)

class CO2Signal(object):

  def get_co2(self, cfg):
    req = urllib.request.Request("https://api.co2signal.com/v1/latest?countryCode=" + cfg.co2country)
    req.add_header("User-Agent", "Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11")
    req.add_header("auth-token", cfg.co2token)

    try:
      resp = urllib.request.urlopen(req).read()
      js = json.loads(resp)
      co2 = float(js['data']['carbonIntensity'])
    except:
      e = sys.exc_info()[0]
      print ("Exception: ", e)
      co2 = None
    return co2

class EcoFreq(object):
  def __init__(self, config):
    self.config = config
    self.co2provider = CO2Signal()
    self.freq = config.fstart

  def co2freq(self, co2):
    c = self.config
    if co2 >= c.co2max:
      k = 0.0
    elif co2 <= c.co2min:
      k = 1.0
    else:
      k = 1.0 - float(co2 - c.co2min) / (c.co2max - c.co2min)
  #  k = max(min(k, 1.0), 0.)
    freq = c.fmin + (c.fmax - c.fmin) * k
    freq = int(round(freq, c.freq_round))
    return freq  

  def set_freq(self, freq):
    if not self.config.debug:
      call("cpupower frequency-set -u " + str(freq) + " > /dev/null", shell=True)

  def update_freq(self): 
    co2 = self.co2provider.get_co2(self.config)

    if co2:
      self.freq = self.co2freq(co2)
      self.set_freq(self.freq)

      logstr='{0}\t{1}\t{2}'.format(time.ctime(), co2, self.freq)
    else:
      logstr = '{0}\t{1}\t{2}'.format(time.ctime(), "NA", self.freq)

    print (logstr)
    if not self.config.debug:
      with open(LOG_FILE, "a") as logf:
        logf.write(logstr + "\n")

  def spin(self):
    try:
      while 1:
        self.update_freq()
        time.sleep(self.config.timeout)
    except:
      e = sys.exc_info()[0]
      print ("Exception: ", e)
      self.set_freq(self.config.fmax)

def parse_args():
  parser = argparse.ArgumentParser()
  parser.add_argument("-c", dest="cfg_file", default=None, help="Config file name.")
  parser.add_argument("-t", dest="co2token", default=None, help="CO2Signal token.")
  args = parser.parse_args()
  return args

if __name__ == '__main__':

  if not os.path.isdir(CPU_PATH):
    print ("ERROR: CPU frequency scaling driver not found!")
    sys.exit(-1)

  args = parse_args()
  cfg = EcoFreqConfig(args)

  ef = EcoFreq(cfg)
  ef.spin()
