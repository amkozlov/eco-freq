import sys
import subprocess

from ecofreq.config import HOMEDIR

class EcofreqInstaller(object):
  INSTALL_SH = HOMEDIR / "installer" / "install.sh"

  @classmethod
  def install(cls, args):
    print("Installing EcoFreq service...")
    efscript = sys.argv[0]
    cmd = [str(cls.INSTALL_SH), "-e", efscript]
    if args.duser:
      cmd += ["-u", args.duser]
    if args.dgroup:
      cmd += ["-g", args.dgroup]
    if args.cfg_file:
      cmd += ["-c", args.cfg_file]
#    print(cmd)
    subprocess.run(cmd)

  @classmethod
  def uninstall(cls, args):
    print("Removing EcoFreq service...")
    cmd = [str(cls.INSTALL_SH), "-U"]
    subprocess.run(cmd)
