import os
import string

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

def getbool(x):
  if isinstance(x, str):
    return True if x.lower() in ['1', 'y', 'yes', 'true', 'on'] else False
  else:
    return x
    
class NAFormatter(string.Formatter):
    def __init__(self, missing='NA'):
        self.missing = missing

    def format_field(self, value, spec):
        if value == None: 
          value = self.missing
          spec = spec.replace("f", "s")
        return super(NAFormatter, self).format_field(value, spec)
