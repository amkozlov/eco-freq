import sys
import os.path
from subprocess import check_output,DEVNULL,CalledProcessError

from ecofreq.utils import read_int_value
from .cpu import CpuInfoHelper

class AMDEsmiHelper(object):
  CMD_ESMI_TOOL="/opt/e-sms/e_smi/bin/e_smi_tool"
  MAX_PLIMIT_LABEL="PowerLimitMax (Watts)"
  CUR_PLIMIT_LABEL="PowerLimit (Watts)"
  UWATT, MWATT, WATT = 1e-6, 1e-3, 1
 
  @classmethod
  def run_esmi(cls, params, parse_out=True):
    cmdline = cls.CMD_ESMI_TOOL + " " + params 
    try:
      out = check_output(cmdline, shell=True, stderr=DEVNULL, universal_newlines=True)
    except CalledProcessError as e:
      if e.returncode == 210:
        out = e.output
      else:
        raise e  
    if parse_out:
      result = {}
      for line in out.split("\n"):
        if line:
          toks = line.split("|")
          if len(toks) > 2:
            field = toks[1].strip()
            result[field] = toks[2:-1]
#      print(result)    
      return result  

  @classmethod
  def available(cls):
    try:
      out = cls.run_esmi("-v")
      return True
    except CalledProcessError:
      return False

  @classmethod
  def enabled(cls, pkg=0):
    try:
      if cls.get_package_power_limit(pkg):
        return True
      else:
        return False
    except CalledProcessError:
      return False

  @classmethod
  def get_field(cls, out, field, pkg=0):
    if pkg >= 0:
      return out[field][pkg]
    else:
      return out[field]

  @classmethod
  def get_package_hw_max_power(cls, pkg, unit=WATT):
    if cls.available():
      params = "--showsockpower"
      out = cls.run_esmi(params)
      limit_w = float(cls.get_field(out, cls.MAX_PLIMIT_LABEL, pkg)) 
      return limit_w / unit 
    else:
      return None

  @classmethod
  def get_package_power_limit(cls, pkg, unit=WATT):
    if cls.available():
      params = "--showsockpower"
      out = cls.run_esmi(params)
      limit_w = float(cls.get_field(out, cls.CUR_PLIMIT_LABEL, pkg)) 
      return limit_w / unit 
    else:
      return None

  @classmethod
  def get_power_limit(cls, unit=WATT):
    if cls.available():
      params = "--showsockpower"
      out = cls.run_esmi(params)
      pkg_limit_w = cls.get_field(out, cls.CUR_PLIMIT_LABEL, -1)
      limit_w = sum([float(x) for x in pkg_limit_w]) 
      return limit_w / unit 
    else:
      return None

  @classmethod
  def set_package_power_limit(cls, pkg, power, unit=WATT):
    # value must be in mW !
    val = round(power * unit / cls.MWATT)
    params = "--setpowerlimit {:d} {:d}".format(pkg, val)
    cls.run_esmi(params, False)

  @classmethod
  def set_power_limit(cls, power, unit=WATT):
    num_sockets = CpuInfoHelper.get_sockets()
    for pkg in range(num_sockets):
      cls.set_package_power_limit(pkg, power, unit)
    
  @classmethod
  def info(cls):
    if cls.available():
      outfmt = "ESMI CPU{0}: max_hw_limit = {1} W, current_limit = {2} W" 
      params = ""
      out = cls.run_esmi(params)
      num_sockets = int(cls.get_field(out, "NR_SOCKETS"))
      for pkg in range(num_sockets):
        maxp = float(cls.get_field(out, cls.MAX_PLIMIT_LABEL, pkg))
        curp = float(cls.get_field(out, cls.CUR_PLIMIT_LABEL, pkg))
        print(outfmt.format(pkg, maxp, curp))
    else:
        print("AMD E-SMI tool not found.")

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
