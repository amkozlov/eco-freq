#!/usr/bin/env python3

import sys, json 
import urllib.request
from subprocess import call,check_output,STDOUT,DEVNULL,CalledProcessError
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
    if os.path.isfile(fname):
      with open(fname, "w") as f:
        f.write(str(val))
      return True
    else:
      return False

class CpuFreqHelper(object):
  SYSFS_CPU_PATH = "/sys/devices/system/cpu/cpu{0}/cpufreq/{1}"
  KHZ, MHZ, GHZ = 1, 1e3, 1e6

  @classmethod
  def cpu_field_fname(cls, cpu, field):
    return cls.SYSFS_CPU_PATH.format(cpu, field)

  @classmethod
  def available(cls):
    return os.path.isfile(cls.cpu_field_fname(0, "scaling_driver"))
  
  @classmethod
  def info(cls):
    if cls.available():
      print ("DVFS settings:  driver = " + cls.get_driver() + ", governor = " + cls.get_governor())
      hw_fmin = round(cls.get_hw_min_freq(cls.MHZ))
      hw_fmax = round(cls.get_hw_max_freq(cls.MHZ))
      gov_fmin = round(cls.get_gov_min_freq(cls.MHZ))
      gov_fmax = round(cls.get_gov_max_freq(cls.MHZ))
      print ("DVFS HW limits: " + str(hw_fmin) + " - " + str(hw_fmax) + " MHz")
      print ("DVFS policy:    " + str(gov_fmin) + " - " + str(gov_fmax) + " MHz")
    else:
        print("DVFS driver not found.")

  @classmethod
  def get_string(cls, name):
    try:
      return read_value(cls.cpu_field_fname(0, name))
    except:
      return None 

  @classmethod
  def get_int(cls, name):
    s = cls.get_string(name)
    return None if s is None else int(s)

  @classmethod
  def get_driver(cls):
    return cls.get_string("scaling_driver").strip()

  @classmethod
  def get_governor(cls):
    return cls.get_string("scaling_governor").strip()

  @classmethod
  def get_hw_min_freq(cls, unit=KHZ):
    return cls.get_int("cpuinfo_min_freq") / unit

  @classmethod
  def get_hw_max_freq(cls, unit=KHZ):
    return cls.get_int("cpuinfo_max_freq") / unit

  @classmethod
  def get_hw_cur_freq(cls, unit=KHZ):
    return cls.get_int("cpuinfo_cur_freq") / unit

  @classmethod
  def get_gov_min_freq(cls, unit=KHZ):
    return cls.get_int("scaling_min_freq") / unit

  @classmethod
  def get_gov_max_freq(cls, unit=KHZ):
    return cls.get_int("scaling_max_freq") / unit

  @classmethod
  def get_gov_cur_freq(cls, unit=KHZ):
    return cls.get_int("scaling_cur_freq") / unit

  @classmethod
  def set_cpu_field_value(cls, cpu, field, value):  
    return write_value(cls.cpu_field_fname(cpu, field), value)
    
  @classmethod
  def set_field_value(cls, field, value):  
    cpu = 0
    while cls.set_cpu_field_value(cpu, field, value):
      cpu += 1

  @classmethod
  def set_gov_max_freq(cls, freq):
    cls.set_field_value("scaling_max_freq", freq)

class CpuPowerHelper(object):
  @classmethod
  def set_max_freq(cls, freq):
    call("cpupower frequency-set -u " + str(freq) + " > /dev/null", shell=True)

