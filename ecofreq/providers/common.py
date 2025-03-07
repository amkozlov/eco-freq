import random
import os.path
from _collections import deque

class EcoProvider(object):
  LABEL=None
  FIELD_CO2='co2'
  FIELD_PRICE='price'
  FIELD_TAX='tax'
  FIELD_FOSSIL_PCT='fossil_pct'
  FIELD_REN_PCT='ren_pct'
  FIELD_INDEX='index'
  FIELD_DEFAULT='_default'
  PRICE_UNITS= {"ct/kWh": 1.,
                "eur/kWh": 100.,
                "eur/mwh": 0.1,
                }
  
  def __init__(self, config, glob_interval):
    if "interval" in config:
      self.interval = int(config["interval"])
    else:
      self.interval = glob_interval

  def cfg_string(self):
    return self.LABEL

  def info_string(self):
    return type(self).__name__ + " (interval = " + str(self.interval) + " sec)"
  
  def get_field(self, field, data=None):
    if not data:
      data = self.get_data()
    try:
      if not field in data:
        field =self.FIELD_DEFAULT
      return float(data[field])
    except:   
      return None

  def get_co2(self, data=None):
    return self.get_field(self.FIELD_CO2, data)
    
  def get_fossil_pct(self, data=None):
    return self.get_field(self.FIELD_FOSSIL_PCT, data)

  def get_price(self, data=None):
    return self.get_field(self.FIELD_PRICE, data)

  def get_config(self):
    cfg = {}
    cfg["interval"] = self.interval
    return cfg

class ConstantProvider(EcoProvider):
  LABEL="const"

  def __init__(self, config, glob_interval):
    EcoProvider.__init__(self, config, glob_interval)
    self.set_config(config)

  def info_string(self):
    return self.cfg_string()

  def cfg_string(self):
    return "{0}:{1}".format(self.LABEL, self.data[self.metric])

  def get_config(self):
    cfg = super().get_config()
    cfg[self.metric] = self.data[self.metric]
    return cfg

  def set_config(self, config):
    self.data = {}
    for m, v in config.items():
      self.metric = m
      self.data[m] = float(v)

  def get_data(self):
    return self.data
  
class MockEcoProvider(EcoProvider):
  LABEL="mock"
  
  def __init__(self, config, glob_interval):
    EcoProvider.__init__(self, config, glob_interval)
    self.co2file = None
    self.set_config(config)

  def get_config(self):
    cfg = super().get_config()
    cfg["co2range"] = "{0}-{1}".format(self.co2min, self.co2max)
    cfg["co2file"] = self.co2file
    return cfg

  def set_config(self, config):
    co2range = '100-800'
    co2range = config.get('co2range', co2range)
    self.co2file = config.get('co2file', None)
    self.co2min, self.co2max = [int(x) for x in co2range.split("-")]
    self.read_co2_file()

  def read_co2_file(self):
    if self.co2file:
      if not os.path.isfile(self.co2file):
        raise ValueError("File not found: " + self.co2file)
      self.co2queue = deque()
      self.fossil_queue = deque()
      self.price_queue = deque()
      self.index_queue = deque()
      co2_field = 0
      fossil_field = 1
      index_field = -1
      with open(self.co2file) as f:
        for line in f:
          if line.startswith("##"):
            pass
          elif line.startswith("#"):
            toks = [x.strip() for x in line.replace("#", "", 1).split("\t")]
            try:
              co2_field = toks.index('CI [g/kWh]')
            except ValueError:
              co2_field = toks.index('gCO2/kWh')
            try:
              fossil_field = toks.index('Fossil [%]')
            except ValueError:
              fossil_field = -1
            if 'Price/kWh' in toks:
              price_field = toks.index('Price/kWh')
              price_factor = 1
            elif 'EUR/MWh'in toks:
              price_field = toks.index('EUR/MWh')
              price_factor = 0.1
            else:
              price_field = -1
            if 'co2index' in toks:  
              index_field = toks.index('co2index')
            elif 'Index' in toks:
              index_field = toks.index('Index')
          else:  
            toks = line.split("\t")
            co2 = None if toks[co2_field].strip() == "NA" else float(toks[co2_field])
            self.co2queue.append(co2)
            if fossil_field >= 0 and fossil_field < len(toks):
              fossil_pct = None if toks[fossil_field].strip() == "NA" else float(toks[fossil_field])
              self.fossil_queue.append(fossil_pct)
            if price_field >= 0 and price_field < len(toks):
              price_kwh = None if toks[price_field].strip() == "NA" else float(toks[price_field]) * price_factor
              self.price_queue.append(price_kwh)
            if index_field >= 0 and index_field < len(toks):
              index = None if toks[index_field].strip() == "NA" else toks[index_field].strip()
              self.index_queue.append(index)
    else:
      self.co2queue = None
      self.fossil_queue = None
      self.price_queue = None
      self.index_queue = None
      
  def get_data(self):
    if self.co2queue and len(self.co2queue) > 0:
      co2 = self.co2queue.popleft()
      self.co2queue.append(co2)
      fossil_pct = None
    else: 
      co2 = random.randint(self.co2min, self.co2max)
      
    if self.fossil_queue and len(self.fossil_queue) > 0:
      fossil_pct = self.fossil_queue.popleft()
      self.fossil_queue.append(fossil_pct)
    elif co2:
      fossil_pct = (co2 - self.co2min) / (self.co2max - self.co2min)
      fossil_pct = min(max(fossil_pct, 0), 1) * 100

    if self.price_queue and len(self.price_queue) > 0:
      price_kwh = self.price_queue.popleft()
      self.price_queue.append(price_kwh)
    else:
      price_kwh = None

    if self.index_queue and len(self.index_queue) > 0:
      index = self.index_queue.popleft()
      self.index_queue.append(index)
    else:
      index = None
      
    data = {}
    data[self.FIELD_CO2] = co2
    data[self.FIELD_FOSSIL_PCT] = fossil_pct
    data[self.FIELD_PRICE] = price_kwh
    data[self.FIELD_INDEX] = index
    return data
  
