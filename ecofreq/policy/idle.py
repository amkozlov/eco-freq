from ecofreq.monitors.idle import IdleMonitor
from ecofreq.helpers.suspend import SuspendHelper

class IdlePolicy(object):
  
  @classmethod
  def from_config(cls, config):
    p = None
    if "idle" in config:
      if "SuspendAfter" in config["idle"]:
        p = SuspendIdlePolicy(config)
    return p
    
  def init_monitors(self, monman):
    self.idlemon = monman.get_by_class(IdleMonitor)

  def init_logger(self, logger):
    self.log = logger
    
  def info_string(self):
    return type(self).__name__ + " (timeout = " + str(self.idle_timeout) + " sec)"

  def check_idle(self):
    if self.idlemon and self.idlemon.idle_duration > self.idle_timeout:
      duration = self.idlemon.idle_duration
      self.idlemon.reset()
      self.on_idle(duration)
      return True
    else:
      return False

  def on_idle(self, idle_duration):
    pass
  
class SuspendIdlePolicy(IdlePolicy):
  def __init__(self, config):
    self.idle_timeout = int(config["idle"].get('SuspendAfter', 600))
    self.mode = config["idle"].get('SuspendMode', SuspendHelper.S2RAM)

  def on_idle(self, idle_duration):
    if self.log:
      self.log.print_cmd("suspend")
    SuspendHelper.suspend(self.mode)   
