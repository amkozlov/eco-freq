from ecofreq.config import OPTION_DISABLED
from ecofreq.helpers.cpu import CpuInfoHelper, CpuFreqHelper, LinuxPowercapHelper
from ecofreq.helpers.amd import AMDRaplMsrHelper
from ecofreq.helpers.nvidia import NvidiaGPUHelper
from ecofreq.helpers.ipmi import IPMIHelper
from ecofreq.monitors.common import Monitor
from ecofreq.mqtt import MQTTManager

class EnergyMonitor(Monitor):
  def __init__(self, config):
    Monitor.__init__(self, config)
    self.total_energy = 0
    self.period_energy = 0
    self.last_avg_power = 0
    self.monitor_freq = CpuFreqHelper.available()

  @classmethod
  def from_config(cls, config):
    sens_dict = {"rapl" : PowercapEnergyMonitor, "amd_msr" : AMDMsrEnergyMonitor, "ipmi" : IPMIEnergyMonitor, "gpu" : GPUEnergyMonitor }
    p = config["monitor"].get("PowerSensor", "auto").lower()
    monitors = []
    if p in OPTION_DISABLED:
      pass
    elif p == "auto":
      if IPMIEnergyMonitor.available():
        monitors.append(IPMIEnergyMonitor(config))
      else:
        if PowercapEnergyMonitor.available():
          monitors.append(PowercapEnergyMonitor(config))
        elif AMDMsrEnergyMonitor.available():
          monitors.append(AMDMsrEnergyMonitor(config))
        if NvidiaGPUHelper.available():
          monitors.append(GPUEnergyMonitor(config))
    elif p == "mqtt":
      monitors.append(MQTTEnergyMonitor(config))
    else:
      for s in p.split(","):
        if s in sens_dict:
          monitors.append(sens_dict[s](config))  
        else:
          raise ValueError("Unknown power sensor: " + p)
    return monitors

  def update_energy(self):
    energy = self.sample_energy()
#    print("energy diff:", energy)
    self.last_avg_power = energy / self.interval
    self.total_energy += energy
    self.period_energy += energy

  def update_impl(self):
    self.update_energy()
 
  def get_period_energy(self):
    return self.period_energy

  def get_total_energy(self):
    return self.total_energy

  def get_last_avg_power(self):
    return self.last_avg_power

  def get_period_avg_power(self):
    if self.period_samples:
      return self.period_energy / (self.period_samples * self.interval)
    else:
      return 0

  def get_total_avg_power(self):
    if self.total_samples:
      return self.total_energy / (self.total_samples * self.interval)
    else:
      return 0
    
  def reset_period(self):
    Monitor.reset_period(self)
    self.period_energy = 0

class NoEnergyMonitor(EnergyMonitor):
  def update_energy(self):
    pass
  
class RAPLEnergyMonitor(EnergyMonitor):
  UJOULE, JOULE, WH = 1, 1e6, 3600*1e6
  
  def __init__(self, config):
    EnergyMonitor.__init__(self, config)
    c = config['powercap'] if 'powercap' in config else {}
    self.estimate_full_power = c.get('EstimateFullPower', True)
    self.syspower_coeff_const = c.get('FullPowerConstCoeff', 0.3)
    self.syspower_coeff_var = c.get('FullPowerVarCoeff', 0.25)
    self.psys_domain = False
    self.init_pkg_list()
    self.init_energy()

  def init_energy(self):
    self.last_energy = {}
    self.energy_range = {}
    for p in self.pkg_list:
      self.last_energy[p] = 0
      self.energy_range[p] = self.get_package_energy_range(p)
    self.sample_energy()
    
  def full_system_energy(self, energy_diff):
    if self.psys_domain or not self.estimate_full_power:
      return energy_diff
    else:
      sysenergy_const = self.cpu_max_power_uw * self.syspower_coeff_const * self.interval
      sysenegy_var = (1. + self.syspower_coeff_var) * energy_diff
      return sysenergy_const + sysenegy_var 

  def sample_energy(self):
    energy_diff = 0
    for p in self.pkg_list:
      new_energy = self.get_package_energy(p)
      if new_energy >= self.last_energy[p]:
        diff_uj = new_energy - self.last_energy[p]
      else:
        diff_uj = new_energy + (self.energy_range[p] - self.last_energy[p]);
      self.last_energy[p] = new_energy
      energy_diff += diff_uj
    energy_diff = self.full_system_energy(energy_diff)
    energy_diff_j = energy_diff / self.JOULE  
    return energy_diff_j
  
