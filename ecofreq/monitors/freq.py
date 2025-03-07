from ecofreq.monitors.common import Monitor
from ecofreq.helpers.cpu import CpuFreqHelper
from ecofreq.config import OPTION_DISABLED

class FreqMonitor(Monitor):
  def __init__(self, config):
    Monitor.__init__(self, config)
    self.period_freq = 0

  def reset_period(self):
    Monitor.reset_period(self)
    self.period_freq = 0

  @classmethod
  def from_config(cls, config):
    sens_dict = { "cpu" : CPUFreqMonitor }
    p = config["monitor"].get("FreqSensor", "auto").lower()
    monitors = []
    if p in OPTION_DISABLED:
      pass
    elif p == "auto":
      if CPUFreqMonitor.available():
        monitors.append(CPUFreqMonitor(config))
    else:
      for s in p.split(","):
        if s in sens_dict:
          monitors.append(sens_dict[s](config))  
        else:
          raise ValueError("Unknown frequency sensor: " + p)
    return monitors

class CPUFreqMonitor(FreqMonitor):
  def __init__(self, config):
    FreqMonitor.__init__(self, config)
 
  @classmethod
  def available(cls):
    return CpuFreqHelper.available()
  
  def update_freq(self):
    avg_freq = CpuFreqHelper.get_avg_gov_cur_freq()
    frac_new = 1. / (self.period_samples + 1)
    frac_old = self.period_samples * frac_new
    self.period_freq = frac_old * self.period_freq + frac_new * avg_freq

  def update_impl(self):
    self.update_freq()
    
  def get_period_avg_freq(self, unit=CpuFreqHelper.KHZ):
    return self.period_freq / unit
     
