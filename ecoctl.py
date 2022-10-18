#!/usr/bin/env python3

import os
import sys
import argparse
from datetime import datetime, timedelta
from subprocess import call,STDOUT,DEVNULL,CalledProcessError

from ecofreq import SHM_FILE, JOULES_IN_KWH, TS_FORMAT
from ecofreq import EcoClient, EcoFreq

def safe_round(val, digits=0):
  return round(val, digits) if (isinstance(val, float)) else val

def parse_args():
  parser = argparse.ArgumentParser()
  cmd_list = ["info", "policy", "provider"]
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
  print("Energy price [ct/kWh]: ", safe_round(info["last_price"], 3))     
  print("")
  print("= STATISTICS =")
  ts_start = datetime.strptime(info["start_date"], TS_FORMAT)
  uptime = str(datetime.now().replace(microsecond=0) - ts_start)
  print("Running since:         ", info["start_date"], "(up " + uptime + ")")     
  print("Energy consumed [kWh]: ", round(float(info["total_energy_j"]) / JOULES_IN_KWH, 3))     
  print("CO2 total [kg]:        ", round(float(info["total_co2"]) / 1000., 6))
  print("Cost total [EUR]:      ", round(float(info["total_cost"]) / 100., 6))

def policy_is_enabled(pol, domain="cpu"):
  if not domain in pol["co2policy"]:
    return False
  elif pol["co2policy"][domain].get("governor", "none") == "none":
    return False
  else:
    return True  

def policy_str(pol, domain="cpu"):
  d = pol["co2policy"][domain]
  return "{0}(governor = {1}, metric = {2})".format(d["control"], d["governor"], d["metric"])

def provider_str(prov):
  d = prov["co2provider"]
  interval = d["provider"]["interval"]
  provlist = []
  for m in d["provider"].keys():
    if m not in ["all", "co2", "price"]:
      continue
    prov_type = d["provider"][m]
    if prov_type.startswith("const"):
      provstr = prov_type
    elif prov_type == "co2signal":
      param1 = "Country = " + str(d["co2signal"]["country"])
#      param2 = "Token = " + str(d["co2signal"]["token"])
      provstr = "{0} (interval = {1} s, {2})".format(prov_type, interval, param1)
    elif prov_type == "mock":
      param1 = "CO2Range = " + str(d["mock"]["co2range"])
      param2 = "CO2File = " + str(d["mock"]["co2file"])
      provstr = "{0} (interval = {1} s, {2}, {3})".format(prov_type, interval, param1, param2)
    provlist.append(m + " = " + provstr)
  return ", ".join(provlist)
  
def cmd_policy(args):
  policy = ec.get_policy()
  
  if len(args.cmd_args) > 0:
    # set policy
    print("Old policy:", policy_str(policy))
    gov = args.cmd_args[0]
    if gov.startswith("co2:") or gov.startswith("price:") or gov.startswith("fossil_pct:"):
      metric, gov = gov.split(":", 1)
      policy["co2policy"]["cpu"]["metric"] = metric
    if gov in ["off", "disabled"]:
      gov = "none"
    elif gov in ["on", "enabled", "default", "eco"]:
      gov = "default"
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
  
def wildcard_set(d, attr, params, idx):
  if len(params) > idx and params[idx] != "*":
    d[attr] = params[idx]

def cmd_provider(args):
  prov = ec.get_provider()
  
#  print(prov)
  if len(args.cmd_args) > 0:
    # set provider
    print("Old provider:", provider_str(prov))

    pstr = args.cmd_args[0] 
    if pstr.startswith("co2:") or pstr.startswith("price:") or pstr.startswith("fossil_pct:"):
      metric, pstr = pstr.split(":", 1)
      prov["co2provider"]["provider"]['all'] = None
    else:
      metric = "all"
    
    prov_params = pstr.split(":")
    p = prov["co2provider"]
    wildcard_set(p["provider"], metric, prov_params, 0)
    wildcard_set(p["provider"], "interval", prov_params, 1)
    prov_type = p["provider"][metric]
    if prov_type not in p:
      p[prov_type] = {}
    if prov_type == "co2signal":
      wildcard_set(p["co2signal"], "token", prov_params, 2)
      wildcard_set(p["co2signal"], "country", prov_params, 3)
    elif prov_type == "mock":
      wildcard_set(p["mock"], "co2range", prov_params, 2)
      wildcard_set(p["mock"], "co2file", prov_params, 3)
    elif prov_type == "const":
      wildcard_set(p["const"], metric, prov_params, 2)
#    print(prov)
    ret = ec.set_provider(prov)
  
    prov = ec.get_provider()
    print("New provider:", provider_str(prov))
  else:
    # get policy
    print("CO2 provider:", provider_str(prov))

def run_command(args):
  if args.command == "info":
    cmd_info(args)
  elif args.command == "policy":  
    cmd_policy(args)      
  elif args.command == "provider":  
    cmd_provider(args)      
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


