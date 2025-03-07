from subprocess import check_output,DEVNULL,CalledProcessError

class NvidiaGPUHelper(object):
  CMD_NVSMI = "nvidia-smi"

  @classmethod
  def available(cls):
#   return call(cls.CMD_NVSMI, shell=True, stdout=DEVNULL, stderr=DEVNULL) == 0
    try:
      out = cls.query_gpus(fields = "power.draw,power.management")
#      print (out)
      return "Enabled" in out[0][1]
    except CalledProcessError:
      return False

  @classmethod
  def query_gpus(cls, fields, fmt = "csv,noheader,nounits", qcmd="--query-gpu"):
    cmdline = cls.CMD_NVSMI + " --format=" + fmt +  " " + qcmd + "=" + fields 
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
  def get_supported_freqs(cls):
    return cls.query_gpus(fields="graphics", qcmd="--query-supported-clocks")

  @classmethod
  def get_hw_max_freq(cls):
    return [float(x[0]) for x in cls.query_gpus(fields = "clocks.max.gr")]

  @classmethod
  def set_freq_limit(cls, max_gpu_freq):
    cmdline = cls.CMD_NVSMI + " -lgc 0," + str(int(max_gpu_freq))
    cmdline += " --mode=1"
    out = check_output(cmdline, shell=True, stderr=DEVNULL, universal_newlines=True)

  @classmethod
  def reset_freq_limit(cls):
    cmdline = cls.CMD_NVSMI + " -rgc"
    out = check_output(cmdline, shell=True, stderr=DEVNULL, universal_newlines=True)

  @classmethod
  def info(cls):
    if cls.available():
      field_list = "name,power.min_limit,power.max_limit,power.limit"
      cnt = 0
      for gi in cls.query_gpus(fields = field_list, fmt="csv,noheader"):
        print ("GPU" + str(cnt) + ": " + gi[0] + ", min_hw_limit = " + gi[1] + ", max_hw_limit = " + gi[2] + ", current_limit = " + gi[3])
        cnt += 1
