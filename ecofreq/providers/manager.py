from ecofreq.providers.common import *
from ecofreq.providers.mqtt import *
from ecofreq.providers.rest import *

class EcoProviderManager(object):
  PROV_DICT = {"co2signal" : CO2Signal, 
               "electricitymaps" : ElectricityMapsProvider,
               "ukgrid": UKGridProvider, 
               "watttime": WattTimeProvider, 
               "stromgedacht": StromGedachtProvider,
               "energycharts": EnergyChartsProvider,
               "gridstatus.io": GridStatusIOProvider,
               "tibber": TibberProvider, 
               "octopus": OctopusProvider, 
               "awattar": AwattarProvider, 
               "mqtt": MQTTEcoProvider,
               "mock" : MockEcoProvider, 
               "const": ConstantProvider }

  def __init__(self, config):
    self.init_prov_dict()
    self.providers = {}
    self.set_config(config)
    
  def init_prov_dict(self):
    self.prov_dict = {}
    # TODO dynamic discovery
    self.prov_dict = EcoProviderManager.PROV_DICT

  def info_string(self):
    if self.providers:
      s = [m + " = " + p.info_string() for m, p in self.providers.items()]
      return  ", ".join(s)
    else:
      return "None"

  def set_config(self, config):
    self.interval = int(config["provider"]["interval"])
    for metric in ["all", EcoProvider.FIELD_CO2, EcoProvider.FIELD_PRICE, EcoProvider.FIELD_INDEX, EcoProvider.FIELD_FOSSIL_PCT]:
      if metric in config["provider"]:
        p = config["provider"].get(metric)
        if p in [None, "", "none", "off"]:
          self.providers.pop(metric, None)
        elif p.startswith("const:"):
          cfg = { metric: p.strip("const:") }
          self.providers[metric] = ConstantProvider(cfg, self.interval)
        elif p.startswith("mqtt"):
          cfg = config[p]
          self.providers[metric] = MQTTEcoProvider(cfg, self.interval, p)
#        elif p in self.PROV_DICT:
        elif p in self.prov_dict:
          try: 
            cfg = config[p]
          except KeyError:
            cfg = {}
          self.providers[metric] = self.prov_dict[p](cfg, self.interval)  
        else:
          raise ValueError("Unknown emission provider: " + p)

  def get_config(self, config={}):
    config["provider"] = {}
    config["provider"]["interval"] = self.interval
    for metric in self.providers:
      p = self.providers[metric]
      config["provider"][metric] = p.cfg_string()
      config[p.LABEL] = p.get_config()
    return config

  def get_data(self):
    data = {}
    if "all" in self.providers:
      data = self.providers["all"].get_data()
    for metric in self.providers.keys():
      if metric != "all":
        data[metric] = self.providers[metric].get_field(metric)
    return data
  