class PowercapEnergyMonitor(RAPLEnergyMonitor):

  @classmethod
  def available(cls):
    try:
      energy = LinuxPowercapHelper.get_package_energy(0)
      return energy > 0
    except OSError:
      return False
     
  def __init__(self, config):
    RAPLEnergyMonitor.__init__(self, config)

  def init_pkg_list(self):
    self.pkg_list = LinuxPowercapHelper.package_list("psys")
    if self.pkg_list:
      self.psys_domain = True
    else:
      self.psys_domain = False
      self.pkg_list = LinuxPowercapHelper.package_list("package-")
      if self.pkg_list:
        if LinuxPowercapHelper.available():
          self.cpu_max_power_uw = LinuxPowercapHelper.get_package_hw_max_power(self.pkg_list[0])
        else:
          self.cpu_max_power_uw = CpuInfoHelper.get_tdp_uw()
      self.pkg_list += LinuxPowercapHelper.package_list("dram")
  
  def get_package_energy(self, pkg):
    return LinuxPowercapHelper.get_package_energy(pkg)

  def get_package_energy_range(self, pkg):
    return LinuxPowercapHelper.get_package_energy_range(pkg)

class AMDMsrEnergyMonitor(RAPLEnergyMonitor):

  @classmethod
  def available(cls):
    try:
      energy = AMDRaplMsrHelper.get_package_energy(0)
      return energy > 0
    except OSError:
      return False

  def __init__(self, config):
    RAPLEnergyMonitor.__init__(self, config)
    
  def init_pkg_list(self):
    self.pkg_list = AMDRaplMsrHelper.package_list()
    self.cpu_max_power_uw = CpuInfoHelper.get_tdp_uw()

  def get_package_energy(self, pkg):
    return AMDRaplMsrHelper.get_package_energy(pkg)

  def get_package_energy_range(self, pkg):
    return AMDRaplMsrHelper.get_package_energy_range(pkg)


class GPUEnergyMonitor(EnergyMonitor):
  def __init__(self, config):
    EnergyMonitor.__init__(self, config)
    self.last_pwr = 0

  @classmethod
  def available(cls):
    return NvidiaGPUHelper.available()

  def sample_energy(self):
    cur_pwr = NvidiaGPUHelper.get_power()
    if not cur_pwr:
      print ("WARNING: GPU power reading failed!")
      cur_pwr = self.last_pwr
    avg_pwr = 0.5 * (self.last_pwr + cur_pwr)
    energy_diff = avg_pwr * self.interval
    self.last_pwr = cur_pwr
    return energy_diff

class IPMIEnergyMonitor(EnergyMonitor):
  def __init__(self, config):
    EnergyMonitor.__init__(self, config)
    self.last_pwr = 0

  @classmethod
  def available(cls):
    return IPMIHelper.available()

  def sample_energy(self):
    cur_pwr = IPMIHelper.get_power()
    if not cur_pwr:
      print ("WARNING: IPMI power reading failed!")
      cur_pwr = self.last_pwr
    avg_pwr = 0.5 * (self.last_pwr + cur_pwr)
    energy_diff = avg_pwr * self.interval
    self.last_pwr = cur_pwr
    return energy_diff

class MQTTEnergyMonitor(EnergyMonitor):
  def __init__(self, config):
    EnergyMonitor.__init__(self, config)
    self.last_pwr = 0
    self.label = "mqtt_power"
    mqtt_cfg = config[self.label]
    self.interval = int(mqtt_cfg.get("interval", self.interval))    
    self.mqtt_client = MQTTManager.add_client(self.label, mqtt_cfg)

  @classmethod
  def available(cls):
    return True

  def sample_energy(self):
    cur_pwr = self.mqtt_client.get_msg()
    if not cur_pwr:
      print ("WARNING: MQTT power reading failed!")
      cur_pwr = self.last_pwr
    else:
      cur_pwr = float(cur_pwr)
    avg_pwr = 0.5 * (self.last_pwr + cur_pwr)
    energy_diff = avg_pwr * self.interval
    self.last_pwr = cur_pwr
    return energy_diff
    
