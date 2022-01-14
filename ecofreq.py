#!/usr/bin/env python3.7

import sys, json 
import urllib.request
from subprocess import call,check_output,STDOUT,DEVNULL,CalledProcessError
from datetime import datetime
import time
import os
import configparser
import argparse
import random
import heapq
import string
import traceback
import asyncio
import json
from math import ceil
from inspect import isclass

HOMEDIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = "/var/log/ecofreq.log"
SHM_FILE = "/dev/shm/ecofreq"
OPTION_DISABLED = ["none", "off"]

JOULES_IN_KWH = 3.6e6

def read_value(fname, field=0, sep=' '):
    with open(fname) as f:
      s = f.readline().rstrip("\n")
      if field == 0:
        return s
      else:
        return s.split(sep)[field]

def read_int_value(fname):
  return int(read_value(fname))

def write_value(fname, val):
    if os.path.isfile(fname):
      with open(fname, "w") as f:
        f.write(str(val))
      return True
    else:
      return False

def safe_round(val):
  return round(val) if (isinstance(val, float)) else val
    
class NAFormatter(string.Formatter):
    def __init__(self, missing='NA'):
        self.missing = missing

    def format_field(self, value, spec):
        if value == None: 
          value = self.missing
          spec = spec.replace("f", "s")
        return super(NAFormatter, self).format_field(value, spec)

class GeoHelper(object):
  API_URL = "http://ipinfo.io"    
  
  @classmethod
  def get_my_geoinfo(self):
    req = urllib.request.Request(self.API_URL)
#    req.add_header("User-Agent", "Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11")

    try:
      resp = urllib.request.urlopen(req).read()
      js = json.loads(resp)
      return js
    except:
      e = sys.exc_info()[0]
      print ("Exception: ", e)
      return None
      
  @classmethod
  def get_my_coords(self):
    try:
      js = self.get_my_geoinfo()
      lat, lon = js['loc'].split(",")
    except:
      e = sys.exc_info()[0]
      print ("Exception: ", e)
      lat, lon = None, None
    return lat, lon

class SuspendHelper(object):
  SYS_PWR="/sys/power/"
  SYS_PWR_STATE=SYS_PWR+"state"
  SYS_PWR_MEMSLEEP=SYS_PWR+"mem_sleep"
  S2MEM="mem"
  S2DISK="disk"
  S2IDLE="s2idle"
  S2RAM="deep"

  @classmethod
  def available(cls):
    return os.path.isdir(cls.SYS_PWR)

  @classmethod
  def supported_modes(cls):
    supported_modes = []
    if cls.available():
      supported_modes = read_value(cls.SYS_PWR_STATE).split(" ")
      if cls.S2MEM in supported_modes:
        supported_modes += read_value(cls.SYS_PWR_MEMSLEEP).split(" ")
    return supported_modes

  @classmethod
  def info(cls):
    print("Suspend-to-RAM available: ", end ="")
    def_s2ram = "[" + cls.S2RAM + "]" 
    if def_s2ram in cls.supported_modes():
      print("YES")
    else:
      print("NO")
    print("Suspend modes supported:", " ".join(cls.supported_modes()))

  @classmethod
  def suspend(cls, mode=S2RAM):
    if mode == cls.S2RAM:
      write_value(cls.SYS_PWR_MEMSLEEP, mode)
      mode = cls.S2MEM
    write_value(cls.SYS_PWR_STATE, mode)

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
    res['total_co2'] = self.ef.total_co2
    res['co2policy'] = self.ef.co2policy.info_string()

  def get_policy(self, res, args):
    res['co2policy'] = self.ef.co2policy.get_config()

  def set_policy(self, res, args):
    self.ef.co2policy.set_config(args["co2policy"])
    self.ef.co2logger.print_cmd("set_policy")

class EcoServer(object):
  IPC_PATH="/tmp/ecofreq-ipc"

  def __init__(self, iface, config=None):
    self.iface = iface
  
  async def spin(self):
    self.serv = await asyncio.start_unix_server(self.on_connect, path=self.IPC_PATH)
    os.chmod(self.IPC_PATH, 0o666)
#    print(f"Server init")    
#    async with self.serv:
    await self.serv.serve_forever()    
    
  async def on_connect(self, reader, writer):
    data = await reader.read(1024)
    msg = data.decode()
    # addr = writer.get_extra_info('peername')
    
    # print(f"Received {msg!r}")    

    try:
      req = json.loads(msg)
      cmd = req['cmd']
      args = req['args'] if 'args' in req else {}
      res = self.iface.run_cmd(cmd, args)
      response = json.dumps(res)
    except:
      response = "Invalid message"  
    
    writer.write(response.encode())
    await writer.drain()
    writer.close()

class EcoClient(object):
    
  async def unix_send(self, message):
      reader, writer = await asyncio.open_unix_connection(EcoServer.IPC_PATH)
  
#     print(f'Send: {message!r}')
      writer.write(message.encode())
      await writer.drain()
  
      data = await reader.read(1024)
      # print(f'Received: {data.decode()!r}')
  
      writer.close()
      
      return data.decode()

  def send_cmd(self, cmd, args=None):
    obj = dict(cmd=cmd, args=args)
    msg = json.dumps(obj)
    resp = asyncio.run(self.unix_send(msg))
    try:
      return json.loads(resp)
    except:
      return dict(status='ERROR', error='Exception')
  
  def info(self):
    return self.send_cmd('info')

  def get_policy(self):
    return self.send_cmd('get_policy')

  def set_policy(self, policy):
    return self.send_cmd('set_policy', policy)
  
class NvidiaGPUHelper(object):
  CMD_NVSMI = "nvidia-smi"

  @classmethod
  def available(cls):
#    return call(cls.CMD_NVSMI, shell=True, stdout=DEVNULL, stderr=DEVNULL) == 0
     try:
       out = cls.query_gpus(fields = "power.draw,power.management")
