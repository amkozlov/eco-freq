#!/usr/bin/env python3

import sys, json 
import urllib.request
from subprocess import call,STDOUT
import datetime
import time
import os
import configparser
import argparse
import random
import heapq

LOG_FILE = "/var/log/ecofreq.log"

def read_value(fname):
    with open(fname) as f:
      return f.readline()

def read_int_value(fname):
  return int(read_value(fname))

def write_value(fname, val):
    with open(fname, "w") as f:
      f.write(str(val))

class CpuFreqHelper(object):
  CPU_PATH = "/sys/devices/system/cpu/cpu0/cpufreq/"

  @classmethod
  def get_string(cls, name):
    try:
      return read_value(cls.CPU_PATH + name)
    except:
      return None 

  @classmethod
  def get_int(cls, name):
    s = cls.get_string(name)
    return None if s is None else int(s)

  @classmethod
  def get_driver(cls):
    return str.strip(cls.get_string("scaling_driver"))

  @classmethod
  def get_hw_min_freq(cls):
    return cls.get_int("cpuinfo_min_freq")

  @classmethod
  def get_hw_max_freq(cls):
    return cls.get_int("cpuinfo_max_freq")

  @classmethod
  def get_hw_cur_freq(cls):
    return cls.get_int("cpuinfo_cur_freq")

  @classmethod
  def get_gov_min_freq(cls):
    return cls.get_int("scaling_min_freq")

  @classmethod
  def get_gov_max_freq(cls):
    return cls.get_int("scaling_max_freq")

  @classmethod
  def get_gov_cur_freq(cls):
    return cls.get_int("scaling_cur_freq")

class CpuPowerHelper(object):
  @classmethod
  def set_max_freq(cls, freq):
    call("cpupower frequency-set -u " + str(freq) + " > /dev/null", shell=True)

class LinuxPowercapHelper(object):
  INTEL_RAPL_PATH="/sys/class/powercap/intel-rapl:"
  PKG_MAX=256

  @classmethod
  def package_path(cls, pkg):
    return cls.INTEL_RAPL_PATH + str(pkg)

  @classmethod
  def package_file(cls, pkg, fname):
    return os.path.join(cls.package_path(pkg), fname)

  @classmethod
  def package_list(cls):
    l = []
    pkg = 0
    while pkg < cls.PKG_MAX:
      fname = cls.package_file(pkg, "name")
      if not os.path.isfile(fname):
        break;
      pkg_name = read_value(fname)  
      if  pkg_name.startswith("package-"):
        l += [pkg]
      pkg += 1
    return l

  @classmethod
  def get_package_hw_max_power(cls, pkg):
    return read_int_value(cls.package_file(pkg, "constraint_0_max_power_uw"))  

  @classmethod
  def get_package_power_limit(cls, pkg):
    return read_int_value(cls.package_file(pkg, "constraint_0_power_limit_uw")) 

  @classmethod
  def set_package_power_limit(cls, pkg, power_uw):
    write_value(cls.package_file(pkg, "constraint_0_power_limit_uw"), power_uw)

  @classmethod
  def reset_package_power_limit(cls, pkg):
    write_value(cls.package_file(pkg, "constraint_0_power_limit_uw"), cls.get_package_hw_max_power(pkg))

  @classmethod
  def set_power_limit(cls, power_uw):
    for pkg in cls.package_list(): 
      cls.set_package_power_limit(pkg, power_uw)

class EcoFreqConfig(object):
  def __init__(self, args=None):
     self.timeout = 900
     self.freq_round = -3
     self.debug = False

     self.homedir = os.path.dirname(os.path.abspath(__file__))
     if args and args.cfg_file:
       self.cfg_file = args.cfg_file
     else:
       self.cfg_file = os.path.join(self.homedir, "ecofreq.cfg")

     self.read_from_file()

     if not args:
       return

     if args.co2token:
       self.co2token = args.co2token

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
      self.timeout = int(co2.get("Timeout", self.timeout))
#    print ("config: ", self.co2country, self.co2token, self.co2min, self.co2max)

class CO2Signal(object):
  def __init__(self, config):
    self.co2country = config.co2country
    self.co2token = config.co2token

    if not self.co2token:
      print ("ERROR: Please specify CO2Signal API token!")
      sys.exit(-1)

  def get_co2(self):
    req = urllib.request.Request("https://api.co2signal.com/v1/latest?countryCode=" + self.co2country)
    req.add_header("User-Agent", "Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11")
    req.add_header("auth-token", self.co2token)

    try:
      resp = urllib.request.urlopen(req).read()
      js = json.loads(resp)
      co2 = float(js['data']['carbonIntensity'])
    except:
      e = sys.exc_info()[0]
      print ("Exception: ", e)
      co2 = None
    return co2

class MockCO2Provider(object):
  def __init__(self, config):
    self.co2min = 100 if config.co2min is None else config.co2min
    self.co2max = 800 if config.co2max is None else config.co2max

  def get_co2(self):
    return random.randint(self.co2min, self.co2max)

