import sys
import time
from datetime import datetime

import urllib.request
import requests
from requests.auth import HTTPBasicAuth
import json

from ecofreq.utils import getbool
from ecofreq.helpers.geo import GeoHelper
from ecofreq.providers.common import EcoProvider

class CO2Signal(EcoProvider):
  LABEL="co2signal"
  URL_BASE = "https://api.co2signal.com/v1/latest?"
  URL_COUNTRY = URL_BASE + "countryCode={0}"
  URL_COORD = URL_BASE + "lat={0}&lon={1}"
  FIELD_MAP = {EcoProvider.FIELD_CO2: "carbonIntensity", 
               EcoProvider.FIELD_FOSSIL_PCT: "fossilFuelPercentage"}
  
  def __init__(self, config, glob_interval):
    EcoProvider.__init__(self, config, glob_interval)
    self.set_config(config)
    
  def get_config(self):
    cfg = super().get_config()
    cfg["token"] = self.co2token
    cfg["country"] = self.co2country
    return cfg

  def set_config(self, config):
    self.co2country = config["country"]
    self.co2token = config["token"]

    if not self.co2token:
      print ("ERROR: Please specify CO2Signal API token!")
      sys.exit(-1)
      
    if self.co2country.lower().startswith("auto"):
      self.coord_lat, self.coord_lon = GeoHelper.get_my_coords()
      if not self.coord_lat or not self.coord_lon:
        print ("ERROR: Failed to autodetect location!")
        print ("Please make sure you have internet connetion, or specify country code in the config file.")
        sys.exit(-1)
      
    self.update_url()

  def remap(self, jsdict):
    data = {}
    for k, v in self.FIELD_MAP.items():
      data[k] = jsdict[v]
    return data

  def update_url(self):
    if not self.co2country.lower().startswith("auto"):
      self.api_url = self.URL_COUNTRY.format(self.co2country)
    else:
      self.api_url = self.URL_COORD.format(self.coord_lat, self.coord_lon)

  def get_data(self):
    req = urllib.request.Request(self.api_url)
    req.add_header("User-Agent", "Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11")
    req.add_header("auth-token", self.co2token)

    try:
      resp = urllib.request.urlopen(req).read()
      js = json.loads(resp)
      data = self.remap(js['data'])
    except:
      e = sys.exc_info()[0]
      print ("Exception: ", e)
      data = None
    return data