#       print (out)
       return "Enabled" in out[0][1]
     except CalledProcessError:
       return False

  @classmethod
  def query_gpus(cls, fields, fmt = "csv,noheader,nounits"):
    cmdline = cls.CMD_NVSMI + " --format=" + fmt +  " --query-gpu=" + fields 
    out = check_output(cmdline, shell=True, stderr=DEVNULL, universal_newlines=True)
    result = []
    for line in out.split("\n"):
      if line:
        result.append([x.strip() for x in line.split(",")])
    return result  

  @classmethod
  def get_power(cls):
    pwr = [ float(x[0]) for x in cls.query_gpus(fields = "power.draw") ]
    return sum(pwr)

  @classmethod
  def get_power_limit(cls):
    pwr = [ float(x[0]) for x in cls.query_gpus(fields = "power.limit") ]
    return sum(pwr)

  @classmethod
  def get_power_limit_all(cls):
   return cls.query_gpus(fields = "power.min_limit,power.max_limit,power.limit")

  @classmethod
  def set_power_limit(cls, max_gpu_power):
    cmdline = cls.CMD_NVSMI + " -pl " + str(max_gpu_power)
    out = check_output(cmdline, shell=True, stderr=DEVNULL, universal_newlines=True)

  @classmethod
  def info(cls):
    if cls.available():
      field_list = "name,power.min_limit,power.max_limit,power.limit"
      cnt = 0
      for gi in cls.query_gpus(fields = field_list, fmt="csv,noheader"):
        print ("GPU" + str(cnt) + ": " + gi[0] + ", min_hw_limit = " + gi[1] + ", max_hw_limit = " + gi[2] + ", current_limit = " + gi[3])
        cnt += 1

class CpuInfoHelper(object):
  CMD_LSCPU = "lscpu"
  CPU_TDP_FILE = os.path.join(HOMEDIR, "cpu_tdp.csv")
  
  @classmethod
  def available(cls):
    return call(cls.CMD_LSCPU, shell=True, stderr=DEVNULL) == 0

  @classmethod
  def parse_lscpu(cls):
    try:
      out = check_output(cls.CMD_LSCPU, shell=True, stderr=DEVNULL, universal_newlines=True)
      cpuinfo = {}
      for line in out.split("\n"):
        tok = line.split(":")
        if len(tok) > 1:
          cpuinfo[tok[0]] = tok[1].strip()
      return cpuinfo
    except CalledProcessError:
      return None  
    
  @classmethod
  def get_tdp_uw(cls):
    cpuinfo = cls.parse_lscpu()
    mymodel = cpuinfo["Model name"]
    mymodel = mymodel.split(" with ")[0]
    mycpu_toks = []
    for w in mymodel.split(" "):
      if w.lower().endswith("-core"):
        break
      if w.lower() in ["processor"]:
        continue
      mycpu_toks.append(w)
    mycpu = " ".join(mycpu_toks)  
      
    with open(cls.CPU_TDP_FILE) as f:
      for line in f:
        model, tdp = line.rstrip('\n').split(",")
        if model == mycpu:
          return float(tdp.rstrip("W")) * 1e6
        
    return None    

  @classmethod
  def info(cls):
    cpuinfo = cls.parse_lscpu()
    if cpuinfo:
      model = cpuinfo["Model name"]
      sockets = int(cpuinfo["Socket(s)"])
      threads = int(cpuinfo["CPU(s)"])
      cores = int(threads / int(cpuinfo["Thread(s) per core"]))
      print("CPU model:                ", model) 
      print("CPU sockets/cores/threads:", sockets, "/", cores, "/", threads) 
    else:
      print("CPU info not available")
  
class CpuFreqHelper(object):
  SYSFS_CPU_PATH = "/sys/devices/system/cpu/cpu{0}/cpufreq/{1}"
  KHZ, MHZ, GHZ = 1, 1e3, 1e6

  @classmethod
  def cpu_field_fname(cls, cpu, field):
    return cls.SYSFS_CPU_PATH.format(cpu, field)

  @classmethod
  def available(cls):
    return os.path.isfile(cls.cpu_field_fname(0, "scaling_driver"))
  
  @classmethod
  def info(cls):
    if cls.available():
      print ("DVFS settings:  driver = " + cls.get_driver() + ", governor = " + cls.get_governor())
      hw_fmin = round(cls.get_hw_min_freq(0, cls.MHZ))
      hw_fmax = round(cls.get_hw_max_freq(0, cls.MHZ))
      gov_fmin = round(cls.get_gov_min_freq(0, cls.MHZ))
      gov_fmax = round(cls.get_gov_max_freq(0, cls.MHZ))
      print ("DVFS HW limits: " + str(hw_fmin) + " - " + str(hw_fmax) + " MHz")
      print ("DVFS policy:    " + str(gov_fmin) + " - " + str(gov_fmax) + " MHz")
    else:
        print("DVFS driver not found.")

  @classmethod
  def get_string(cls, name, cpu=0):
    try:
      return read_value(cls.cpu_field_fname(cpu, name))
    except:
      return None 

  @classmethod
  def get_int(cls, name, cpu=0):
    s = cls.get_string(name, cpu)
    return None if s is None else int(s)

  @classmethod
  def get_int_scaled(cls, name, cpu=0, unit=KHZ):
    s = cls.get_string(name, cpu)
    if s:
      return int(s) / unit
    else:
      return None

  @classmethod
  def get_driver(cls):
    return cls.get_string("scaling_driver").strip()

  @classmethod
  def get_governor(cls):
    return cls.get_string("scaling_governor").strip()

  @classmethod
  def get_hw_min_freq(cls, cpu=0, unit=KHZ):
    return cls.get_int_scaled("cpuinfo_min_freq", cpu, unit)

  @classmethod
  def get_hw_max_freq(cls, cpu=0, unit=KHZ):
    return cls.get_int_scaled("cpuinfo_max_freq", cpu, unit)

  @classmethod
  def get_hw_cur_freq(cls, cpu=0, unit=KHZ):
    return cls.get_int_scaled("cpuinfo_cur_freq", cpu, unit)
  
  @classmethod
  def get_gov_min_freq(cls, cpu=0, unit=KHZ):
    return cls.get_int_scaled("scaling_min_freq", cpu, unit)

  @classmethod
  def get_gov_max_freq(cls, cpu=0, unit=KHZ):
    return cls.get_int_scaled("scaling_max_freq", cpu, unit)

  @classmethod
  def get_gov_cur_freq(cls, cpu=0, unit=KHZ):
    return cls.get_int_scaled("scaling_cur_freq", cpu, unit)

  @classmethod
  def get_avg_gov_cur_freq(cls, unit=KHZ):  
    cpu = 0
    fsum = 0
    while True:
      fcpu = cls.get_gov_cur_freq(cpu, unit)
      if fcpu:
        fsum += fcpu
        cpu += 1
      else:
        break
    return fsum / cpu

  @classmethod
  def set_cpu_field_value(cls, cpu, field, value):  
    return write_value(cls.cpu_field_fname(cpu, field), value)
    
  @classmethod
  def set_field_value(cls, field, value):  
    cpu = 0
    while cls.set_cpu_field_value(cpu, field, value):
      cpu += 1

  @classmethod
  def set_gov_max_freq(cls, freq):
    cls.set_field_value("scaling_max_freq", freq)

