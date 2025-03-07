from ecofreq.providers.common import EcoProvider
from ecofreq.policy.cpu import CPUEcoPolicy
from ecofreq.policy.gpu import GPUEcoPolicy

class EcoPolicyManager(object):
  def __init__(self, config):
    self.policies = []
    cfg_dict = {"cpu": None, "gpu": None}
    if "policy" in config:
      cfg_dict["gpu"] = cfg_dict["cpu"] = dict(config.items("policy"))  
    if "cpu_policy" in config:
      cfg_dict["cpu"] = dict(config.items("cpu_policy"))
    if "gpu_policy" in config:
      cfg_dict["gpu"] = dict(config.items("gpu_policy"))
    cfg_dict["metric"] = cfg_dict["cpu"].get("metric", "co2")  
    self.set_config(cfg_dict)
    
  def info_string(self):
    if self.policies:
      s = [p.info_string() for p in self.policies]
      s.append("metric = " + self.metric)
      return  ", ".join(s)
    else:
      return "None"

  def clear(self):
    self.reset()
    self.policies = []

  def set_config(self, cfg):
    if not cfg:
      self.clear()
      return
    self.metric = cfg.get("metric", "co2")
    if "cpu" in cfg or "gpu" in cfg:
      all_cfg = None
    else:
      all_cfg = cfg
    cpu_cfg = cfg.get("cpu", all_cfg)
    gpu_cfg = cfg.get("gpu", all_cfg)
    cpu_pol = CPUEcoPolicy.from_config(cpu_cfg)
    gpu_pol = GPUEcoPolicy.from_config(gpu_cfg)
    self.clear()
    if cpu_pol:
      self.policies.append(cpu_pol)
    if gpu_pol:
      self.policies.append(gpu_pol)

  def get_config(self):
    res = {}
    for p in self.policies:
      domain = "global"
      if issubclass(type(p), CPUEcoPolicy):
        domain = "cpu"
      elif issubclass(type(p), GPUEcoPolicy):
        domain = "gpu"
      res[domain] = p.get_config({})
      res[domain]["metric"] = self.metric
    return res
    
  def set_co2(self, co2_data):
    if self.metric == "price":
      field = EcoProvider.FIELD_PRICE
    elif self.metric == "fossil_pct":
      field = EcoProvider.FIELD_FOSSIL_PCT
    elif self.metric == "ren_pct":
      field = EcoProvider.FIELD_REN_PCT
    elif self.metric == "index":
      field = EcoProvider.FIELD_INDEX
    else:
      field = EcoProvider.FIELD_CO2
    if co2_data[field]:
      val = co2_data[field]
      for p in self.policies:
        p.set_co2(val)

  def reset(self):
    for p in self.policies:
      p.reset()
