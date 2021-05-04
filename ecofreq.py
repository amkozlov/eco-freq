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
  def available(cls):
    return os.path.isfile(cls.CPU_PATH + "scaling_driver")

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
  def available(cls):
    return os.path.isfile(cls.package_file(0, "constraint_0_power_limit_uw"))

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

class EmissionProvider(object):
  def __init__(self, config):
    self.interval = int(config["emission"]["interval"])

  @classmethod
  def from_config(cls, config):
    prov_dict = {"co2signal" : CO2Signal, "mock" : MockCO2Provider }
    p = config["emission"].get("Provider", "co2signal")
    if p in prov_dict:
      return prov_dict[p](config)  
    else:
      raise ValueError("Unknown emission provider: " + p)

class CO2Signal(object):
  def __init__(self, config):
    EmissionProvider.__init__(self, config)
    self.co2country = config["co2signal"]["country"]
    self.co2token = config["co2signal"]["token"]

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
    EmissionProvider.__init__(self, config)
    if 'mock' in config:
      r = config['mock'].get('CO2Range', '100-800')
    self.co2min, self.co2max = [int(x) for x in r.split("-")]

  def get_co2(self):
    return random.randint(self.co2min, self.co2max)

class EcoPolicy(object):
  def __init__(self, config):
    self.freq_round = 3
    self.debug = False
    r = config["policy"]["CO2Range"].lower()
    if r == "auto":
      self.co2min = self.co2max = -1
    else:
      self.co2min, self.co2max = [int(x) for x in r.split("-")]

  @classmethod
  def from_config(cls, config):
    c = config["policy"]["Control"].lower()
    t = config["policy"]["Type"].lower()
    if c == "auto":
      if LinuxPowercapHelper.available():
        c = "power"
      elif CpuFreqHelper.available():
        c = "frequency"
      else:
        print ("ERROR: Power management interface not found!")
        sys.exit(-1)

    if c == "power" and t == "linear":
      return LinearPowerEcoPolicy(config)
    elif c == "frequency" and t == "linear":
      return LinearFreqEcoPolicy(config)
    else:
      raise ValueError("Unknown policy: " + [c, t])

class FreqEcoPolicy(EcoPolicy):
  def __init__(self, config):
    EcoPolicy.__init__(self, config)
    self.driver = CpuFreqHelper.get_driver()
   
    if not self.driver:
      print ("ERROR: CPU frequency scaling driver not found!")
      sys.exit(-1)

    self.fmin = CpuFreqHelper.get_hw_min_freq()
    self.fmax = CpuFreqHelper.get_hw_max_freq()
    self.fstart = CpuFreqHelper.get_gov_max_freq()
    print ("Detected driver: ", self.driver, "  fmin: ", self.fmin, "  fmax: ", self.fmax)

  def set_freq(self, freq):
    if not self.debug:
      CpuPowerHelper.set_max_freq(freq)      

  def set_co2(self, co2):
    self.freq = self.co2freq(co2)
    self.set_freq(self.freq)

  def reset(self):
    self.set_freq(self.fmax)

class LinearFreqEcoPolicy(FreqEcoPolicy):

  def __init__(self, config):
    FreqEcoPolicy.__init__(self, config)

  def co2freq(self, co2):
    if co2 >= self.co2max:
      k = 0.0
    elif co2 <= self.co2min:
      k = 1.0
    else:
      k = 1.0 - float(co2 - self.co2min) / (self.co2max - self.co2min)
  #  k = max(min(k, 1.0), 0.)
    freq = self.fmin + (self.fmax - self.fmin) * k
    freq = int(round(freq, self.freq_round))
    return freq


class PowerEcoPolicy(EcoPolicy):
  def __init__(self, config):
    EcoPolicy.__init__(self, config)
    
    if not LinuxPowercapHelper.available():
      print ("ERROR: RAPL powercap driver not found!")
      sys.exit(-1)

    self.pmax = LinuxPowercapHelper.get_package_hw_max_power(0)
    self.pmin = int(0.5*self.pmax)
    self.pstart = LinuxPowercapHelper.get_package_power_limit(0)

  def set_power(self, power_uw):
    if not self.debug:
      LinuxPowercapHelper.set_power_limit(power_uw)

  def set_co2(self, co2):
    self.power = self.co2power(co2)
    self.set_power(self.power)

  def reset(self):
    self.set_power(self.pmax)

class LinearPowerEcoPolicy(PowerEcoPolicy):
  def __init__(self, config):
    PowerEcoPolicy.__init__(self, config)

  def co2power(self, co2):
    if co2 >= self.co2max:
      k = 0.0
    elif co2 <= self.co2min:
      k = 1.0
    else:
      k = 1.0 - float(co2 - self.co2min) / (self.co2max - self.co2min)
    power = self.pmin + (self.pmax - self.pmin) * k
    power = int(round(power, self.freq_round))
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
    self.co2provider = EmissionProvider.from_config(config)
    self.co2policy = EcoPolicy.from_config(config)
    self.co2history = CO2History(config)
    self.debug = False

  def update_co2(self): 
    co2 = self.co2provider.get_co2()

    if co2:
      self.co2policy.set_co2(co2)
      self.co2history.add_co2(co2)
    else:
      co2 = "NA"

    ts = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    freq = power = None
    if CpuFreqHelper.available():
      freq = CpuFreqHelper.get_gov_max_freq()
    if LinuxPowercapHelper.available():
      power = LinuxPowercapHelper.get_package_power_limit(0) 
    logstr = '{0}\t{1}\t{2}\t{3}'.format(ts, co2, freq, power)

    logstr += "\t" + str(self.co2history.min_co2()) + "\t" + str(self.co2history.max_co2())

    print (logstr)
    if not self.debug:
      with open(LOG_FILE, "a") as logf:
        logf.write(logstr + "\n")

  def spin(self):
    try:
      while 1:
        self.update_co2()
        time.sleep(self.co2provider.interval)
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

def read_config(args):
  def_dict = {'emission' : { 'Provider' : 'co2signal',
                             'Interval' : '600'     },
              'policy'   : { 'Control'  : 'auto',    
                             'Type'     : 'Linear', 
                             'CO2Range' : 'auto'    }        
             }

  homedir = os.path.dirname(os.path.abspath(__file__))
  if args and args.cfg_file:
    cfg_file = args.cfg_file
  else:
    cfg_file = os.path.join(homedir, "ecofreq.cfg")

  if not os.path.exists(cfg_file):
    print("ERROR: Config file not found: ", cfg_file)
    sys.exit(-1)

  parser = configparser.ConfigParser()
  parser.read_dict(def_dict)
  parser.read(cfg_file)
 
  if args:
     if args.co2token:
       parser["co2signal"]["token"] = args.co2token

  return parser


if __name__ == '__main__':

  args = parse_args()
  cfg = read_config(args)

  ef = EcoFreq(cfg)
  ef.spin()