class CpuPowerHelper(object):
  @classmethod
  def set_max_freq(cls, freq):
    call("cpupower frequency-set -u " + str(freq) + " > /dev/null", shell=True)

class LinuxPowercapHelper(object):
  INTEL_RAPL_PATH="/sys/class/powercap/intel-rapl:"
  PKG_MAX=256
  UWATT, MWATT, WATT = 1, 1e3, 1e6

  @classmethod
  def package_path(cls, pkg):
    return cls.INTEL_RAPL_PATH + str(pkg)

  @classmethod
  def package_file(cls, pkg, fname):
    return os.path.join(cls.package_path(pkg), fname)

  @classmethod
  def read_package_int(cls, pkg, fname):
    return read_int_value(cls.package_file(pkg, fname))

  @classmethod
  def package_list(cls, domain="package-"):
    l = []
    pkg = 0
    while pkg < cls.PKG_MAX:
      fname = cls.package_file(pkg, "name")
      if not os.path.isfile(fname):
        break;
      pkg_name = read_value(fname)  
      if pkg_name.startswith(domain):
        l += [str(pkg)]
      if domain in ["dram", "core", "uncore"]:
        subpkg = 0
        while subpkg < cls.PKG_MAX:
          subpkg_code = str(pkg) + ":" + str(subpkg) 
          fname = cls.package_file(subpkg_code, "name")
          if not os.path.isfile(fname):
            break;
          pkg_name = read_value(fname)  
          if pkg_name.startswith(domain):
            l += [subpkg_code]
          subpkg += 1
      pkg += 1
    return l

  @classmethod
  def available(cls, readonly=False):
    if readonly:  
      return os.path.isfile(cls.package_file(0, "energy_uj"))
    else:
      return os.path.isfile(cls.package_file(0, "constraint_0_power_limit_uw"))

  @classmethod
  def enabled(cls, pkg=0):
    return cls.read_package_int(pkg, "enabled") != 0 

  @classmethod
  def info(cls):
    if cls.available(True):
        outfmt = "RAPL {0} domains: count = {1}, hw_limit = {2} W, current_limit = {3} W" 
        cpus = cls.package_list()
        if len(cpus):
          maxp = cls.get_package_hw_max_power(cpus[0], cls.WATT)
          curp = cls.get_package_power_limit(cpus[0], cls.WATT)
          print(outfmt.format("CPU ", len(cpus), maxp, curp))
        dram = cls.package_list("dram")
        if len(dram):
          try:
            maxp = cls.get_package_hw_max_power(dram[0], cls.WATT)
          except OSError:
            maxp = None
          curp = cls.get_package_power_limit(dram[0], cls.WATT)
          print(outfmt.format("DRAM", len(dram), maxp, curp))
        psys = cls.package_list("psys")
        if len(psys):
          try:
            maxp = cls.get_package_hw_max_power(psys[0], cls.WATT)
          except OSError:
            maxp = None
          curp = cls.get_package_power_limit(psys[0], cls.WATT)
          print(outfmt.format("PSYS", len(psys), maxp, curp))
    else:
        print("RAPL powercap not found.")

  @classmethod
  def get_package_hw_max_power(cls, pkg, unit=UWATT):
    if cls.available():
      return cls.read_package_int(pkg, "constraint_0_max_power_uw") / unit 
    else:
      return None

  @classmethod
  def get_package_power_limit(cls, pkg, unit=UWATT):
    if cls.available():
      return cls.read_package_int(pkg, "constraint_0_power_limit_uw") / unit 
    else:
      return None

  @classmethod
  def get_package_energy(cls, pkg):
    return cls.read_package_int(pkg, "energy_uj") 

  @classmethod
  def get_package_energy_range(cls, pkg):
    return cls.read_package_int(pkg, "max_energy_range_uj") 

  @classmethod
  def get_power_limit(cls, unit=UWATT):
    power = 0
    for pkg in cls.package_list(): 
      power += cls.get_package_power_limit(pkg, unit)
    return power

  @classmethod
  def set_package_power_limit(cls, pkg, power, unit=UWATT):
    val = round(power * unit)
    write_value(cls.package_file(pkg, "constraint_0_power_limit_uw"), val)

  @classmethod
  def reset_package_power_limit(cls, pkg):
    # write_value(cls.package_file(pkg, "constraint_0_power_limit_uw"), round(cls.get_package_hw_max_power(pkg)))
    cls.set_package_power_limit(pkg, cls.get_package_hw_max_power(pkg))

  @classmethod
  def set_power_limit(cls, power, unit=UWATT):
    for pkg in cls.package_list(): 
      cls.set_package_power_limit(pkg, power, unit)

