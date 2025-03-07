#!/usr/bin/env python3

import sys 
from datetime import datetime
import configparser
import argparse
import heapq
import traceback
import copy

import ecofreq.helpers as efh

from ecofreq import __version__
from .mqtt import *
from ecofreq.config import *
from ecofreq.utils import *
from ecofreq.ipc import EcoServer
from ecofreq.monitors.manager import MonitorManager
from ecofreq.providers.manager import EcoProviderManager, EcoProvider
from ecofreq.policy.manager import EcoPolicyManager
from ecofreq.policy.idle import IdlePolicy

class EcoFreqController(object):

  def __init__(self, ef):
    self.ef = ef
    
  def run_cmd(self, cmd, args={}):
    res = {}
    try:
      if hasattr(self, cmd):
        getattr(self, cmd)(res, args)
        res['status'] = 'OK'
      else:
        res['status'] = 'ERROR'
        res['error'] = 'Unknown command: ' + cmd
    except:
      res['status'] = 'ERROR'
      res['error'] = 'Exception: ' + sys.exc_info()
      
    return res 

  def info(self, res, args):
    res.update(self.ef.get_info())
    m_stats = self.ef.monitor.get_stats()
    if "LastState" in m_stats:
      res['idle_state'] = m_stats["LastState"]
      res['idle_load'] = m_stats["LastLoad"]
      res['idle_duration'] = m_stats["IdleDuration"]
    else:
      res['idle_state'] = "NA"
    res['avg_power'] = self.ef.monitor.get_last_avg_power()
    res['total_energy_j'] = self.ef.monitor.get_total_energy()
    res['total_co2'] = self.ef.total_co2
    res['total_cost'] = self.ef.total_cost
    res['last_co2kwh'] = self.ef.last_co2kwh
    res['last_price'] = self.ef.last_price

  def get_policy(self, res, args):
    res['co2policy'] = self.ef.co2policy.get_config()

  def set_policy(self, res, args):
    new_cfg = {}
    for domain in args["co2policy"].keys():
      dpol = domain + "_policy" 
      if dpol in self.ef.config:
        old_cfg = dict(self.ef.config[dpol])
      else:
        old_cfg = dict(self.ef.config["policy"])
#    print(old_cfg)
      new_cfg[domain] = copy.deepcopy(old_cfg)
      new_cfg[domain].update(args["co2policy"][domain])
      # all domains use the same metric for now
      new_cfg["metric"] = args["co2policy"][domain]["metric"]
#    print(new_cfg)
    self.ef.co2policy.set_config(new_cfg)
    if self.ef.last_co2_data:
      self.ef.co2policy.set_co2(self.ef.last_co2_data)
    self.ef.co2logger.print_cmd("set_policy")

  def get_provider(self, res, args):
    res['co2provider'] = self.ef.co2provider.get_config()

  def set_provider(self, res, args):
    old_cfg = self.ef.config 
#    print(args["co2provider"])
    new_cfg = copy.deepcopy(old_cfg)
    try:
      new_cfg.read_dict(args["co2provider"])
      self.ef.reset_co2provider(new_cfg)
    except:
      print(sys.exc_info())
  
class CO2History(object):
  def __init__(self, config):
    self.config = config
    self.h = []

  def add_co2(self, co2):
    heapq.heappush(self.h, co2)

  def min_co2(self, quantile = 5):
    n = int(0.01 * quantile * len(self.h)) + 1
    return heapq.nsmallest(n, self.h)[n-1]

  def max_co2(self, quantile = 5):
    n = int(0.01 * quantile * len(self.h)) + 1
    return heapq.nlargest(n, self.h)[n-1]

class MQTTLogger(object):
  def __init__(self, config, iface):
    self.iface = iface
    self.label = "mqtt_logger"
    cfg = config[self.label]
    self.mqtt_client = MQTTManager.add_client(self.label, cfg)
    
  def log(self):
    data = self.iface.run_cmd("info")
    self.mqtt_client.put_msg(data)

class EcoLogger(object):
  def __init__(self, config):
    self.log_fname = config["general"]["logfile"]
    if self.log_fname in OPTION_DISABLED:
      self.log_fname = None
    self.fmt = NAFormatter()
    self.idle_fields = False
    self.idle_debug = False
    self.cost_fields = config["general"].get("logcost", True)
    self.co2_extra = config["general"].get("logco2extra", False)
    
  def init_fields(self, monitors):
    if monitors.get_period_idle():
      self.idle_fields = True