class ElectricityMapsProvider(EcoProvider):
  LABEL="electricitymaps"
  URL_BASE = "https://api.electricitymap.org/v3/"
  URL_CO2_PARAMS = "?disableEstimations={}&emissionFactorType={}"
  URL_MIX_PARAMS = "?disableEstimations={}"
  URL_CO2 = URL_BASE + "carbon-intensity/"
  URL_CO2_NOW = URL_CO2 + "latest" + URL_CO2_PARAMS
  URL_MIX = URL_BASE + "power-breakdown/"
  URL_MIX_NOW = URL_MIX + "latest" + URL_MIX_PARAMS
  URL_ZONE = "&zone={}"
  URL_COORD = "&lat={0}&lon={1}"
  FIELD_MAP = {EcoProvider.FIELD_CO2: "carbonIntensity", 
               EcoProvider.FIELD_REN_PCT: 'renewablePercentage',
               EcoProvider.FIELD_FOSSIL_PCT: "fossilFuelPercentage"}
  
  def __init__(self, config, glob_interval):
    EcoProvider.__init__(self, config, glob_interval)
    self.set_config(config)
    
  def get_config(self):
    cfg = super().get_config()
    cfg["zone"] = self.zone
    cfg["disableestimations"] = self.noestimates
    cfg["emissionfactortype"] = self.eftype
    if self.token:
      cfg["token"] = self.token
    return cfg

  def set_config(self, config):
    self.zone = config.get("zone", "auto")
    self.token = config.get("token", None)
    self.noestimates = config.get("disableestimations", False)
    self.eftype = config.get("emissionfactortype", "lifecycle")

    if self.zone.lower().startswith("auto"):
      self.coord_lat, self.coord_lon = GeoHelper.get_my_coords()
      if not self.coord_lat or not self.coord_lon:
        print ("ERROR: Failed to autodetect location!")
        print ("Please make sure you have internet connetion, or specify country code in the config file.")
        sys.exit(-1)
      
    self.update_url()

  def remap(self, jsco2, jsmix):
    data = {}
    for k, v in self.FIELD_MAP.items():
      if v in jsco2:
        data[k] = jsco2[v]
      elif v in jsmix:
        data[k] = jsmix[v]
        
    data[EcoProvider.FIELD_FOSSIL_PCT] = 100 - jsmix["fossilFreePercentage"]      
        
    return data

  def url_zone(self):
    if not self.zone.lower().startswith("auto"):
      return self.URL_ZONE.format(self.zone)
    else:
      return self.URL_COORD.format(self.coord_lat, self.coord_lon)

  def update_url(self):
    zone_param = self.url_zone()
    self.api_url_co2 = self.URL_CO2_NOW.format(self.noestimates, self.eftype) + zone_param
    self.api_url_mix = self.URL_MIX_NOW.format(self.noestimates) + zone_param

  def fetch_json(self, url):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11")
    if self.token:
      req.add_header("auth-token", self.token)

    try:
      resp = urllib.request.urlopen(req).read()
      js = json.loads(resp)
      return js
    except:
      e = sys.exc_info()
      print ("Exception: ", e)
      return None

  def get_data(self):
    jsco2 = self.fetch_json(self.api_url_co2)
    jsmix = self.fetch_json(self.api_url_mix)
    data = self.remap(jsco2, jsmix)
    return data 

class UKGridProvider(EcoProvider):
  LABEL="ukgrid"
  URL_BASE = " https://api.carbonintensity.org.uk/"
  URL_COUNTRY = URL_BASE + "intensity"
  URL_REGIONAL = URL_BASE + "regional/"
  URL_REGION = URL_REGIONAL + "regionid/{0}"
  URL_POSTCODE = URL_REGIONAL + "postcode/{0}"
  FIELD_MAP = {EcoProvider.FIELD_CO2: "forecast", EcoProvider.FIELD_INDEX: "index"}
  
  def __init__(self, config, glob_interval):
    EcoProvider.__init__(self, config, glob_interval)
    self.set_config(config)
    
  def get_config(self):
    cfg = super().get_config()
    if self.region:
      cfg["regionid"] = self.region
    if self.postcode:
      cfg["postcode"] = self.postcode
    return cfg

  def set_config(self, config):
    self.region = config.get("regionid", None)
    self.postcode = config.get("postcode", None)
    self.update_url()

  def remap(self, jsdict):
#    print(jsdict)
    data = {}
    jsdata = jsdict[0]
    if "data" in jsdata:
      jsdata = jsdata["data"][0]
    jsci = jsdata["intensity"]  
    for k, v in self.FIELD_MAP.items():
      data[k] = jsci[v]
#    print(jsdata)
    if "generationmix" in jsdata:
      fossil_pct = 0
      for f in jsdata["generationmix"]:
        if f["fuel"] in ["coal", "gas", "other"]:
          fossil_pct += float(f["perc"])
      data[EcoProvider.FIELD_FOSSIL_PCT] = fossil_pct
#      print(fossil_pct)
    return data

  def update_url(self):
    if self.postcode:
      self.api_url = self.URL_POSTCODE.format(self.postcode)
    elif self.region:
      self.api_url = self.URL_REGION.format(self.region)
    else:
      self.api_url = self.URL_COUNTRY

  def get_data(self):
    req = urllib.request.Request(self.api_url)
    req.add_header("User-Agent", "Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11")
    req.add_header("Accept", "application/json")

    try:
      resp = urllib.request.urlopen(req).read()
      js = json.loads(resp)
      data = self.remap(js['data'])
    except:
      e = sys.exc_info()
      print ("Exception: ", e)
      data = None
    return data