# Code adapted from s-tui: 
# https://github.com/amanusk/s-tui/commit/5c87727f5a2364697bfce84a0b688c1a6d2b3250
class AMDRaplMsrHelper(object):
  MSR_CPU_PATH="/dev/cpu/{0}/msr"
  TOPOL_CPU_PATH="/sys/devices/system/cpu/cpu{0}/topology/physical_package_id"
  CPU_MAX = 4096
  UNIT_MSR = 0xC0010299
  CORE_MSR = 0xC001029A
  PACKAGE_MSR = 0xC001029B
  ENERGY_UNIT_MASK = 0x1F00
  ENERGY_STATUS_MASK = 0xffffffff
  UJOULE_IN_JOULE = 1e6

  @staticmethod
  def read_msr(filename, register):
    with open(filename, "rb") as f:
      f.seek(register)
      res = int.from_bytes(f.read(8), sys.byteorder)
    return res

  @classmethod
  def package_list(cls):
    pkg_list = set()
    for cpu in range(cls.CPU_MAX):
      fname = cls.TOPOL_CPU_PATH.format(cpu)
      if not os.path.isfile(fname):
        break
      pkg = read_int_value(fname)
      pkg_list.add(pkg)
    return list(pkg_list)

  @classmethod
  def pkg_to_cpu(cls, pkg):
    for cpu in range(cls.CPU_MAX):
      fname = cls.TOPOL_CPU_PATH.format(cpu)
      if not os.path.isfile(fname):
        break;
      if read_int_value(fname) == cpu:
        return cpu
    return None

  @classmethod
  def cpu_msr_file(cls, cpu):
    return cls.MSR_CPU_PATH.format(cpu)

  @classmethod
  def pkg_msr_file(cls, pkg):
    cpu = cls.pkg_to_cpu(pkg)
    return cls.cpu_msr_file(cpu)
  
  @classmethod
  def get_energy_factor(cls, filename):
    unit_msr = cls.read_msr(filename, cls.UNIT_MSR)
    energy_factor = 0.5 ** ((unit_msr & cls.ENERGY_UNIT_MASK) >> 8)
    return energy_factor * cls.UJOULE_IN_JOULE

  @classmethod
  def get_energy_range(cls, filename):
    return cls.ENERGY_STATUS_MASK * cls.get_energy_factor(filename)

  @classmethod
  def get_energy(cls, filename, register):
    energy_factor = cls.get_energy_factor(filename)
    package_msr = cls.read_msr(filename, register)
    energy = package_msr * energy_factor
    # print ("amd pkg_energy: ", energy)
    return energy

  @classmethod
  def get_package_energy(cls, pkg):
    filename = cls.pkg_msr_file(pkg)
    return cls.get_energy(filename, cls.PACKAGE_MSR)

  @classmethod
  def get_core_energy(cls, cpu):
    filename = cls.cpu_msr_file(cpu)
    return cls.get_energy(filename, cls.CORE_MSR)

  @classmethod
  def get_package_energy_range(cls, pkg):
    filename = cls.pkg_msr_file(pkg)
    return cls.get_energy_range(filename)

  @classmethod
  def get_core_energy_range(cls, cpu):
    filename = cls.cpu_msr_file(cpu)
    return cls.get_energy_range(filename)

class IPMIHelper(object):
  @classmethod
  def available(cls):
    return cls.get_power() is not None

  @classmethod
  def info(cls):
    print("IPMI available: ", end ="")
    if cls.available():
      print("YES")
    else:
      print("NO")
      
  @classmethod
  def get_power(cls):
    try:
      out = check_output("ipmitool dcmi power reading", shell=True, stderr=DEVNULL, universal_newlines=True)
      for line in out.split("\n"):
        tok = [x.strip() for x in line.split(":")]
        if tok[0] == "Instantaneous power reading":
          pwr = tok[1].split()[0]
          return float(pwr)
      return None
    except CalledProcessError:
      return None

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

class Monitor(object):
  def __init__(self, config):
    self.interval = int(config["monitor"]["interval"])
    self.period_samples = 0
    self.total_samples = 0
    
  def reset_period(self):
    self.period_samples = 0

  # subclasses must override this to call actual update routine
  def update_impl(self):
    pass
  
  def update(self):
    self.update_impl() 
    self.period_samples += 1
    self.total_samples += 1
    
  # subclasses must override this
  def get_stats(self):
    return {}

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
    self.reset_period()

  def active_sessions(self):
    out = check_output(self.CMD_SESSION_COUNT, shell=True, stderr=DEVNULL, universal_newlines=True)
    return int(out)    

  def active_load(self):
    return float(read_value(self.LOADAVG_FILE, self.load_period))

  def update_impl(self):
    self.max_sessions = max(self.max_sessions, self.active_sessions())
    self.max_load = max(self.max_load, self.active_load())
    if self.get_period_idle() == "IDLE":
      self.idle_duration += self.interval
    else:
      self.idle_duration = 0
    
  def get_period_idle(self):
    if self.max_sessions > 0 and self.max_load > self.load_cutoff:
      return "ACTIVE"
    elif self.max_sessions > 0:
      return "SESSION"
    elif self.max_load > self.load_cutoff:
      return "LOAD"
    else:
      return "IDLE"
    
  def get_stats(self):
    return {"State": self.get_period_idle(),
            "MaxSessions": self.max_sessions,
            "MaxLoad1": self.max_load }

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
     
