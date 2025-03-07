import sys
from inspect import isclass

from ecofreq.helpers.nvidia import NvidiaGPUHelper
from ecofreq.policy.common import EcoPolicy
from ecofreq.config import OPTION_DISABLED

class GPUEcoPolicy(EcoPolicy):
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
      if isclass(cls) and issubclass(cls, GPUEcoPolicy):
        return cls(config)

    # otherwise, look for a generic policy type
    c = c.lower()
    if c == "auto":
      if NvidiaGPUHelper.available():
        c = "power"
#      elif CpuFreqHelper.available():
#        c = "frequency"
      else:
        return None

    if c == "power":
      return GPUPowerEcoPolicy(config)
    elif c == "frequency":
      return GPUFreqEcoPolicy(config)
    elif c == "cgroup":
      # cgroup currently does not support GPUs, so let's rely on CPU scaling 
      return None
    elif c in OPTION_DISABLED:
      return None
    else:
      raise ValueError("Unknown policy: " + c)

class GPUPowerEcoPolicy(GPUEcoPolicy):
  UNIT={"W": 1}
  
  def __init__(self, config):
    GPUEcoPolicy.__init__(self, config)
    
    if not NvidiaGPUHelper.available():
      print ("ERROR: NVIDIA driver not found!")
      sys.exit(-1)

    plinfo = NvidiaGPUHelper.get_power_limit_all() 
    self.pmin = float(plinfo[0][0])
    self.pmax = float(plinfo[0][1])
    self.pstart = float(plinfo[0][2])
    self.init_governor(config, self.pmin, self.pmax, 0)

  def set_power(self, power_w):
    if power_w and not self.debug:
      NvidiaGPUHelper.set_power_limit(power_w)

  def set_co2(self, co2):
    self.power = self.co2val(co2)
#    print("Update policy co2 -> power: ", co2, "->", self.power)
    self.set_power(self.power)

  def reset(self):
    self.set_power(self.pmax)

class GPUFreqEcoPolicy(GPUEcoPolicy):
  UNIT={"MHz": 1}
  
  def __init__(self, config):
    GPUEcoPolicy.__init__(self, config)
    
    if not NvidiaGPUHelper.available():
      print ("ERROR: NVIDIA driver not found!")
      sys.exit(-1)

    self.fmax = NvidiaGPUHelper.get_hw_max_freq()[0]
    self.fmin = self.fmax * 0.3
    self.init_governor(config, self.fmin, self.fmax, 0)

  def set_freq(self, freq):
    if freq and not self.debug:
      NvidiaGPUHelper.set_freq_limit(freq)    

  def set_co2(self, co2):
    self.freq = self.co2val(co2)
    self.set_freq(self.freq)

  def reset(self):
    NvidiaGPUHelper.reset_freq_limit()
