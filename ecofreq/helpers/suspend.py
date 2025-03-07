import os.path

from ecofreq.utils import read_value,write_value

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
