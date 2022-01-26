#!/usr/bin/env python3

import os
import sys
import argparse
from datetime import datetime, timedelta
from subprocess import call,STDOUT,DEVNULL,CalledProcessError

from ecofreq import SHM_FILE, JOULES_IN_KWH, TS_FORMAT
from ecofreq import EcoClient, EcoFreq

def parse_args():
  parser = argparse.ArgumentParser()
  cmd_list = ["info", "policy"]
  parser.add_argument("command", choices=cmd_list, default="info", help="Command", nargs="?")
  parser.add_argument("cmd_args", nargs="*")
  args = parser.parse_args()
  return args

def cmd_info(args):
  info = ec.info()
  print("EcoFreq is RUNNING")
  print("")
  print("= CONFIGURATION =")
  EcoFreq.print_info(info)
  print("")
  print("= STATUS =")
  print("State:                 ", info["idle_state"])
  if info["idle_state"] == "IDLE":
    print("Idle duration:         ", timedelta(seconds = int(info["idle_duration"])))
  print("Load:                  ", info["idle_load"])
  print("Power [W]:             ", round(info["avg_power"]))
  print("CO2 intensity [g/kWh]: ", info["last_co2kwh"])     
  print("")
  print("= STATISTICS =")
  ts_start = datetime.strptime(info["start_date"], TS_FORMAT)
  uptime = str(datetime.now().replace(microsecond=0) - ts_start)
  print("Running since:         ", info["start_date"], "(up " + uptime + ")")     
  print("Energy consumed [kWh]: ", round(float(info["total_energy_j"]) / JOULES_IN_KWH, 3))     
  print("CO2 total [kg]:        ", round(float(info["total_co2"]) / 1000., 6))

def policy_is_enabled(pol, domain="cpu"):
  if not domain in pol["co2policy"]:
    return False
  elif pol["co2policy"][domain].get("governor", "none") == "none":
    return False
  else:
    return True  

def policy_str(pol, domain="cpu"):
  d = pol["co2policy"][domain]
  return "{0}({1})".format(d["control"], d["governor"])
  
def cmd_policy(args):
  policy = ec.get_policy()
  
  if len(args.cmd_args) > 0:
    # set policy
    print("Old policy:", policy_str(policy))
    gov = args.cmd_args[0]
    if gov in ["off", "disabled"]:
      gov = "none"
    elif gov in ["on", "enabled", "default", "eco"]:
      gov = "linear"
    policy["co2policy"]["cpu"]["governor"] = gov
    ret = ec.set_policy(policy)
  
    policy = ec.get_policy()
    print("New policy:", policy_str(policy))
  else:
    # get policy
    print("CO2 policy:", policy_str(policy))

  print() 
  pol_state = "ENABLED" if policy_is_enabled(policy) else "DISABLED"
  print("CO2-aware power scaling is now", pol_state)

def run_command(args):
  if args.command == "info":
    cmd_info(args)
  elif args.command == "policy":  
    cmd_policy(args)      
  else:
    print("Unknown command:", args.command)

if __name__ == '__main__':
  ec = EcoClient()
#  print(ec.info())

  args = parse_args()
#  print(args)
  
  try:
    run_command(args)
  except ConnectionRefusedError:
    print("ERROR: Connection refused! Please check that EcoFreq daemon is running.")