class EnergyMonitor(Monitor):
  def __init__(self, config):
    Monitor.__init__(self, config)
    self.total_energy = 0
    self.period_energy = 0
    self.monitor_freq = CpuFreqHelper.available()

  @classmethod
  def from_config(cls, config):
    sens_dict = {"rapl" : PowercapEnergyMonitor, "amd_msr" : AMDMsrEnergyMonitor, "ipmi" : IPMIEnergyMonitor, "gpu" : GPUEnergyMonitor }
    p = config["monitor"].get("PowerSensor", "auto").lower()
    monitors = []
    if p in OPTION_DISABLED:
      pass
    elif p == "auto":
      if IPMIEnergyMonitor.available():
        monitors.append(IPMIEnergyMonitor(config))
      else:
        if PowercapEnergyMonitor.available():
          monitors.append(PowercapEnergyMonitor(config))
        elif AMDMsrEnergyMonitor.available():
          monitors.append(AMDMsrEnergyMonitor(config))
        if NvidiaGPUHelper.available():
          monitors.append(GPUEnergyMonitor(config))
    else:
      for s in p.split(","):
        if s in sens_dict:
          monitors.append(sens_dict[s](config))  
        else:
          raise ValueError("Unknown power sensor: " + p)
    return monitors

  def update_energy(self):
     energy = self.sample_energy()
#     print("energy diff:", energy)
     self.total_energy += energy
     self.period_energy += energy

  def update_impl(self):
    self.update_energy()
 
  def get_period_energy(self):
    return self.period_energy

  def get_total_energy(self):
    return self.total_energy

  def get_period_avg_power(self):
    if self.period_samples:
      return self.period_energy / (self.period_samples * self.interval)
    else:
      return 0

  def get_total_avg_power(self):
    if self.total_samples:
      return self.total_energy / (self.total_samples * self.interval)
    else:
      return 0
    
  def reset_period(self):
    Monitor.reset_period(self)
    self.period_energy = 0

class NoEnergyMonitor(EnergyMonitor):
  def update_energy(self):
    pass
  
class RAPLEnergyMonitor(EnergyMonitor):
  UJOULE, JOULE, WH = 1, 1e6, 3600*1e6
  
  def __init__(self, config):
    EnergyMonitor.__init__(self, config)
    c = config['powercap'] if 'powercap' in config else {}
    self.estimate_full_power = c.get('EstimateFullPower', True)
    self.syspower_coeff_const = c.get('FullPowerConstCoeff', 0.3)
    self.syspower_coeff_var = c.get('FullPowerVarCoeff', 0.25)
    self.psys_domain = False
    self.init_pkg_list()
    self.init_energy()

  def init_energy(self):
    self.last_energy = {}
    self.energy_range = {}
    for p in self.pkg_list:
      self.last_energy[p] = 0
      self.energy_range[p] = self.get_package_energy_range(p)
    self.sample_energy()
    
  def full_system_energy(self, energy_diff):
    if self.psys_domain or not self.estimate_full_power:
      return energy_diff
    else:
      sysenergy_const = self.cpu_max_power_uw * self.syspower_coeff_const * self.interval
      sysenegy_var = (1. + self.syspower_coeff_var) * energy_diff
      return sysenergy_const + sysenegy_var 

  def sample_energy(self):
    energy_diff = 0
    for p in self.pkg_list:
      new_energy = self.get_package_energy(p)
      if new_energy >= self.last_energy[p]:
        diff_uj = new_energy - self.last_energy[p]
      else:
        diff_uj = new_energy + (self.energy_range[p] - self.last_energy[p]);
      self.last_energy[p] = new_energy
      energy_diff += diff_uj
    energy_diff = self.full_system_energy(energy_diff)
    energy_diff_j = energy_diff / self.JOULE  
    return energy_diff_j
  
class PowercapEnergyMonitor(RAPLEnergyMonitor):

  @classmethod
  def available(cls):
    try:
      energy = LinuxPowercapHelper.get_package_energy(0)
      return energy > 0
    except OSError:
      return False
     
  def __init__(self, config):
    RAPLEnergyMonitor.__init__(self, config)

  def init_pkg_list(self):
    self.pkg_list = LinuxPowercapHelper.package_list("psys")
    if self.pkg_list:
      self.psys_domain = True
    else:
      self.psys_domain = False
      self.pkg_list = LinuxPowercapHelper.package_list("package-")
      if self.pkg_list:
        if LinuxPowercapHelper.available():
          self.cpu_max_power_uw = LinuxPowercapHelper.get_package_hw_max_power(self.pkg_list[0])
        else:
          self.cpu_max_power_uw = CpuInfoHelper.get_tdp_uw()
      self.pkg_list += LinuxPowercapHelper.package_list("dram")
  
  def get_package_energy(self, pkg):
    return LinuxPowercapHelper.get_package_energy(pkg)

  def get_package_energy_range(self, pkg):
    return LinuxPowercapHelper.get_package_energy_range(pkg)

class AMDMsrEnergyMonitor(RAPLEnergyMonitor):

  @classmethod
  def available(cls):
    try:
      energy = AMDRaplMsrHelper.get_package_energy(0)
      return energy > 0
    except OSError:
      return False

  def __init__(self, config):
    RAPLEnergyMonitor.__init__(self, config)
    
  def init_pkg_list(self):
    self.pkg_list = AMDRaplMsrHelper.package_list()
    self.cpu_max_power_uw = CpuInfoHelper.get_tdp_uw()

  def get_package_energy(self, pkg):
    return AMDRaplMsrHelper.get_package_energy(pkg)

  def get_package_energy_range(self, pkg):
    return AMDRaplMsrHelper.get_package_energy_range(pkg)


class GPUEnergyMonitor(EnergyMonitor):
  def __init__(self, config):
    EnergyMonitor.__init__(self, config)
    self.last_pwr = 0

  @classmethod
  def available(cls):
    return NvidiaGPUHelper.available()

  def sample_energy(self):
    cur_pwr = NvidiaGPUHelper.get_power()
    if not cur_pwr:
      print ("WARNING: GPU power reading failed!")
      cur_pwr = self.last_pwr
    avg_pwr = 0.5 * (self.last_pwr + cur_pwr)
    energy_diff = avg_pwr * self.interval
    self.last_pwr = cur_pwr
    return energy_diff