class StromGedachtProvider(EcoProvider):
  LABEL="stromgedacht"
  URL_BASE = "https://api.stromgedacht.de/v1/"
  URL_POSTCODE = "?zip={0}"
  URL_NOW = URL_BASE + "now" + URL_POSTCODE
  URL_FORECAST = URL_BASE + "forecast" + URL_POSTCODE
  STATE_MAP = {-1: "supergreen", 1: "green", 3: "orange", 4: "red"}
  
  def __init__(self, config, glob_interval):
    EcoProvider.__init__(self, config, glob_interval)
    self.set_config(config)
    
  def get_config(self):
    cfg = super().get_config()
    if self.postcode:
      cfg["postcode"] = self.postcode
    return cfg

  def set_config(self, config):
    self.postcode = config.get("postcode", 70173)
    self.intstates = config.get("integerstates", False)
    self.update_url()

  def get_val_now(self, ts, arr):
    last_val = None
    last_ts = None
    for e in arr:
      t =  datetime.fromisoformat(e["dateTime"].replace('Z', '' ))
      if last_ts and ts >= last_ts and  ts < t:
        return last_val 
      else:
        last_ts = t
        last_val = int(e["value"])
    return None

  def remap(self, jsnow, jsforecast):
    data = {}
    s = jsnow["state"]
    data[EcoProvider.FIELD_INDEX] = s if self.intstates else self.STATE_MAP[s]
      
    ts = datetime.utcnow()
    load = self.get_val_now(ts, jsforecast["load"])
    renewableEnergy = self.get_val_now(ts, jsforecast["renewableEnergy"])
    residualLoad = self.get_val_now(ts, jsforecast["residualLoad"])
    superGreenThreshold = self.get_val_now(ts, jsforecast["superGreenThreshold"])
      
#    print(load, renewableEnergy, residualLoad, superGreenThreshold)
    data[EcoProvider.FIELD_FOSSIL_PCT] = 100. * (residualLoad - superGreenThreshold) / load
    return data

  def update_url(self):
    self.api_url_now = self.URL_NOW.format(self.postcode)
    self.api_url_forecast = self.URL_FORECAST.format(self.postcode)

  def fetch_json(self, url):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11")
    req.add_header("Accept", "application/json")

    try:
      resp = urllib.request.urlopen(req).read()
      js = json.loads(resp)
      return js
    except:
      e = sys.exc_info()
      print ("Exception: ", e)
      return None

  def get_data(self):
    jsnow = self.fetch_json(self.api_url_now)
    jsforecast = self.fetch_json(self.api_url_forecast)
    data = self.remap(jsnow, jsforecast)
    return data 