class LinuxPowercapHelper(object):
  INTEL_RAPL_PATH="/sys/class/powercap/intel-rapl:"
  PKG_MAX=256
  UWATT, MWATT, WATT = 1, 1e3, 1e6

  @classmethod
  def package_path(cls, pkg):
    return cls.INTEL_RAPL_PATH + str(pkg)

  @classmethod
  def package_file(cls, pkg, fname):
    return os.path.join(cls.package_path(pkg), fname)

  @classmethod
  def package_list(cls, domain="package-"):
    l = []
    pkg = 0
    while pkg < cls.PKG_MAX:
      fname = cls.package_file(pkg, "name")
      if not os.path.isfile(fname):
        break;
      pkg_name = read_value(fname)  
      if pkg_name.startswith(domain):
        l += [str(pkg)]
      if domain in ["dram", "core", "uncore"]:
        subpkg = 0
        while subpkg < cls.PKG_MAX:
          subpkg_code = str(pkg) + ":" + str(subpkg) 
          fname = cls.package_file(subpkg_code, "name")
          if not os.path.isfile(fname):
            break;
          pkg_name = read_value(fname)  
          if pkg_name.startswith(domain):
            l += [subpkg_code]
          subpkg += 1
      pkg += 1
    return l

  @classmethod
  def available(cls):
    return os.path.isfile(cls.package_file(0, "constraint_0_power_limit_uw"))

  @classmethod
  def info(cls):
    if cls.available():
        outfmt = "RAPL {0} domains: count = {1}, hw_limit = {2} W, current_limit = {3} W" 
        cpus = cls.package_list()
        if len(cpus):
          maxp = cls.get_package_hw_max_power(cpus[0], cls.WATT)
          curp = cls.get_package_power_limit(cpus[0], cls.WATT)
          print(outfmt.format("CPU ", len(cpus), maxp, curp))
        dram = cls.package_list("dram")
        if len(dram):
          try:
            maxp = cls.get_package_hw_max_power(dram[0], cls.WATT)
          except OSError:
            maxp = None
          curp = cls.get_package_power_limit(dram[0], cls.WATT)
          print(outfmt.format("DRAM", len(dram), maxp, curp))
        psys = cls.package_list("psys")
        if len(psys):
          try:
            maxp = cls.get_package_hw_max_power(psys[0], cls.WATT)
          except OSError:
            maxp = None
          curp = cls.get_package_power_limit(psys[0], cls.WATT)
          print(outfmt.format("PSYS", len(psys), maxp, curp))
    else:
        print("RAPL powercap not found.")

  @classmethod
  def get_package_hw_max_power(cls, pkg, unit=UWATT):
    return read_int_value(cls.package_file(pkg, "constraint_0_max_power_uw")) / unit 

  @classmethod
  def get_package_power_limit(cls, pkg, unit=UWATT):
    return read_int_value(cls.package_file(pkg, "constraint_0_power_limit_uw")) / unit 

  @classmethod
  def get_package_energy(cls, pkg):
    return read_int_value(cls.package_file(pkg, "energy_uj")) 

  @classmethod
  def get_package_energy_range(cls, pkg):
    return read_int_value(cls.package_file(pkg, "max_energy_range_uj")) 

  @classmethod
  def set_package_power_limit(cls, pkg, power, unit=UWATT):
    val = round(power * unit)
    write_value(cls.package_file(pkg, "constraint_0_power_limit_uw"), val)

  @classmethod
  def reset_package_power_limit(cls, pkg):
    # write_value(cls.package_file(pkg, "constraint_0_power_limit_uw"), round(cls.get_package_hw_max_power(pkg)))
    cls.set_package_power_limit(pkg, cls.get_package_hw_max_power(pkg))

  @classmethod
  def set_power_limit(cls, power, unit=UWATT):
    for pkg in cls.package_list(): 
      cls.set_package_power_limit(pkg, power, unit)

class IPMIHelper(object):
  @classmethod
  def available(cls):
    return cls.get_power() is not None

  @classmethod
  def info(cls):
    print("IPMI available: ", end ="")
    if cls.available():
      print("YES")
    else:
      print("NO")
      
  @classmethod
  def get_power(cls):
    try:
      out = check_output("ipmitool dcmi power reading", shell=True, stderr=DEVNULL, universal_newlines=True)
      for line in out.decode().split("\n"):
        tok = [x.strip() for x in line.split(":")]
        if tok[0] == "Instantaneous power reading":
          pwr = tok[1].split()[0]
          return float(pwr)
      return None
    except CalledProcessError:
      return None

class EnergyMonitor(object):
  def __init__(self, config):
    self.interval = int(config["monitor"]["interval"])

  @classmethod
  def from_config(cls, config):
    sens_dict = {"rapl" : PowercapEnergyMonitor, "ipmi" : IPMIEnergyMonitor }
    p = config["monitor"].get("PowerSensor", "auto").lower()
    if p == "auto":
      if IPMIEnergyMonitor.available():
        return IPMIEnergyMonitor(config)
      elif PowercapEnergyMonitor.available():
        return PowercapEnergyMonitor(config)
      else:
        raise ValueError("No power sensors found")
    else:
      if p in sens_dict:
        return sens_dict[p](config)  
      else:
        raise ValueError("Unknown power sensor: " + p)