class CO2Policy(object):
  def __init__(self, config):
    self.config = config

class FreqCO2Policy(CO2Policy):
  def __init__(self, config):
    CO2Policy.__init__(self, config)
    self.driver = CpuFreqHelper.get_driver()
   
    if not self.driver:
      print ("ERROR: CPU frequency scaling driver not found!")
      sys.exit(-1)

    self.fmin = CpuFreqHelper.get_hw_min_freq()
    self.fmax = CpuFreqHelper.get_hw_max_freq()
    self.fstart = CpuFreqHelper.get_gov_max_freq()
    print ("Detected driver: ", self.driver, "  fmin: ", self.fmin, "  fmax: ", self.fmax)

  def set_freq(self, freq):
    if not self.config.debug:
      CpuPowerHelper.set_max_freq(freq)      

  def set_co2(self, co2):
    self.freq = self.co2freq(co2)
    self.set_freq(self.freq)

  def reset(self):
    self.set_freq(self.fmax)

class LinearFreqCO2Policy(FreqCO2Policy):

  def __init__(self, config):
    FreqCO2Policy.__init__(self, config)

  def co2freq(self, co2):
    c = self.config
    if co2 >= c.co2max:
      k = 0.0
    elif co2 <= c.co2min:
      k = 1.0
    else:
      k = 1.0 - float(co2 - c.co2min) / (c.co2max - c.co2min)
  #  k = max(min(k, 1.0), 0.)
    freq = self.fmin + (self.fmax - self.fmin) * k
    freq = int(round(freq, c.freq_round))
    return freq


class PowerCO2Policy(CO2Policy):
  def __init__(self, config):
    CO2Policy.__init__(self, config)
    self.pmax = LinuxPowercapHelper.get_package_hw_max_power(0)
    self.pmin = int(0.5*self.pmax)
    self.pstart = LinuxPowercapHelper.get_package_power_limit(0)

  def set_power(self, power_uw):
    if not self.config.debug:
      LinuxPowercapHelper.set_power_limit(power_uw)

  def set_co2(self, co2):
    self.power = self.co2power(co2)
    self.set_power(self.power)

  def reset(self):
    self.set_power(self.pmax)

class LinearPowerCO2Policy(PowerCO2Policy):
  def co2power(self, co2):
    c = self.config
    if co2 >= c.co2max:
      k = 0.0
    elif co2 <= c.co2min:
      k = 1.0
    else:
      k = 1.0 - float(co2 - c.co2min) / (c.co2max - c.co2min)
    power = self.pmin + (self.pmax - self.pmin) * k
    power = int(round(power, c.freq_round))
    return power

class CO2History(object):
  def __init__(self, config):
    self.config = config
    self.h = []

  def add_co2(self, co2):
    heapq.heappush(self.h, co2)

  def min_co2(self, quantile = 5):
    n = int(0.01 * quantile * len(self.h)) + 1
    return heapq.nsmallest(n, self.h)[n-1]

  def max_co2(self, quantile = 5):
    n = int(0.01 * quantile * len(self.h)) + 1
    return heapq.nlargest(n, self.h)[n-1]

class EcoFreq(object):
  def __init__(self, config):
    self.config = config
#    self.co2provider = CO2Signal()
    self.co2provider = MockCO2Provider(config)
    self.co2policy = LinearFreqCO2Policy(config)
#    self.co2policy = LinearPowerCO2Policy(config)
    self.co2history = CO2History(config)

  def update_co2(self): 
    co2 = self.co2provider.get_co2()

    if co2:
      self.co2policy.set_co2(co2)
      self.co2history.add_co2(co2)
    else:
      co2 = "NA"

    ts = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    freq  = CpuFreqHelper.get_gov_max_freq()
    power = LinuxPowercapHelper.get_package_power_limit(0) 
    logstr = '{0}\t{1}\t{2}\t{3}'.format(ts, co2, freq, power)

    logstr += "\t" + str(self.co2history.min_co2()) + "\t" + str(self.co2history.max_co2())

    print (logstr)
    if not self.config.debug:
      with open(LOG_FILE, "a") as logf:
        logf.write(logstr + "\n")

  def spin(self):
    try:
      while 1:
        self.update_co2()
        time.sleep(self.config.timeout)
    except:
      e = sys.exc_info()
      print ("Exception: ", e)
      self.co2policy.reset()

def parse_args():
  parser = argparse.ArgumentParser()
  parser.add_argument("-c", dest="cfg_file", default=None, help="Config file name.")
  parser.add_argument("-t", dest="co2token", default=None, help="CO2Signal token.")
  args = parser.parse_args()
  return args

if __name__ == '__main__':

  args = parse_args()
  cfg = EcoFreqConfig(args)

  ef = EcoFreq(cfg)
  ef.spin()