class EnergyChartsProvider(EcoProvider):
  LABEL="energycharts"
  URL_BASE = "https://api.energy-charts.info/"
  URL_COUNTRY = "?country={0}"
  URL_PRICE_ZONE = "?bzn={}"
  URL_POSTCODE = "&postal_code={}"
  URL_PERIOD = "&start={}&end={}"
  URL_SIGNAL = URL_BASE + "signal" + URL_COUNTRY
  URL_PRICE = URL_BASE + "price" + URL_PRICE_ZONE
  STATE_MAP = {-1: "black", 0: "red", 1: "yellow", 2: "green"}
  
  def __init__(self, config, glob_interval):
    EcoProvider.__init__(self, config, glob_interval)
    self.set_config(config)
    
  def get_config(self):
    cfg = super().get_config()
    cfg["country"] = self.country
    cfg["integerstates"] = self.intstates
    if self.postcode:
      cfg["postcode"] = self.postcode
    if self.pricezone:
      cfg["pricezone"] = self.pricezone
    return cfg

  def set_config(self, config):
    self.country = config.get("country", "de").lower()
    self.postcode = config.get("postcode", None)
    self.pricezone = config.get("pricezone", None)
    self.intstates = config.get("integerstates", False)
    self.update_url()

  def get_val_now_idx(self, ts, arr):
    idx = -1
    last_ts = None
    for t in arr:
      if last_ts and ts >= last_ts and ts < t:
        return idx 
      else:
        last_ts = t
        idx += 1
    return None

  def remap(self, jssignal, jsprice):
    data = {}
    
    ts = int(time.time())

    if jssignal:
      idx = self.get_val_now_idx(ts, jssignal["unix_seconds"])
      s = int(jssignal["signal"][idx])
      data[EcoProvider.FIELD_INDEX] = s if self.intstates else self.STATE_MAP[s]
      data[EcoProvider.FIELD_REN_PCT] = jssignal["share"][idx] 
      
    if jsprice:
      idx = self.get_val_now_idx(ts, jsprice["unix_seconds"])
      p = float(jsprice["price"][idx])
      if 'unit' in jsprice:
        unit = jsprice['unit'].lower()
        p *= EcoProvider.PRICE_UNITS.get(unit, 1)    
      data[EcoProvider.FIELD_PRICE] = p   

#    print(data)
    return data

  def update_url(self):
    self.api_url_signal = self.URL_SIGNAL.format(self.country)
    if self.postcode:
      self.api_url_signal +=  self.URL_POSTCODE.format(self.postcode)
    if self.pricezone:
      self.api_url_price = self.URL_PRICE.format(self.pricezone.upper())
    else:
      self.api_url_price = None

  def fetch_json(self, url):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11")
    req.add_header("Accept", "application/json")

    try:
      resp = urllib.request.urlopen(req).read()
      js = json.loads(resp)
      return js
    except:
      e = sys.exc_info()
      print ("Exception: ", e)
      return None

  def get_data(self):
    jssignal = self.fetch_json(self.api_url_signal)
    if self.api_url_price:
      ts = time.time()
      tsdelta = 4*3600 
      fmt = '%Y-%m-%dT%H:%M'
      start = datetime.utcfromtimestamp(ts-tsdelta).strftime(fmt) 
      end = datetime.utcfromtimestamp(ts+tsdelta).strftime(fmt) 
      url = self.api_url_price + self.URL_PERIOD.format(start, end)
      jsprice = self.fetch_json(url)
    else:
      jsprice = None
    data = self.remap(jssignal, jsprice)
    return data 