#      self.idle_debug = True
    self.row_fmt = '{:<20}\t{:>10}\t{:>10}\t{:>10}\t{:>12.3f}\t{:>12.3f}\t{:>12.3f}\t{:>10.3f}\t{:>10.3f}'
    if self.idle_fields:
      self.row_fmt += "\t{:<7}"
    if self.idle_debug:
      self.row_fmt += "\t{:>10}\t{:>10.3f}"
    if self.co2_extra:
      self.row_fmt += "\t{:>10}\t{:>8.3f}\t{:>10}"
    if self.cost_fields:
      self.row_fmt += "\t{:>8.3f}\t{:>8.3f}"
          
    self.header_fmt = "#" + self.row_fmt.replace(".3f", "")

  def log(self, logstr):
    print (logstr)
    if self.log_fname:
      with open(self.log_fname, "a") as logf:
        logf.write(logstr + "\n")

  def print_header(self):
    headers = ["Timestamp", "gCO2/kWh", "Fmax [Mhz]", "Favg [Mhz]", "CPU_Pmax [W]", "GPU_Pmax [W]", "SYS_Pavg [W]", "Energy [J]", "CO2 [g]"] 
    if self.idle_fields:
      headers += ["State"] 
    if self.idle_debug:
      headers += ["MaxSessions", "MaxLoad"] 
    if self.co2_extra:
      headers += ["CI [g/kWh]", "Fossil [%]", "Index"]
    if self.cost_fields:
      headers += ["Price/kWh", "Cost"]
    self.log(self.fmt.format(self.header_fmt, *headers))

  def print_row(self, co2kwh, period_price, avg_freq, energy, avg_power, co2period, period_cost, idle, stats, co2_data):
    ts = datetime.now().strftime(TS_FORMAT)
    max_freq = cpu_max_power = gpu_max_power = None
    if efh.CpuFreqHelper.available():
      max_freq = round(efh.CpuFreqHelper.get_gov_max_freq(unit=efh.CpuFreqHelper.MHZ))
    if efh.LinuxPowercapHelper.available():
      cpu_max_power = efh.LinuxPowercapHelper.get_power_limit(efh.LinuxPowercapHelper.WATT)
    elif efh.AMDEsmiHelper.available():
      cpu_max_power = efh.AMDEsmiHelper.get_power_limit(efh.AMDEsmiHelper.WATT)
    if efh.NvidiaGPUHelper.available():
      gpu_max_power = efh.NvidiaGPUHelper.get_power_limit()
    cols = [ts, safe_round(co2kwh), max_freq, safe_round(avg_freq), cpu_max_power, gpu_max_power, avg_power, energy, co2period]
    if self.idle_fields:
      cols += [idle]
    if self.idle_debug:
      cols += [stats["MaxSessions"], stats["MaxLoad"]]
    if self.co2_extra:
      cols += [safe_round(co2_data.get(EcoProvider.FIELD_CO2)), co2_data.get(EcoProvider.FIELD_FOSSIL_PCT), co2_data.get(EcoProvider.FIELD_INDEX)]
    if self.cost_fields:
      cols += [period_price, period_cost]
      
    logstr = self.fmt.format(self.row_fmt, *cols)

#    logstr += "\t" + str(self.co2history.min_co2()) + "\t" + str(self.co2history.max_co2())

    self.log(logstr)

  def print_cmd(self, cmd):
    ts = datetime.now().strftime(TS_FORMAT)
    logstr = "##" + ts + "\t" + cmd.upper()
    self.log(logstr)

