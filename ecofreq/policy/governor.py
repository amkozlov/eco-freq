from ecofreq.config import OPTION_DISABLED

class Governor(object):
  LABEL="None"

  def __init__(self, args, vmin, vmax):
    self.val_round = 3
    
  def info_args(self):
    return {}
  
  def info_string(self, unit={"": 1}):
    args = [self.LABEL]
    d = self.info_args()
    uname, ufactor = list(unit.items())[0]
    for k in d.keys():
      if d[k]:
        arg = "{0}={1}{2}".format(k, d[k] / ufactor, uname)
      else:
        arg = "{0}{1}".format(k / ufactor, uname)
      args.append(arg)
    return ":".join(args)
  
  def round_val(self, val):
    return int(round(val, self.val_round))

  @classmethod
  def parse_args(cls, toks):
    args = {}
    for t in toks:
      if "=" in t:
        k, v = t.split("=")
        args[k] = v
      else:
        args[t] = None
    return args

  @classmethod
  def parse_val(cls, vstr, vmin, vmax, units={}):
    if vstr == "min":
      val = vmin
    elif vstr == "max":
      val = vmax
    else:  
      val = None
      # absolute value with unit specifier (W, MHz etc.)
      for uname, ufactor in units.items():
        if vstr.endswith(uname.lower()):
          val = float(vstr.strip(uname.lower())) * ufactor
          break 
      if not val:
        # relative value
        if vstr.endswith("%"):
          p = float(vstr.strip("%")) / 100
        else:
          p = float(vstr)
        val = vmax * p
    if val > vmax or val < vmin:
      raise ValueError("Constant governor parameter out-of-bounds: " + vstr)   
    return val
  
  @classmethod
  def from_config(cls, config, vmin, vmax, units):
    govstr = config["governor"].lower()
    if govstr == "default":
      govstr = config["defaultgovernor"].lower()
    toks = govstr.split(":")
    t = toks[0] 
    args = cls.parse_args(toks[1:])
    if t == "linear" or t == "lineargovernor":
      return LinearGovernor(args, vmin, vmax, units)
    elif t == "step":
      return StepGovernor(args, vmin, vmax, units)
    elif t == "list":
      return ListGovernor(args, vmin, vmax, units)
    elif t == "maxperf":
      args = {}
      return ConstantGovernor(args, vmin, vmax, units)
    elif t == "const":
      return ConstantGovernor(args, vmin, vmax, units)
    elif t in OPTION_DISABLED:
      return None
    else:
      raise ValueError("Unknown governor: " + t)

class ConstantGovernor(Governor):
  LABEL="const"

  def __init__(self, args, vmin, vmax, units):
    Governor.__init__(self, args, vmin, vmax)
    if len(args) > 0:
      s = list(args.keys())[0]
      self.val = Governor.parse_val(s, vmin, vmax, units)
    else:
      self.val = vmax
    
  def info_args(self):
    return {self.round_val(self.val) : None} 

  def co2val(self, co2):
    return round(self.val, self.val_round)
  
class LinearGovernor(Governor):
  LABEL="linear"
  
  def __init__(self, args, vmin, vmax, units):
    Governor.__init__(self, args, vmin, vmax)
    self.co2min = self.co2max = -1
    self.vmin = vmin
    self.vmax = vmax
    if len(args) == 2:
      self.co2min, self.co2max = sorted([int(x) for x in args.keys()])
      v1 = args[str(self.co2max)]
      v2 = args[str(self.co2min)]
      if v1:
        self.vmin = Governor.parse_val(v1, vmin, vmax, units)
      if v2:
        self.vmax = Governor.parse_val(v2, vmin, vmax, units)

  def info_args(self):
    args = {}
    args[self.co2min] = self.round_val(self.vmax)
    args[self.co2max] = self.round_val(self.vmin)
    return args 

  def co2val(self, co2):
    co2 = float(co2)
    if co2 >= self.co2max:
      k = 0.0
    elif co2 <= self.co2min:
      k = 1.0
    else:
      k = 1.0 - float(co2 - self.co2min) / (self.co2max - self.co2min)
    val = self.vmin + (self.vmax - self.vmin) * k
    val = int(round(val, self.val_round))
    return val

class StepGovernor(Governor):
  LABEL="step"
  
  def __init__(self, args, vmin, vmax, units, discrete=False):
    Governor.__init__(self, args, vmin, vmax)
    self.vmin = vmin
    self.vmax = vmax
    self.discrete = discrete
    self.steps = []
    if self.discrete:
      klist = args.keys()
    else:
      klist = sorted([int(x) for x in args.keys()], reverse=True)
    for s in klist:
      v = Governor.parse_val(args[str(s)], vmin, vmax, units)
      self.steps.append((s, v))

  def info_args(self):
    args = {}
    for s, v in reversed(self.steps):
      args[s] = v
    return args 

  def co2val(self, co2):
    val = self.vmax
    for s, v in self.steps:
      if (self.discrete and str(co2) == s) or (not self.discrete and float(co2) >= s):
        val = v
        break 
    val = int(round(val, self.val_round))
    return val

class ListGovernor(StepGovernor):
  LABEL="list"

  def __init__(self, args, vmin, vmax, units):
    StepGovernor.__init__(self, args, vmin, vmax, units, True)