class GridStatusIOProvider(EcoProvider):
  LABEL="gridstatus.io"
  TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
  PRICE_UNIT = "eur/mwh"
  URL_BASE = "https://api.gridstatus.io/v1/"
  URL_QUERY = URL_BASE + "datasets/{}/query"
  URL_ISO = "/iso/{}"
  URL_LOCATION = "/location/{}"
  URL_PERIOD = "?start_time={}"
  URL_LATEST = URL_QUERY.format("isos_latest") + URL_ISO
  URL_FORECAST = URL_QUERY + URL_LOCATION + URL_PERIOD
  
  def __init__(self, config, glob_interval):
    EcoProvider.__init__(self, config, glob_interval)
    self.set_config(config)
    self.cached_data = None
    
  def get_config(self):
    cfg = super().get_config()
    cfg["token"] = self.token
    cfg["iso"] = self.iso
    cfg["pricefield"] = self.price_field
    if self.location:
      cfg["location"] = self.location
    if self.dataset:
      cfg["dataset"] = self.dataset
    return cfg

  def set_config(self, config):
    self.token = config.get("token", None)
    self.iso = config.get("iso", "caiso").lower()
    self.location = config.get("location", None)
    def_price = "spp" if self.iso == "ercot" else "lmp"
    self.price_field = config.get("pricefield", def_price)
    def_dataset = "{}_{}_day_ahead_hourly".format(self.iso, self.price_field)
    self.dataset = config.get("dataset", def_dataset)
    self.update_url()

  def remap(self, jslatest, jsforecast):
    data = {}
    
    ts = time.time()

    if jslatest:
      p = float(jslatest[0]["latest_lmp"])
    elif jsforecast:
      tsrec = None
      for jsrec in jsforecast:
        t1 = datetime.fromisoformat(jsrec["interval_start_utc"]).timestamp()
        t2 = datetime.fromisoformat(jsrec["interval_end_utc"]).timestamp()
        if ts >= t1 and  ts <= t2: 
          tsrec = jsrec
          break
      if tsrec:  
        p = float(tsrec[self.price_field])
      else:
        return None
    else:
      return None

    p *= EcoProvider.PRICE_UNITS.get(self.PRICE_UNIT, 1)    
    data[EcoProvider.FIELD_PRICE] = p   

    return data

  def update_url(self):
    self.api_url_latest = self.URL_LATEST.format(self.iso)
    if self.location:
      self.api_url_forecast = self.URL_FORECAST.format(self.dataset, self.location, "{}")
    else:
      self.api_url_forecast = None

  def fetch_json(self, url):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11")
    req.add_header("Accept", "application/json")
    if self.token:
      req.add_header("x-api-key", self.token)

    try:
      resp = urllib.request.urlopen(req).read()
      js = json.loads(resp)
      return js
    except:
      e = sys.exc_info()
      print ("Exception: ", e)
      return None

  def get_data(self):
    if self.api_url_forecast:
      data = self.remap(None, self.cached_data)
      if not data:
        tnow = datetime.utcnow().replace(minute=0, second=0).strftime(self.TIME_FORMAT)
        url = self.api_url_forecast.format(tnow)
        jsforecast = self.fetch_json(url)
        self.cached_data = jsforecast['data']
        data = self.remap(None, self.cached_data)
    else:      
      jslatest = self.fetch_json(self.api_url_latest)
      data = self.remap(jslatest['data'], None)
    return data 

class WattTimeProvider(EcoProvider):
  LABEL="watttime"
  URL_BASE = "https://api.watttime.org/"
  URL_LOGIN = URL_BASE + "login"
  URL_INDEX = URL_BASE + "v3/signal-index"
  URL_FORECAST = URL_BASE + "v3/forecast"
  LB_TO_KG = 0.45359237
  
  def __init__(self, config, glob_interval):
    EcoProvider.__init__(self, config, glob_interval)
    self.set_config(config)
    
  def get_config(self):
    cfg = super().get_config()
    if self.region:
      cfg["region"] = self.region
    return cfg

  def set_config(self, config):
    self.username = config.get("username", None)
    self.password = config.get("password", None)
    self.region = config.get("region", None)
    self.signal_type = config.get("signaltype", "co2_moer")
    self.use_index = getbool(config.get("useindex", True))
    self.use_forecast = getbool(config.get("useforecast", True))
    
    if not self.region:
      print ("ERROR: WattTime: region code is missing!")
      sys.exit(-1)
    
    self.update_url()

  def login(self):
    rsp = requests.get(self.URL_LOGIN, auth=HTTPBasicAuth(self.username, self.password))
    self.token = rsp.json()['token']

  def remap(self, jsdict, data={}):
    jsdata = jsdict["data"]
    jsmeta = jsdict["meta"]
    val = jsdata[0]["value"]
    if jsmeta["units"] == "percentile":
      data[EcoProvider.FIELD_INDEX] = val  
    elif jsmeta["units"] == "lbs_co2_per_mwh":  
      data[EcoProvider.FIELD_CO2] = float(val) * self.LB_TO_KG 
      
#    print(data)
    return data

  def update_url(self):
    self.api_url_index = self.URL_INDEX if self.use_index else None
    self.api_url_forecast = self.URL_FORECAST if self.use_forecast else None

  def get_data(self):
    self.login()
    headers = {'Authorization': 'Bearer {}'.format(self.token)}
    params = {'region': self.region, 'signal_type': self.signal_type}
    try:
      data = {}
      if self.api_url_index: 
        rsp = requests.get(self.api_url_index, headers=headers, params=params)
        js = rsp.json()