class EcoFreq(object):
  def __init__(self, config):
    self.config = config

    self.co2provider = EcoProviderManager(config)
    self.co2policy = EcoPolicyManager(config)
    self.co2history = CO2History(config)
    self.co2logger = EcoLogger(config)
    self.monitor = MonitorManager(config)
    self.co2logger.init_fields(self.monitor)
    self.debug = False
    self.idle_policy = IdlePolicy.from_config(config)
    if self.idle_policy:
      self.idle_policy.init_monitors(self.monitor)
      self.idle_policy.init_logger(self.co2logger)

    self.iface = EcoFreqController(self)
    self.server = EcoServer(self.iface, config)
    
    mqtt_log = config["general"].get("logmqtt", False)
    if mqtt_log:
      self.mqtt_logger = MQTTLogger(config, self.iface)
    else:
      self.mqtt_logger = None
    
    # make sure that CO2 sampling interval is a multiple of energy sampling interval
    self.sample_interval = self.monitor.adjust_interval(self.co2provider.interval)
    # print("sampling intervals co2/energy:", self.co2provider.interval, self.sample_interval)
    self.last_co2_data = self.co2provider.get_data()
    self.last_co2kwh = self.last_co2_data.get(EcoProvider.FIELD_CO2, None)
    self.last_price = self.last_co2_data.get(EcoProvider.FIELD_PRICE, None)
    #self.last_co2_data = self.last_co2kwh = self.last_price = None
    self.total_co2 = 0.
    self.total_cost = 0.
    self.start_date = datetime.now()
    self.co2provider_updated = False
    
  def get_info(self):
    return {"logfile": self.co2logger.log_fname,
            "co2provider": self.co2provider.info_string(),
            "co2policy": self.co2policy.info_string(),
            "idlepolicy":  self.idle_policy.info_string() if self.idle_policy else "None",
            "monitors": self.monitor.info_string(),
            "start_date": self.start_date.strftime(TS_FORMAT) }

  @classmethod
  def print_info(cls, info):
    print("Log file:    ", info["logfile"])
    print("CO2 Provider:", info["co2provider"])
    print("CO2 Policy:  ", info["co2policy"])
    print("Idle Policy: ", info["idlepolicy"])
    print("Monitors:    ", info["monitors"])

  def info(self):
    info = self.get_info()
    EcoFreq.print_info(info)
    
  def reset_co2provider(self, cfg):
    self.co2provider = EcoProviderManager(cfg)
    self.co2provider_updated = True
    self.co2logger.print_cmd("set_provider")
    
  def update_co2(self):
    # fetch new co2 intensity 
    co2_data = self.co2provider.get_data()
    co2 = co2_data.get(EcoProvider.FIELD_CO2, None)
    if co2:
      if self.last_co2kwh:
        self.period_co2kwh = 0.5 * (co2 + self.last_co2kwh)
      else:
        self.period_co2kwh = co2
    else:
      self.period_co2kwh = self.last_co2kwh
      self.last_co2kwh = co2

    price_kwh = co2_data.get(EcoProvider.FIELD_PRICE, None)
    if price_kwh:
      if self.last_price:
        self.period_price = self.last_price
      else:
        self.period_price = price_kwh
    else:
      self.period_price = self.last_price

    # prepare and print log row -> shows values for *past* interval!
    idle = self.monitor.get_period_idle()
    avg_freq = self.monitor.get_period_cpu_avg_freq(efh.CpuFreqHelper.MHZ)
    energy = self.monitor.get_period_energy()
    avg_power = self.monitor.get_period_avg_power()
    if self.period_co2kwh:
      period_co2 = energy * self.period_co2kwh / JOULES_IN_KWH
      self.total_co2 += period_co2
    else:
      period_co2 = None

    if self.period_price:
      period_cost = energy * self.period_price / JOULES_IN_KWH
      self.total_cost += period_cost
    else:
      period_cost = None
      
    stats = self.monitor.get_stats()
    
    self.co2logger.print_row(self.period_co2kwh, self.period_price, avg_freq, energy, avg_power, period_co2, period_cost, idle, stats, co2_data) 

    # apply policy for new co2 reading
    self.co2policy.set_co2(co2_data)

    if co2:
      self.co2history.add_co2(co2)

    self.last_co2_data = co2_data       
    self.last_co2kwh = co2
    self.last_price = price_kwh
    
  def write_shm(self):  
    ts = datetime.now().timestamp()
    energy_j = str(round(self.monitor.get_total_energy(), 3))
    co2_g = self.total_co2
    cost = self.total_cost
    period_energy = self.monitor.get_period_energy()
    if period_energy > 0.:
      if self.last_co2kwh:
        co2_g += period_energy * self.last_co2kwh / JOULES_IN_KWH
      if self.last_price:
        cost += period_energy * self.last_price / JOULES_IN_KWH
        
    ts = str(round(ts))
    co2_g = str(round(co2_g, 3))
    cost = str(round(cost, 3))
    with open(SHM_FILE, "w") as f:
      f.write(" ".join([ts, energy_j, co2_g, cost]))

  def write_mqtt(self):
    if self.mqtt_logger:
      self.mqtt_logger.log()

  async def spin(self):
    try:
      self.co2logger.print_header()
      self.co2logger.print_cmd("start")
      duration = 0
      self.monitor.reset_period() 
      elapsed = 0
      while 1:
        to_sleep = max(self.sample_interval - elapsed, 0)
        #print("to_sleep:", to_sleep)
