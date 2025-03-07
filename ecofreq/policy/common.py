from ecofreq.policy.governor import Governor

class EcoPolicy(object):
  UNIT={}
  def __init__(self, config):
    self.debug = False

  def info_string(self):
    g = self.governor.info_string(self.UNIT) if self.governor else "None" 
    return type(self).__name__ + " (governor = " + g + ")" 

  def init_governor(self, config, vmin, vmax, vround=None):
    self.governor = Governor.from_config(config, vmin, vmax, self.UNIT)
    if self.governor and vround:
      self.governor.val_round = vround
      
  def get_config(self, config={}):
    config["control"] = type(self).__name__
    config["governor"] = self.governor.info_string(self.UNIT) if self.governor else "none"
    return config
  
  def co2val(self, co2):
    if self.governor:
      return self.governor.co2val(co2)
    else:
      return None
