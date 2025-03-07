#!/usr/bin/env python3

import os
import sys
import time
from subprocess import call

from ecofreq.config import SHM_FILE, JOULES_IN_KWH
from ecofreq.ipc import EcoClient

def read_shm():
  with open(SHM_FILE) as f:
    ts, joules, co2, cost = [float(x) for x in f.readline().split(" ")]
  return ts, joules, co2, cost

def set_governor(gov):
  try:
    ec = EcoClient()
    policy = ec.get_policy()
    domain = "cpu"
    if gov.startswith("cpu:") or gov.startswith("gpu:"):
      domain, gov = gov.split(":", 1)
      if not domain in policy["co2policy"]:
        policy["co2policy"][domain] = {}

    old_gov = policy["co2policy"][domain]["governor"]
    if gov.startswith("co2:") or gov.startswith("price:") or gov.startswith("fossil_pct:") or gov.startswith("index:"):
      old_gov = ":".join([policy["co2policy"][domain]["metric"], old_gov])
      metric, gov = gov.split(":", 1)
      policy["co2policy"][domain]["metric"] = metric
    policy["co2policy"][domain]["governor"] = gov
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
  iters = 1
  cmdline_start = 1
  if len(sys.argv) > 3 and sys.argv[1] == "-p":
    gov = sys.argv[2]
    if gov in ["off", "disabled"]:
      gov = "none"
    elif gov in ["on", "enabled", "default", "eco"]:
      gov = "default"    
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

  if len(sys.argv) > 9 and sys.argv[7] == "-i":
    iters = int(sys.argv[8])
    cmdline_start += 2
 
  cmdline = sys.argv[cmdline_start:]
  
  start_ts, start_joules, start_co2, start_cost = read_shm()
  
  start_time = time.time()

#  call(cmdline, shell=True)
  for i in range(iters):
    call(cmdline)

  end_time = time.time()

  start_ts, end_joules, end_co2, end_cost = read_shm()
  
  if old_gov:
    set_governor(old_gov)

  diff_joules = end_joules - start_joules
  diff_kwh = diff_joules / JOULES_IN_KWH
  diff_co2 = end_co2 - start_co2
  diff_cost = end_cost - start_cost
  
  diff_time = end_time - start_time  
  avg_pwr = diff_joules / diff_time

  print("")
  print("time_s:    ", round(diff_time, 3))
  print("pwr_avg_w: ", round(avg_pwr, 3))
  print("energy_j:  ", round(diff_joules, 3))
  print("energy_kwh:", round(diff_kwh, 3))
  print("co2_g:     ", round(diff_co2, 3))
  print("cost_ct:   ", round(diff_cost, 3))
  
  if outfile:
    if not os.path.exists(outfile):
      with open(outfile, "w") as f:
        headers = ["name", "policy", "time_s", "pwr_avg_w", "energy_j", "energy_kwh", "co2_g", "cost_ct"]
        f.write(",".join(headers) + "\n");
      
    with open(outfile, "a") as f:
      vals = [runname, gov]
      res = [diff_time, avg_pwr, diff_joules, diff_kwh, diff_co2, diff_cost]
      vals += [str(round(x, 3)) for x in res]
      f.write(",".join(vals) + "\n")