#        print(js)
        self.remap(js, data)
      if self.api_url_forecast: 
        params["horizon_hours"] = 0
        rsp = requests.get(self.api_url_forecast, headers=headers, params=params)
        js = rsp.json()
#        print(js)
        self.remap(js, data)
    except:
      e = sys.exc_info()
      print ("Exception: ", e)
      data = None
      
    return data

class TibberProvider(EcoProvider):
  LABEL="tibber"
  URL_BASE="https://api.tibber.com/v1-beta/gql"
  QUERY_PRICE='{ "query": "{viewer {homes {currentSubscription {priceInfo {%period% {total energy tax startsAt }}}}}}" }'
  FIELD_MAP = {EcoProvider.FIELD_PRICE: "total", EcoProvider.FIELD_TAX: "tax"}

  def __init__(self, config, glob_interval):
    EcoProvider.__init__(self, config, glob_interval)
    self.set_config(config)
    self.cached_data = None

  def get_config(self):
    cfg = super().get_config()
    cfg["token"] = self.token
    cfg["usecache"] = self.use_cache
    return cfg

  def set_config(self, config):
    self.token = config.get("token", None)
    self.use_cache = config.get("usecache", False)
    self.query_period = "today" if self.use_cache else "current"
    self.api_url = self.URL_BASE
    self.query = self.QUERY_PRICE.replace("%period%", self.query_period)
    
  def remap(self, jsdata):
    if not jsdata:
      return None
    data = {}
#    print(jsdata)
    jsprice = jsdata["viewer"]["homes"][0]["currentSubscription"]["priceInfo"][self.query_period] 
    ts = time.time()
#    print(ts)
    if self.use_cache:
      tsrec = None
      for jsrec in jsprice:
        t =  datetime.fromisoformat(jsrec["startsAt"]).timestamp()
        if ts >= t and  ts <= t + 3600: 
          tsrec = jsrec
          break
    else:
      tsrec = jsprice   
    if not tsrec:
      return None
#    print(tsrec)
    for k, v in self.FIELD_MAP.items():
      data[k] = tsrec[v]
#    print(data)
    return data

  def fetch_data(self):
    req = urllib.request.Request(self.api_url)
    req.add_header("User-Agent", "Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11")
    req.add_header("Content-Type", "application/json")
    if self.token:
      req.add_header("Authorization", self.token)

    try:
      resp = urllib.request.urlopen(req, data=self.query.encode("utf-8")).read()
      js = json.loads(resp)
#      print(js)
      self.cached_data = js['data']
    except:
      e = sys.exc_info()
      print ("Exception: ", e)
      data = None

  def get_data(self):
      if not self.use_cache:
        self.fetch_data()
      data = self.remap(self.cached_data)
      if not data:
        self.fetch_data()
        data = self.remap(self.cached_data)
      return data


class OctopusProvider(EcoProvider):
  LABEL="octopus"
  URL_BASE="https://api.octopus.energy"
  URL_PRODUCT=URL_BASE+"/v1/products/{}"
  URL_TARRIF=URL_PRODUCT+"/electricity-tariffs/{}"
  URL_PRICE=URL_TARRIF+"/standard-unit-rates"
  FIELD_MAP = {EcoProvider.FIELD_PRICE: "value_inc_vat"}

  def __init__(self, config, glob_interval):
    EcoProvider.__init__(self, config, glob_interval)
    self.set_config(config)
    self.cached_data = None

  def get_config(self):
    cfg = super().get_config()
    cfg["token"] = self.token
    cfg["product"] = self.product
    cfg["tariff"] = self.tariff
    cfg["usecache"] = self.use_cache
    return cfg

  def set_config(self, config):
    self.token = config.get("token", None)
    self.product = config.get("product", None)
    self.tariff = config.get("tariff", None)
    self.use_cache = config.get("usecache", True)
    self.update_url()
    
  def update_url(self):
    self.api_url = self.URL_PRICE.format(self.product, self.tariff)
    
  def remap(self, jsdata):
    if not jsdata:
      return None
    data = {}