class IPMIEnergyMonitor(EnergyMonitor):
  def __init__(self, config):
    EnergyMonitor.__init__(self, config)
    self.last_pwr = 0

  @classmethod
  def available(cls):
    return IPMIHelper.available()

  def sample_energy(self):
    cur_pwr = IPMIHelper.get_power()
    if not cur_pwr:
      print ("WARNING: IPMI power reading failed!")
      cur_pwr = self.last_pwr
    avg_pwr = 0.5 * (self.last_pwr + cur_pwr)
    energy_diff = avg_pwr * self.interval
    self.last_pwr = cur_pwr
    return energy_diff

class EmissionProvider(object):
  def __init__(self, config):
    self.interval = int(config["emission"]["interval"])

  @classmethod
  def from_config(cls, config):
    prov_dict = {"co2signal" : CO2Signal, "mock" : MockCO2Provider }
    p = config["emission"].get("Provider", "co2signal")
    if p in prov_dict:
      return prov_dict[p](config)  
    else:
      raise ValueError("Unknown emission provider: " + p)

class CO2Signal(object):
  URL_BASE = "https://api.co2signal.com/v1/latest?"
  URL_COUNTRY = URL_BASE + "countryCode={0}"
  URL_COORD = URL_BASE + "lat={0}&lon={1}"
  
  def __init__(self, config):
    EmissionProvider.__init__(self, config)
    self.co2country = config["co2signal"]["country"]
    self.co2token = config["co2signal"]["token"]

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

  def update_url(self):
    if not self.co2country.lower().startswith("auto"):
      self.api_url = self.URL_COUNTRY.format(self.co2country)
    else:
      self.api_url = self.URL_COORD.format(self.coord_lat, self.coord_lon)

  def get_co2(self):
    req = urllib.request.Request(self.api_url)
    req.add_header("User-Agent", "Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11")
    req.add_header("auth-token", self.co2token)

    try:
      resp = urllib.request.urlopen(req).read()
      js = json.loads(resp)
      co2 = float(js['data']['carbonIntensity'])
    except:
      e = sys.exc_info()[0]
      print ("Exception: ", e)
      co2 = None
    return co2

class MockCO2Provider(object):
  def __init__(self, config):
    EmissionProvider.__init__(self, config)
    if 'mock' in config:
      r = config['mock'].get('CO2Range', '100-800')
    self.co2min, self.co2max = [int(x) for x in r.split("-")]

  def get_co2(self):
    co2 = random.randint(self.co2min, self.co2max)
    # if co2 % 2 == 0:
    #   co2 = None
    return co2

class Governor(object):
  def __init__(self, config, vmin, vmax):
    r = config["co2range"].lower()
    if r == "auto":
      self.co2min = self.co2max = -1
    else:
      self.co2min, self.co2max = [int(x) for x in r.split("-")]
    self.val_round = 3

  def get_config(self, config={}):
    config["co2range"] = "{0}-{1}".format(self.co2min, self.co2max)
    return config

  @classmethod
  def from_config(cls, config, vmin, vmax):
    t = config["governor"].lower()

    if t == "linear" or t == "lineargovernor":
      return LinearGovernor(config, vmin, vmax)
    elif t == "maxperf":
      return ConstantGovernor(config, vmax)
    elif t in OPTION_DISABLED:
      return None
    else:
      raise ValueError("Unknown governor: " + t)

class ConstantGovernor(Governor):
  def __init__(self, config, val):
    Governor.__init__(self, config, val, val)
    self.val = val

  def co2val(self, co2):
    return self.val
  
class LinearGovernor(Governor):
  def __init__(self, config, vmin, vmax):
    Governor.__init__(self, config, vmin, vmax)
    self.vmin = vmin
    self.vmax = vmax

  def co2val(self, co2):
    if co2 >= self.co2max:
      k = 0.0
    elif co2 <= self.co2min:
      k = 1.0
    else:
      k = 1.0 - float(co2 - self.co2min) / (self.co2max - self.co2min)
    val = self.vmin + (self.vmax - self.vmin) * k
    val = int(round(val, self.val_round))
    return val

class EcoPolicy(object):
  def __init__(self, config):
    self.debug = False

  def info_string(self):
    g = type(self.governor).__name__ if self.governor else "None" 
    return type(self).__name__ + "(" + g + ")" 

  def init_governor(self, config, vmin, vmax, vround=None):
    self.governor = Governor.from_config(config, vmin, vmax)
    if self.governor and vround:
      self.governor.val_round = vround
      
  def get_config(self, config={}):
    config["control"] = type(self).__name__
    config["governor"] = type(self.governor).__name__ if self.governor else "none"
    if self.governor:
      self.governor.get_config(config)
    return config
  
  def co2val(self, co2):
    if self.governor:
      return self.governor.co2val(co2)
    else:
      return None

class CPUEcoPolicy(EcoPolicy):
  def __init__(self, config):
    EcoPolicy.__init__(self, config)

  @classmethod
  def from_config(cls, config):
    if not config:
      return None

    # first, check if we have a specific EcoPolicy class
    c = config["control"]
    if c in globals(): 
      cls = globals()[c]
      if isclass(cls) and issubclass(cls, CPUEcoPolicy):
        return cls(config)
    
    # otherwise, look for a generic policy type
    c = c.lower()
    if c == "auto":
      if LinuxPowercapHelper.available() and LinuxPowercapHelper.enabled():
        c = "power"
      elif CpuFreqHelper.available():
        c = "frequency"
      else:
        print ("ERROR: Power management interface not found!")
        sys.exit(-1)

    if c == "power":
      return CPUPowerEcoPolicy(config)
    elif c == "frequency":
      return CPUFreqEcoPolicy(config)
    elif c in OPTION_DISABLED or t in OPTION_DISABLED:
      return None
    else:
      raise ValueError("Unknown policy: " + c)

