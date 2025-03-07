import sys
from inspect import isclass

from ecofreq.helpers.cpu import CpuInfoHelper, CpuFreqHelper, LinuxPowercapHelper
from ecofreq.helpers.amd import AMDEsmiHelper
from ecofreq.helpers.cgroup import LinuxCgroupHelper, LinuxCgroupV1Helper, LinuxCgroupV2Helper
from ecofreq.helpers.docker import DockerHelper
from ecofreq.policy.common import EcoPolicy
from ecofreq.config import OPTION_DISABLED


class CPUEcoPolicy(EcoPolicy):
  def __init__(self, config):
    EcoPolicy.__init__(self, config)

  @classmethod
  def from_config(cls, config):
    if not config:
      return None

    # first, check if we have a specific EcoPolicy class
    c = config["control"]
    if c in globals(): 
      cls = globals()[c]
      if isclass(cls) and issubclass(cls, CPUEcoPolicy):
        return cls(config)
    
    # otherwise, look for a generic policy type
    c = c.lower()
    if c == "auto":
      if LinuxPowercapHelper.available() and LinuxPowercapHelper.enabled():
        c = "power"
      elif AMDEsmiHelper.available() and AMDEsmiHelper.enabled():
        c = "power"
      elif CpuFreqHelper.available():
        c = "frequency"
      else:
        print ("ERROR: Power management interface not found!")
        sys.exit(-1)

    if c == "power":
      return CPUPowerEcoPolicy(config)
    elif c == "frequency":
      return CPUFreqEcoPolicy(config)
    elif c == "cgroup":
      return CPUCgroupEcoPolicy(config)
    elif c == "docker":
      return CPUDockerEcoPolicy(config)
    elif c in OPTION_DISABLED:
      return None
    else:
      raise ValueError("Unknown policy: " + c)

class CPUFreqEcoPolicy(CPUEcoPolicy):
  UNIT={"MHz": CpuFreqHelper.MHZ}
  
  def __init__(self, config):
    CPUEcoPolicy.__init__(self, config)
    self.driver = CpuFreqHelper.get_driver()
   
    if not self.driver:
      print ("ERROR: CPU frequency scaling driver not found!")
      sys.exit(-1)

    self.fmin = CpuFreqHelper.get_hw_min_freq()
    self.fmax = CpuFreqHelper.get_hw_max_freq()
    self.fstart = CpuFreqHelper.get_gov_max_freq()
    self.init_governor(config, self.fmin, self.fmax)

  def set_freq(self, freq):
    if freq and not self.debug:
      #CpuPowerHelper.set_max_freq(freq)  
      CpuFreqHelper.set_gov_max_freq(freq)    

  def set_co2(self, co2):
    self.freq = self.co2val(co2)
    self.set_freq(self.freq)

  def reset(self):
    self.set_freq(self.fmax)

class CPUPowerEcoPolicy(CPUEcoPolicy):
  UNIT={"W": 1}
  
  def __init__(self, config):
    EcoPolicy.__init__(self, config)
    
    if AMDEsmiHelper.available():
      self.helper = AMDEsmiHelper
    else:
      self.helper = LinuxPowercapHelper   
    
      if not LinuxPowercapHelper.available():
        print ("ERROR: RAPL powercap driver not found!")
        sys.exit(-1)
  
      if not LinuxPowercapHelper.enabled():
        print ("ERROR: RAPL driver found, but powercap is disabled!")
        print ("Please try to enable it as described here: https://askubuntu.com/a/1231490")
        print ("If it does not work, switch to frequency control policy.")
        sys.exit(-1)

    self.pmax = self.helper.get_package_hw_max_power(0, self.helper.WATT)
    self.pmin = 0.1 * self.pmax
    self.pstart = self.helper.get_package_power_limit(0, self.helper.WATT)
    self.init_governor(config, self.pmin, self.pmax)

  def set_power(self, power_w):
    if power_w and not self.debug:
      self.helper.set_power_limit(power_w, self.helper.WATT)

  def set_co2(self, co2):
    self.power = self.co2val(co2)
#  print("Update policy co2 -> power:", co2, "->", self.power)
    self.set_power(self.power)

  def reset(self):
    self.set_power(self.pmax)

class CPUCgroupEcoPolicy(CPUEcoPolicy):
  UNIT={"c": 1}

  def __init__(self, config):
    EcoPolicy.__init__(self, config)
    
    if not LinuxCgroupV1Helper.available():
      print ("ERROR: Linux cgroup filesystem not mounted!")
      sys.exit(-1)

    if LinuxCgroupV1Helper.enabled():
      self.helper = LinuxCgroupV1Helper
    elif LinuxCgroupV2Helper.enabled():
      self.helper = LinuxCgroupV2Helper
    else:    
      print ("ERROR: Linux cgroup subsystem is not properly configured!")
      sys.exit(-1)

    self.grp = "user.slice" if "cgroup" not in config else config["cgroup"]
    self.use_freeze = True if "cgroupfreeze" not in config else config["cgroupfreeze"]
    self.use_freeze = self.use_freeze and self.helper.enabled("freezer", self.grp)
    
    if not self.helper.enabled("cpu", self.grp):
      print ("ERROR: Linux cgroup not found or cpu controller is disabled:", self.grp)
      sys.exit(-1)
    
    num_cores = CpuInfoHelper.get_cores()
    self.qmax = num_cores
    self.qmin = 0
    self.qstart = self.helper.get_cpu_quota(self.grp, num_cores)
    self.init_governor(config, self.qmin, self.qmax)

  def set_quota(self, quota):
    if self.use_freeze:
      if quota == self.qmin:
        self.helper.freeze(self.grp)
        return
      else:
        self.helper.unfreeze(self.grp)
    if quota and not self.debug:
      self.helper.set_cpu_quota(self.grp, quota)

  def set_co2(self, co2):
    self.quota = self.co2val(co2)
#    print("Update policy co2 -> power: ", co2, "->", self.power)
    self.set_quota(self.quota)

  def reset(self):
    self.set_quota(self.qmax)

class CPUDockerEcoPolicy(CPUEcoPolicy):
  UNIT={"c": 1}
  UNLIMITED=0.0

  def __init__(self, config):
    EcoPolicy.__init__(self, config)
    
    if not DockerHelper.available():
      print ("ERROR: Docker not found!")
      sys.exit(-1)

    self.ctrs = [] if "containers" not in config else config["containers"].split(",")
    self.use_freeze = False if "cgroupfreeze" not in config else config["cgroupfreeze"]
    num_cores = CpuInfoHelper.get_cores() if "maxcpus" not in config else float(config["maxcpus"])
    self.qmax = num_cores
    self.qmin = 0
    self.qstart = self.UNLIMITED
    self.init_governor(config, self.qmin, self.qmax)

  def set_quota(self, cpu_quota):
    if self.debug:
      return
    if self.use_freeze:
      if cpu_quota == self.qmin:
        DockerHelper.set_pause(self.ctrs, True)
        return
      else:
        DockerHelper.set_pause(self.ctrs, False)
    if cpu_quota:
      DockerHelper.set_container_cpus(self.ctrs, cpu_quota)

  def set_co2(self, co2):
    self.quota = self.co2val(co2)
#    print("Update policy co2 -> power: ", co2, "->", self.power)
    self.set_quota(self.quota)

  def reset(self):
    self.set_quota(self.qstart)