#        time.sleep(to_sleep)
        await asyncio.sleep(to_sleep)
        duration += self.sample_interval
        t1 = datetime.now()
        self.monitor.update(duration)
        do_update_co2 = duration % self.co2provider.interval == 0 
        if self.co2provider_updated:
          do_update_co2 = True
          self.co2provider_updated = False
        if do_update_co2:
          self.update_co2()
          self.monitor.reset_period() 
        self.write_shm()  
        self.write_mqtt()
        if self.idle_policy:
          if self.idle_policy.check_idle():
            self.monitor.update(0)
            self.monitor.reset_period()
            self.co2logger.print_cmd("wakeup")
            t1 = datetime.now()
        elapsed = (datetime.now() - t1).total_seconds()
#        print("elapsed:", elapsed)
    except:
      e = sys.exc_info()
      print ("Exception: ", e)
      self.co2policy.reset()
      
  async def main(self):
    spins = [self.server.spin(), MQTTManager.run(), self.spin()]
    tasks = [asyncio.create_task(t) for t in spins]
    for t in tasks:
      await t

def parse_args():
  parser = argparse.ArgumentParser()
  parser.add_argument("-c", dest="cfg_file", default=None, help="Config file name.")
  parser.add_argument("-d", dest="diag", action="store_true", help="Show system info and exit.")
  parser.add_argument("-g", dest="governor", default=None, help="Power governor (off = no power scaling).")
  parser.add_argument("-l", dest="log_fname", default=None, help="Log file name.")
  parser.add_argument("-t", dest="co2token", default=None, help="CO2Signal token.")
  parser.add_argument("-i", dest="interval", default=None, help="Provider polling interval in seconds.")
  parser.add_argument("--user", dest="usermode", default=False, action="store_true", 
                      help="Run in rootless mode (limited functionality)")
  args = parser.parse_args()
  return args

def read_config(args):
  def_dict = {'general' :  { 'LogFile'     : LOG_FILE    },
              'provider' : { 'Interval'    : '600'     },
              'policy'   : { 'Control'     : 'auto',    
                             'Governor'    : 'linear', 
                             'CO2Range'    : 'auto'    },        
              'monitor'  : { 'PowerSensor' : 'auto',    
                             'Interval'    : '5'       }        
             }

  if args and args.cfg_file:
    cfg_file = args.cfg_file
  else:
    cfg_file = os.path.join(CONFIGDIR, "default.cfg")

  if not os.path.exists(cfg_file):
    # one of the built-in profiles?
    cfg_file = os.path.join(CONFIGDIR, f"{cfg_file}.cfg")
    if not os.path.exists(cfg_file):
      print("ERROR: Config file not found: ", cfg_file)
      sys.exit(-1)

  parser = configparser.ConfigParser(allow_no_value=True)
  parser.read_dict(def_dict)
  parser.read(cfg_file)
 
  if args:
    if args.co2token:
      parser["co2signal"]["token"] = args.co2token
    if args.log_fname:
      parser["general"]["LogFile"] = args.log_fname
    if args.governor:
      parser["policy"]["Governor"] = args.governor
    if args.interval:
      parser["provider"]["interval"] = args.interval

  return parser

def diag():
  print(f"EcoFreq v{__version__} (c) 2025 Oleksiy Kozlov\n")
  efh.CpuInfoHelper.info()
  print("")
  efh.LinuxPowercapHelper.info()
  print("")
  efh.AMDEsmiHelper.info()
  print("")
  efh.CpuFreqHelper.info()
  print("")
  efh.NvidiaGPUHelper.info()
  print("")
  efh.IPMIHelper.info()
  print("")
  efh.LinuxCgroupHelper.info()
  print("")
  efh.SuspendHelper.info()
  print("")
  
def main():
  args = parse_args()

  if os.getuid() != 0 and not args.usermode:
    print("\nTrying to obtain root permissions, please enter your password if requested...")
    from elevate import elevate
    elevate(graphical=False)

  try:
    diag()

    if not args.diag:
      cfg = read_config(args)
      ef = EcoFreq(cfg)
      ef.info()
      print("")
      asyncio.run(ef.main())
  except PermissionError:
    print(traceback.format_exc())
    print("\nPlease run EcoFreq with root permissions!\n")
  except SystemExit:
    pass
  except:
    print("Exception:", traceback.format_exc())
    
  if not args.diag and os.path.exists(SHM_FILE):
    os.remove(SHM_FILE)
    
if __name__ == '__main__':
  main()