class CPUFreqEcoPolicy(CPUEcoPolicy):
  def __init__(self, config):
    CPUEcoPolicy.__init__(self, config)
    self.driver = CpuFreqHelper.get_driver()
   
    if not self.driver:
      print ("ERROR: CPU frequency scaling driver not found!")
      sys.exit(-1)

    self.fmin = CpuFreqHelper.get_hw_min_freq()
    self.fmax = CpuFreqHelper.get_hw_max_freq()
    self.fstart = CpuFreqHelper.get_gov_max_freq()
    self.init_governor(config, self.fmin, self.fmax)

  def set_freq(self, freq):
    if freq and not self.debug:
      #CpuPowerHelper.set_max_freq(freq)  
      CpuFreqHelper.set_gov_max_freq(freq)    

  def set_co2(self, co2):
    self.freq = self.co2val(co2)
    self.set_freq(self.freq)

  def reset(self):
    self.set_freq(self.fmax)

class CPUPowerEcoPolicy(CPUEcoPolicy):
  def __init__(self, config):
    EcoPolicy.__init__(self, config)
    
    if not LinuxPowercapHelper.available():
      print ("ERROR: RAPL powercap driver not found!")
      sys.exit(-1)

    if not LinuxPowercapHelper.enabled():
      print ("ERROR: RAPL driver found, but powercap is disabled!")
      print ("Please try to enable it as described here: https://askubuntu.com/a/1231490")
      print ("If it does not work, switch to frequency control policy.")
      sys.exit(-1)

    self.pmax = LinuxPowercapHelper.get_package_hw_max_power(0)
    self.pmin = int(0.5*self.pmax)
    self.pstart = LinuxPowercapHelper.get_package_power_limit(0)
    self.init_governor(config, self.pmin, self.pmax)

  def set_power(self, power_uw):
    if power_uw and not self.debug:
      LinuxPowercapHelper.set_power_limit(power_uw)

  def set_co2(self, co2):
    self.power = self.co2val(co2)
#    print("Update policy co2 -> power: ", co2, "->", self.power)
    self.set_power(self.power)

  def reset(self):
    self.set_power(self.pmax)

class GPUEcoPolicy(EcoPolicy):
  def __init__(self, config):
    EcoPolicy.__init__(self, config)

  @classmethod
  def from_config(cls, config):
    if not config:
      return None
    
    c = config["control"].lower()
    if c == "auto":
      if NvidiaGPUHelper.available():
        c = "power"
#      elif CpuFreqHelper.available():
#        c = "frequency"
      else:
        return None

    if c == "power":
      return GPUPowerEcoPolicy(config)
#    elif c == "frequency":
#      return CPUFreqEcoPolicy(config)
    elif c in OPTION_DISABLED or t in OPTION_DISABLED:
      return None
    else:
      raise ValueError("Unknown policy: " + c)

class GPUPowerEcoPolicy(GPUEcoPolicy):
  def __init__(self, config):
    GPUEcoPolicy.__init__(self, config)
    
    if not NvidiaGPUHelper.available():
      print ("ERROR: NVIDIA driver not found!")
      sys.exit(-1)

    plinfo = NvidiaGPUHelper.get_power_limit_all() 
    self.pmin = plinfo[0][0]
    self.pmax = plinfo[0][1]
    self.pstart = plinfo[0][2]
    self.init_governor(config, self.pmin, self.pmax, 0)

  def set_power(self, power_w):
    if power_w and not self.debug:
      NvidiaGPUHelper.set_power_limit(power_w)

  def set_co2(self, co2):
    self.power = self.co2val(co2)
#    print("Update policy co2 -> power: ", co2, "->", self.power)
    self.set_power(self.power)

  def reset(self):
    self.set_power(self.pmax)
    
class EcoPolicyManager(object):
  def __init__(self, config):
    self.policies = []
    cfg_dict = dict(config.items("policy")) if "policy" in config else None
    self.set_config(cfg_dict)
    
  def info_string(self):
    if self.policies:
      s = [p.info_string() for p in self.policies]
      return  ", ".join(s)
    else:
      return "None"

  def set_config(self, cfg):
    self.reset()
    self.policies = []
    if not cfg:
      return
    if "cpu" in cfg or "gpu" in cfg:
      all_cfg = None
    else:
      all_cfg = cfg
    cpu_cfg = cfg.get("cpu", all_cfg)
    gpu_cfg = cfg.get("gpu", all_cfg)
    cpu_pol = CPUEcoPolicy.from_config(cpu_cfg)
    gpu_pol = GPUEcoPolicy.from_config(gpu_cfg)
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
      res[domain] = p.get_config()
    return res
    
  def set_co2(self, co2):
    for p in self.policies:
      p.set_co2(co2)

  def reset(self):
    for p in self.policies:
      p.reset()
      
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

class EcoLogger(object):
  def __init__(self, config):
    self.log_fname = config["general"]["logfile"]
    if self.log_fname in OPTION_DISABLED:
      self.log_fname = None
    self.fmt = NAFormatter()
    self.idle_fields = False
    self.idle_debug = False
    
  def init_fields(self, monitors):
    if monitors.get_period_idle():
      self.idle_fields = True
#      self.idle_debug = True
    self.row_fmt = '{:<20}\t{:>10}\t{:>10}\t{:>10}\t{:>12.3f}\t{:>12.3f}\t{:>12.3f}\t{:>10.3f}\t{:>10.3f}'
    if self.idle_fields:
      self.row_fmt += "\t{:<10}"
    if self.idle_debug:
      self.row_fmt += "\t{:>10}\t{:>10.3f}"
          
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
      headers += ["MaxSessions", "MaxLoad1"] 
    self.log(self.fmt.format(self.header_fmt, *headers))

  def print_row(self, co2kwh, avg_freq, energy, avg_power, co2period, idle, stats):
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    max_freq = cpu_max_power = gpu_max_power = None
    if CpuFreqHelper.available():
      max_freq = round(CpuFreqHelper.get_gov_max_freq(unit=CpuFreqHelper.MHZ))
    if LinuxPowercapHelper.available():
      cpu_max_power = LinuxPowercapHelper.get_power_limit(LinuxPowercapHelper.WATT)
    if NvidiaGPUHelper.available():
      gpu_max_power = NvidiaGPUHelper.get_power_limit()
    cols = [ts, safe_round(co2kwh), max_freq, safe_round(avg_freq), cpu_max_power, gpu_max_power, avg_power, energy, co2period]
    if self.idle_fields:
      cols += [idle]
    if self.idle_debug:
      cols += [stats["MaxSessions"], stats["MaxLoad1"]]
      
    logstr = self.fmt.format(self.row_fmt, *cols)

