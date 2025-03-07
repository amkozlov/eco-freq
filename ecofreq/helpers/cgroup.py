from ecofreq.utils import *

class LinuxCgroupHelper(object):
  CGROUP_FS_PATH="/sys/fs/cgroup/"

  @classmethod
  def available(cls):
    return os.path.exists(cls.CGROUP_FS_PATH)
  
  @classmethod
  def subsystems(cls, grp=""):
    sub = []
    if cls.available():
      for sname in ["cpu", "freezer"]:
        if cls.enabled(sname, grp):
          sub.append(sname)
    return sub
  
  @classmethod
  def info(cls):
    print("Linux cgroup available: ", end ="")
    if cls.available():
      print("YES", end ="")
      helper = None
      if LinuxCgroupV1Helper.enabled():
        helper = LinuxCgroupV1Helper
      elif LinuxCgroupV2Helper.enabled():
        helper = LinuxCgroupV2Helper
        
      if helper:
        print(" ({}) ({})".format(helper.VERSION, ",".join(helper.subsystems())))
      else:
        print("(disabled)")
    else:
      print("NO")

class LinuxCgroupV1Helper(LinuxCgroupHelper):
  VERSION = "v1"
  PROCS_FILE="cgroup.procs"
  CFS_QUOTA_FILE="cpu.cfs_quota_us"
  CFS_PERIOD_FILE="cpu.cfs_period_us"
  FREEZER_STATE_FILE="freezer.state"

  @classmethod
  def subsys_path(cls, sub):
    return os.path.join(cls.CGROUP_FS_PATH, sub)

  @classmethod
  def subsys_file(cls, sub, grp, fname):
    return os.path.join(cls.subsys_path(sub), grp, fname)

  @classmethod
  def procs_file(cls, sub, grp):
    return cls.subsys_file(sub, grp, cls.PROCS_FILE)

  @classmethod
  def cfs_quota_file(cls, grp):
    return cls.subsys_file("cpu", grp, cls.CFS_QUOTA_FILE)

  @classmethod
  def cfs_period_file(cls, grp):
    return cls.subsys_file("cpu", grp, cls.CFS_PERIOD_FILE)

  @classmethod
  def freezer_state_file(cls, grp):
    return cls.subsys_file("freezer", grp, cls.FREEZER_STATE_FILE)

  @classmethod
  def read_cgroup_int(cls, sub, grp, fname):
    return read_int_value(cls.subsys_file(sub, grp, fname))
  
  @classmethod
  def get_cpu_cfs_period_us(cls, grp):
    return read_int_value(cls.cfs_period_file(grp))

  @classmethod
  def set_cpu_cfs_period_us(cls, grp, period_us):
    return write_value(cls.cfs_period_file(grp), period_us)

  @classmethod
  def get_cpu_cfs_quota_us(cls, grp):
    return read_int_value(cls.cfs_quota_file(grp))

  @classmethod
  def set_cpu_cfs_quota_us(cls, grp, quota_us):
    write_value(cls.cfs_quota_file(grp), int(quota_us))
    
  @classmethod
  def set_cpu_quota(cls, grp, quota, period=None):
    if period:
      cls.set_cpu_cfs_period_us(grp, period)
    else:
      period = cls.get_cpu_cfs_period_us(grp)
    quota_us = int(quota * period)  
    cls.set_cpu_cfs_quota_us(grp, quota_us)
    
  @classmethod
  def get_cpu_quota(cls, grp, ncores):
    quota_us = cls.get_cpu_cfs_quota_us(grp)
    period_us = cls.get_cpu_cfs_period_us(grp)
    if quota_us == -1:
      return ncores
    else:
      return float(quota_us) / period_us

  @classmethod
  def freeze(cls, grp):
    write_value(cls.freezer_state_file(grp), "FROZEN")

  @classmethod
  def unfreeze(cls, grp):
    write_value(cls.freezer_state_file(grp), "THAWED")
    
  @classmethod
  def add_proc_to_cgroup(cls, grp, pid):
    write_value(cls.procs_file(grp), pid)

  @classmethod
  def enabled(cls, sub="cpu", grp=""):
    return os.path.isfile(cls.procs_file(sub, grp))

class LinuxCgroupV2Helper(LinuxCgroupHelper):
  VERSION = "v2"
  PROCS_FILE="cgroup.procs"
  CPU_QUOTA_FILE="cpu.max"
  FREEZER_STATE_FILE="cgroup.freeze"

  @classmethod
  def subsys_file(cls, grp, fname):
    return os.path.join(cls.CGROUP_FS_PATH, grp, fname)
  
  @classmethod
  def procs_file(cls, grp):
    return cls.subsys_file(grp, cls.PROCS_FILE)
  
  @classmethod
  def freezer_state_file(cls, grp):
    return cls.subsys_file(grp, cls.FREEZER_STATE_FILE)
  
  @classmethod
  def cpu_quota_file(cls, grp):
    return cls.subsys_file(grp, cls.CPU_QUOTA_FILE)

  @classmethod
  def freeze(cls, grp):
    write_value(cls.freezer_state_file(grp), "1")

  @classmethod
  def unfreeze(cls, grp):
    write_value(cls.freezer_state_file(grp), "0")

  @classmethod
  def set_cpu_quota(cls, grp, quota, period=None):
    fname = cls.cpu_quota_file(grp)
    old_period  = read_value(fname, 1)
    if not period:
      period = old_period
    if not isinstance(quota, str):
      quota = quota * int(period)
#    print(quota, period)  
    write_value(fname, quota)

  @classmethod
  def get_cpu_quota(cls, grp, ncores):
    fname = cls.cpu_quota_file(grp)
    quota, period = read_value(fname).split(" ")
    if quota == "max":
      return ncores
    else:
      return float(quota) / int(period)
   
  @classmethod
  def enabled(cls, sub="", grp=""):
    if not sub:
      return os.path.isfile(cls.procs_file(grp))
    elif sub == "cpu":
      return os.path.isfile(cls.cpu_quota_file(grp))
    elif sub == "freezer":
      return os.path.isfile(cls.freezer_state_file(grp))
    else:
      return False
