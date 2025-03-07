from subprocess import check_output,DEVNULL

from ecofreq.utils import *
from ecofreq.monitors.common import Monitor
from ecofreq.config import OPTION_DISABLED

class IdleMonitor(Monitor):
  CMD_SESSION_COUNT="w -h | wc -l"
  LOADAVG_FILE="/proc/loadavg"
  LOADAVG_M1=1
  LOADAVG_M5=2
  LOADAVG_M15=3
  
  @classmethod
  def from_config(cls, config):
    monitors = []
    p = "on"
    if config.has_section("idle"): 
      p = config["idle"].get("IdleMonitor", p).lower()
    if p not in OPTION_DISABLED:
      monitors.append(IdleMonitor(config))
    return monitors
  
  def __init__(self, config):
    Monitor.__init__(self, config)
    c = config['idle'] if 'idle' in config else {}
    self.load_cutoff = float(c.get('LoadCutoff', 0.05))
    self.load_period = int(c.get('LoadPeriod', 1))
    if self.load_period not in [self.LOADAVG_M1, self.LOADAVG_M5, self.LOADAVG_M15]:
      raise ValueError("IdleMonitor: Unknown load period: " + self.load_period)
    self.reset()

  def reset_period(self):
    Monitor.reset_period(self)
    self.max_sessions = 0
    self.max_load = 0.

  def reset(self):
    self.idle_duration = 0
    self.last_sessions = 0
    self.last_load = 0.
    self.reset_period()

  def active_sessions(self):
    out = check_output(self.CMD_SESSION_COUNT, shell=True, stderr=DEVNULL, universal_newlines=True)
    return int(out)    

  def active_load(self):
    return float(read_value(self.LOADAVG_FILE, self.load_period))

  def update_impl(self):
    self.last_sessions = self.active_sessions()
    self.last_load = self.active_load()
    self.max_sessions = max(self.max_sessions, self.last_sessions)
    self.max_load = max(self.max_load, self.last_load)
    if self.get_period_idle() == "IDLE":
      self.idle_duration += self.interval
    else:
      self.idle_duration = 0
    
  def get_state(self, sessions, load):
    if sessions > 0 and load > self.load_cutoff:
      return "ACTIVE"
    elif sessions > 0:
      return "SESSION"
    elif load > self.load_cutoff:
      return "LOAD"
    else:
      return "IDLE"

  def get_period_idle(self):
    return self.get_state(self.max_sessions, self.max_load)

  def get_last_idle(self):
    return self.get_state(self.last_sessions, self.last_load)
    
  def get_stats(self):
    return {"State": self.get_period_idle(),
            "LastState": self.get_last_idle(),
            "MaxSessions": self.max_sessions,
            "LastSessions": self.last_sessions,
            "MaxLoad": self.max_load,
            "LastLoad": self.last_load,
            "IdleDuration": self.idle_duration }