#    logstr += "\t" + str(self.co2history.min_co2()) + "\t" + str(self.co2history.max_co2())

    self.log(logstr)

  def print_cmd(self, cmd):
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    logstr = "##" + ts + "\t" + cmd.upper()
    self.log(logstr)

class EcoFreq(object):
  def __init__(self, config):
    self.config = config
    self.co2provider = EmissionProvider.from_config(config)
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
      
    # make sure that CO2 sampling interval is a multiple of energy sampling interval
    self.sample_interval = self.monitor.adjust_interval(self.co2provider.interval)
    # print("sampling intervals co2/energy:", self.co2provider.interval, self.sample_interval)
    self.last_co2kwh = self.co2provider.get_co2()
    self.total_co2 = 0.
    
  def info(self):
    print("Log file:    ", self.co2logger.log_fname)
    print("CO2 Provider:", type(self.co2provider).__name__, "(interval =", self.co2provider.interval, "sec)")
    print("CO2 Policy:  ", self.co2policy.info_string())
    print("Idle Policy: ", self.idle_policy.info_string())
    print("Monitors:    ", self.monitor.info_string())

  def update_co2(self):
    # fetch new co2 intensity 
    co2 = self.co2provider.get_co2()
    if co2:
      if self.last_co2kwh:
        self.period_co2kwh = 0.5 * (co2 + self.last_co2kwh)
      else:
        self.period_co2kwh = co2
    else:
      self.period_co2kwh = self.last_co2kwh

    # prepare and print log row -> shows values for *past* interval!
    idle = self.monitor.get_period_idle()
    avg_freq = self.monitor.get_period_cpu_avg_freq(CpuFreqHelper.MHZ)
    energy = self.monitor.get_period_energy()
    avg_power = self.monitor.get_period_avg_power()
    if self.period_co2kwh:
      period_co2 = energy * self.period_co2kwh / JOULES_IN_KWH
      self.total_co2 += period_co2
    else:
      period_co2 = None
      
    stats = self.monitor.get_stats()
    
    self.co2logger.print_row(self.period_co2kwh, avg_freq, energy, avg_power, period_co2, idle, stats) 

    # apply policy for new co2 reading
    if co2:
      self.co2policy.set_co2(co2)
      self.co2history.add_co2(co2)
        
    self.last_co2kwh = co2
    
  def write_shm(self):  
    energy_j = str(round(self.monitor.get_total_energy(), 3))
    co2_g = self.total_co2
    if self.monitor.get_period_energy() > 0. and self.last_co2kwh:
      co2_g += self.monitor.get_period_energy() * self.last_co2kwh / JOULES_IN_KWH
    co2_g = str(round(co2_g, 3))
    with open(SHM_FILE, "w") as f:
      f.write(" ".join([energy_j, co2_g]))

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
        if duration % self.co2provider.interval == 0:
          self.update_co2()
          self.monitor.reset_period() 
        self.write_shm()  
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
    spins = [self.server.spin(), self.spin()]
    tasks = [asyncio.create_task(t) for t in spins]
    for t in tasks:
      await t

def parse_args():
  parser = argparse.ArgumentParser()
  parser.add_argument("-c", dest="cfg_file", default=None, help="Config file name.")
  parser.add_argument("-d", dest="diag", action="store_true", help="Show system info.")
  parser.add_argument("-g", dest="governor", default=None, help="Power governor (off = no power scaling).")
  parser.add_argument("-l", dest="log_fname", default=None, help="Log file name.")
  parser.add_argument("-t", dest="co2token", default=None, help="CO2Signal token.")
  args = parser.parse_args()
  return args

def read_config(args):
  def_dict = {'general' :  { 'LogFile'    : LOG_FILE    },
              'emission' : { 'Provider'    : 'co2signal',
                             'Interval'    : '600'     },
              'policy'   : { 'Control'     : 'auto',    
                             'Governor'    : 'linear', 
                             'CO2Range'    : 'auto'    },        
              'monitor'  : { 'PowerSensor' : 'auto',    
                             'Interval'    : '5'       }        
             }

  if args and args.cfg_file:
    cfg_file = args.cfg_file
  else:
    cfg_file = os.path.join(HOMEDIR, "ecofreq.cfg")

  if not os.path.exists(cfg_file):
    print("ERROR: Config file not found: ", cfg_file)
    sys.exit(-1)

  parser = configparser.ConfigParser()
  parser.read_dict(def_dict)
  parser.read(cfg_file)
 
  if args:
     if args.co2token:
       parser["co2signal"]["token"] = args.co2token
     if args.log_fname:
       parser["general"]["LogFile"] = args.log_fname
     if args.governor:
       parser["policy"]["Governor"] = args.governor

  return parser

def diag():
  print("EcoFreq v0.0.1 (c) 2021 Alexey Kozlov\n")
  CpuInfoHelper.info()
  print("")
  LinuxPowercapHelper.info()
  print("")
  CpuFreqHelper.info()
  print("")
  NvidiaGPUHelper.info()
  print("")
  IPMIHelper.info()
  print("")
  SuspendHelper.info()
  print("")
  
if __name__ == '__main__':

  try:
    args = parse_args()

    diag()

    if args.diag:
      sys.exit()
      
    cfg = read_config(args)
    ef = EcoFreq(cfg)
    ef.info()
    print("")
    asyncio.run(ef.main())
  except PermissionError:
    print(traceback.format_exc())
    print("\nPlease run EcoFreq with root permissions!\n")
  except:
    print("Exception:", traceback.format_exc())
    
  if os.path.exists(SHM_FILE):
    os.remove(SHM_FILE)
