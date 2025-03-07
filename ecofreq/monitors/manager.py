from math import ceil

from ecofreq.monitors.energy import EnergyMonitor
from ecofreq.monitors.freq import FreqMonitor, CPUFreqMonitor
from ecofreq.monitors.idle import IdleMonitor

class MonitorManager(object):
  def __init__(self, config):
    self.monitors = EnergyMonitor.from_config(config)
    self.monitors += FreqMonitor.from_config(config)
    self.monitors += IdleMonitor.from_config(config)
    
  def info_string(self):
    s = []
    for m in self.monitors:
      s.append(type(m).__name__ + " (interval = " + str(m.interval) + " sec)")
    return ", ".join(s)

  def adjust_interval(self, period):
    min_interval = min([m.interval for m in self.monitors])
    int_ratio = ceil(period / min_interval)
    sample_interval = round(period / int_ratio)
    for m in self.monitors:
      if m.interval % sample_interval > 0:
        m.interval = sample_interval * int(m.interval / sample_interval)
    return sample_interval

  def update(self, duration):
    for m in self.monitors:
      if duration % m.interval == 0:
        m.update()
      
  def reset_period(self):
    for m in self.monitors:
      m.reset_period()

  def get_reading(self, metric, domain, method):
    for m in self.monitors:
      pass
    
  def get_period_energy(self):
    result = 0
    for m in self.monitors:
      if issubclass(type(m), EnergyMonitor):
        result += m.get_period_energy()
    return result

  def get_total_energy(self):
    result = 0
    for m in self.monitors:
      if issubclass(type(m), EnergyMonitor):
        result += m.get_total_energy()
    return result

  def get_period_avg_power(self):
    result = 0
    for m in self.monitors:
      if issubclass(type(m), EnergyMonitor):
        result += m.get_period_avg_power()
    return result

  def get_last_avg_power(self):
    result = 0
    for m in self.monitors:
      if issubclass(type(m), EnergyMonitor):
        result += m.get_last_avg_power()
    return result

  def get_period_cpu_avg_freq(self, unit):
    for m in self.monitors:
      if issubclass(type(m), CPUFreqMonitor):
        return m.get_period_avg_freq(unit)
    return None
  
  def get_period_idle(self):
    for m in self.monitors:
      if issubclass(type(m), IdleMonitor):
        return m.get_period_idle()
    return None
  
  def get_by_class(self, cls):
    for m in self.monitors:
      if issubclass(type(m), cls):
        return m
    return None

  def get_stats(self):
    stats = {}
    for m in self.monitors:
      stats.update(m.get_stats())
    return stats
