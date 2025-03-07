from subprocess import check_output,DEVNULL,CalledProcessError

class DockerHelper(object):
  CMD_DOCKER = "docker"

  @classmethod
  def available(cls):
     try:
       out = cls.run_cmd(["-v"])
       #TODO check version
       return True
     except CalledProcessError:
       return False
     
  @classmethod
  def run_cmd(cls, args, parse_output=True):
    cmdline = cls.CMD_DOCKER + " " + " ".join(args) 
#    print(cmdline)
    out = check_output(cmdline, shell=True, stderr=DEVNULL, universal_newlines=True)
    result = []
    if parse_output:
      for line in out.split("\n"):
        if line:
          if not line.startswith("Emulate Docker CLI"):
            result.append([x.strip() for x in line.split(",")])
    return result  

  @classmethod
  def get_container_ids(cls):
    out = cls.run_cmd(["ps", "--format", "{{.ID}}"])
    ids = [x[0] for x in out]
    return ids 
 
  @classmethod
  def set_container_cpus(cls, ctrs, cpus):
    if not ctrs:
      ctrs = cls.get_container_ids()
    for c in ctrs:
      cls.run_cmd(["container", "update", "--cpus", str(cpus), c], False)

  @classmethod
  def set_pause(cls, ctrs, pause=True):
    args = ["pause" if pause else "unpause"]
    if not ctrs:
      args += ["-a"]
    else:  
      args += ctrs
    cls.run_cmd(args, False)