#    print(jsdata)
    jsprice = jsdata["results"] 
    ts = datetime.utcnow()
#    print(ts)
    tsrec = None
    for jsrec in jsprice:
      ts_from = datetime.fromisoformat(jsrec["valid_from"].replace('Z', '' ))
      ts_to = datetime.fromisoformat(jsrec["valid_to"].replace('Z', '' ))
      if ts >= ts_from and  ts <= ts_to: 
        tsrec = jsrec
        break
    if not tsrec:
      return None
#    print(tsrec)
    for k, v in self.FIELD_MAP.items():
      data[k] = tsrec[v]
#    print(data)
    return data

  def fetch_data(self):
    req = urllib.request.Request(self.api_url)
    req.add_header("User-Agent", "Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11")
    req.add_header("Content-Type", "application/json")
    if self.token:
      base64string = base64.b64encode('%s:%s' % (self.token, ""))
      req.add_header("Authorization", "Basic %s" % base64string)  

    try:
      resp = urllib.request.urlopen(req).read()
      js = json.loads(resp)
#      print(js)
      self.cached_data = js
    except:
      e = sys.exc_info()
      print ("Exception: ", e)
      data = None

  def get_data(self):
      if not self.use_cache:
        self.fetch_data()
      data = self.remap(self.cached_data)
      if not data:
        self.fetch_data()
        data = self.remap(self.cached_data)
      return data

class AwattarProvider(EcoProvider):
  LABEL="awattar"
  URL_BASE = "https://api.awattar.{0}/v1/marketdata"
  FIELD_MAP = {EcoProvider.FIELD_PRICE: "marketprice"}
  
  def __init__(self, config, glob_interval):
    EcoProvider.__init__(self, config, glob_interval)
    self.set_config(config)
    self.cached_data = []
    
  def get_config(self):
    cfg = super().get_config()
    cfg["country"] = self.country
    return cfg

  def set_config(self, config):
    self.country = config["country"]
    self.token = config.get("token", None)
    self.fixed_price = float(config.get("fixedprice", 0.))
    self.vat = float(config.get("vat", 0.))
    self.update_url()

  def remap(self, jsdata):
    data = {}
    ts = time.time() * 1000
#    print(ts)
    tsrec = None
    for jsrec in jsdata:
      if ts >= float(jsrec["start_timestamp"]) and  ts <= float(jsrec["end_timestamp"]): 
        tsrec = jsrec
        break
    if not tsrec:
      return None
#    print(tsrec)
    for k, v in self.FIELD_MAP.items():
      data[k] = tsrec[v]
    unit = tsrec['unit'].lower()   
    data[EcoProvider.FIELD_PRICE] *= EcoProvider.PRICE_UNITS.get(unit, 1)  
    data[EcoProvider.FIELD_PRICE] *= (1.0 + self.vat)
    data[EcoProvider.FIELD_PRICE] += self.fixed_price
#    print(data)
    return data

  def update_url(self):
    if self.country.lower() in ["de", "at"]:
      self.api_url = self.URL_BASE.format(self.country.lower())
    else:
      raise ValueError("Country not supported: " + self.country)

  def fetch_data(self):
    req = urllib.request.Request(self.api_url)
    req.add_header("User-Agent", "Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11")
    if self.token:
      req.add_header("auth-token", self.token)

    try:
      resp = urllib.request.urlopen(req).read()
      js = json.loads(resp)
      self.cached_data = js['data']
    except:
      e = sys.exc_info()[0]
      print ("Exception: ", e)
      data = None

  def get_data(self):
      data = self.remap(self.cached_data)
      if not data:
        self.fetch_data()
        data = self.remap(self.cached_data)
      return data
