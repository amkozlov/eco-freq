#!/usr/bin/env python3

import os
import sys
import time
from subprocess import call,STDOUT,DEVNULL,CalledProcessError

from ecofreq import SHM_FILE, JOULES_IN_KWH
from ecofreq import EcoClient

def read_shm():
  with open(SHM_FILE) as f:
    joules, co2 = [float(x) for x in f.readline().split(" ")]
  return joules, co2

def set_governor(gov):
  try:
    ec = EcoClient()
    policy = ec.get_policy()
    old_gov = policy["co2policy"]["cpu"]["governor"]
    policy["co2policy"]["cpu"]["governor"] = gov
#    print(policy)
    ret = ec.set_policy(policy)
    return old_gov
  except ConnectionRefusedError:
    print("ERROR: Connection refused! Please check that EcoFreq daemon is running.")

if __name__ == '__main__':

  if not os.path.exists(SHM_FILE):
    print("ERROR: File not found:", SHM_FILE)
    print("Please make sure that EcoFreq service is active!")
    sys.exit(-1)

#  print(sys.argv)
  
  outfile = None
  runname = "noname"
  cmdline_start = 1
  if len(sys.argv) > 3 and sys.argv[1] == "-p":
    gov = sys.argv[2]
    if gov in ["off", "disabled"]:
      gov = "none"
    elif gov in ["on", "enabled", "default", "eco"]:
      gov = "linear"    
    old_gov = set_governor(gov)
    cmdline_start += 2
  else:
    old_gov = None

  if len(sys.argv) > 5 and sys.argv[3] == "-o":
    outfile = sys.argv[4]
    cmdline_start += 2

  if len(sys.argv) > 7 and sys.argv[5] == "-n":
    runname = sys.argv[6]
    cmdline_start += 2
 
  cmdline = sys.argv[cmdline_start:]
  
  start_joules, start_co2 = read_shm()
  
  start_time = time.time()

#  call(cmdline, shell=True)
  call(cmdline)

  end_time = time.time()

  end_joules, end_co2 = read_shm()
  
  if old_gov:
    set_governor(old_gov)

  diff_joules = end_joules - start_joules
  diff_kwh = diff_joules / JOULES_IN_KWH
  diff_co2 = end_co2 - start_co2
  
  diff_time = end_time - start_time  
  avg_pwr = diff_joules / diff_time

  print("")
  print("time_s:    ", round(diff_time, 3))
  print("pwr_avg_w: ", round(avg_pwr, 3))
  print("energy_j:  ", round(diff_joules, 3))
  print("energy_kwh:", round(diff_kwh, 3))
  print("co2_g:     ", round(diff_co2, 3))
  
  if outfile:
    if not os.path.exists(outfile):
      with open(outfile, "w") as f:
        headers = ["name", "policy", "time_s", "pwr_avg_w", "energy_j", "energy_kwh", "co2_g"]
        f.write(",".join(headers) + "\n");
      
    with open(outfile, "a") as f:
      vals = [runname, gov]
      res = [diff_time, avg_pwr, diff_joules, diff_kwh, diff_co2]
      vals += [str(round(x, 3)) for x in res]
      f.write(",".join(vals) + "\n")