class PowercapEnergyMonitor(EnergyMonitor):
  UJOULE, JOULE, WH = 1, 1e6, 3600*1e6
  
  @classmethod
  def available(cls):
    try:
      energy = LinuxPowercapHelper.get_package_energy(0)
      return energy > 0
    except OSError:
      return False
     
  def __init__(self, config):
    EnergyMonitor.__init__(self, config)
    self.pkg_list = LinuxPowercapHelper.package_list("psys")
    if self.pkg_list:
      self.psys_domain = True
    else:
      self.psys_domain = False
      self.pkg_list = LinuxPowercapHelper.package_list("package-")
      self.pkg_list += LinuxPowercapHelper.package_list("dram")
    self.last_energy = {}
    self.energy_range = {}
    for p in self.pkg_list:
      self.last_energy[p] = 0
      self.energy_range[p] = LinuxPowercapHelper.get_package_energy_range(p)
    self.update_energy()

  def update_energy(self, unit=JOULE):
    energy_diff = 0
    for p in self.pkg_list:
      new_energy = LinuxPowercapHelper.get_package_energy(p)
      if new_energy >= self.last_energy[p]:
        diff_uj = new_energy - self.last_energy[p]
      else:
        diff_uj = new_energy + (self.energy_range[p] - self.last_energy[p]);
      self.last_energy[p] = new_energy
      energy_diff += diff_uj
    return energy_diff / unit

class IPMIEnergyMonitor(EnergyMonitor):
  def __init__(self, config):
    EnergyMonitor.__init__(self, config)
    self.last_pwr = 0

  @classmethod
  def available(cls):
    return IPMIHelper.available()

  def update_energy(self):
    pwr = IPMIHelper.get_power()
    energy_diff = 0.5 * (self.last_pwr + pwr) * self.interval
    self.last_pwr = pwr
    return energy_diff

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
    elif c in ["none", "off"]:
      return NoEcoPolicy(config)
    else:
      raise ValueError("Unknown policy: " + [c, t])

class NoEcoPolicy(EcoPolicy):
  def __init__(self, config):
    EcoPolicy.__init__(self, config)

  def set_co2(self, co2):
    pass
    
  def reset(self):
    pass

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

  def set_freq(self, freq):
    if not self.debug:
      #CpuPowerHelper.set_max_freq(freq)  
      CpuFreqHelper.set_gov_max_freq(freq)    

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

class EcoLogger(object):
  def __init__(self, config):
    self.log_fname = LOG_FILE
    self.row_fmt = '{0:<20}\t{1:>10}\t{2:>10}\t{3:>10.3f}\t{4:>10.3f}\t{5:>10.3f}'
    self.header_fmt = self.row_fmt.replace(".3f", "")

  def print_header(self):
    print (self.header_fmt.format("Timestamp", "gCO2/kWh", "Fmax [Mhz]", "Pmax [W]", "Pavg [W]", "Energy [J]"))

  def print_row(self, co2, energy, avg_power):
    ts = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    freq = power = None
    if CpuFreqHelper.available():
      freq = round(CpuFreqHelper.get_gov_max_freq(CpuFreqHelper.MHZ))
    if LinuxPowercapHelper.available():
      max_power = LinuxPowercapHelper.get_package_power_limit(0, LinuxPowercapHelper.WATT)
    logstr = self.row_fmt.format(ts, co2, freq, max_power, avg_power, energy)

#    logstr += "\t" + str(self.co2history.min_co2()) + "\t" + str(self.co2history.max_co2())

    print (logstr)
    if self.log_fname:
      with open(self.log_fname, "a") as logf:
        logf.write(logstr + "\n")

class EcoFreq(object):
  def __init__(self, config):
    self.config = config
    self.co2provider = EmissionProvider.from_config(config)
    self.co2policy = EcoPolicy.from_config(config)
    self.co2history = CO2History(config)
    self.co2logger = EcoLogger(config)
    self.energymon = EnergyMonitor.from_config(config)
    self.debug = False

  def update_co2(self): 
    co2 = self.co2provider.get_co2()

    if co2:
      self.co2policy.set_co2(co2)
      self.co2history.add_co2(co2)
    else:
      co2 = "NA"
      
    energy = self.energymon.update_energy()
    avg_power = energy / self.co2provider.interval

    self.co2logger.print_row(co2, energy, avg_power)  

  def spin(self):
    try:
      self.co2logger.print_header()
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
  parser.add_argument("-d", dest="diag", action="store_true", help="Show system info.")
  parser.add_argument("-t", dest="co2token", default=None, help="CO2Signal token.")
  args = parser.parse_args()
  return args

def read_config(args):
  def_dict = {'emission' : { 'Provider'    : 'co2signal',
                             'Interval'    : '600'     },
              'policy'   : { 'Control'     : 'auto',    
                             'Type'        : 'Linear', 
                             'CO2Range'    : 'auto'    },        
              'monitor'  : { 'PowerSensor' : 'auto',    
                             'Interval'    : '10'       }        
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

def diag():
  LinuxPowercapHelper.info()
  print("")
  CpuFreqHelper.info()
  print("")
  IPMIHelper.info()
  print("")

if __name__ == '__main__':

  args = parse_args()
  cfg = read_config(args)
  
  diag()

  if not args.diag:
    ef = EcoFreq(cfg)
    ef.spin()
