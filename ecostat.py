#!/usr/bin/env python3

import sys
from datetime import datetime, timedelta
import time
import os
import configparser
import argparse
import string

LOG_FILE = "/var/log/ecofreq.log"
TS_FORMAT = "%Y-%m-%dT%H:%M:%S"
DATE_FORMAT = "%Y-%m-%d"

def parse_timestamp(str, exit_on_error=False):
  ts = None
  for fmt in TS_FORMAT, DATE_FORMAT: 
    try:
      ts = datetime.strptime(str.strip(), fmt)
    except ValueError:
      pass
    
  if not ts and exit_on_error:
    print("ERROR: Invalid date/time: ", str)
    sys.exit(-1)
  else:  
    return ts  
    
class EcoStat(object):      
  def __init__(self, args):
    self.log_fname = args.log_fname
    self.samples = 0
    self.energy = 0
    self.co2 = 0
    self.co2kwh_min = 1e6
    self.co2kwh_max = 0
    self.timestamp_min = datetime.max
    self.timestamp_max = datetime.min
    
    if args.ts_start:
      self.ts_start = parse_timestamp(args.ts_start, True)
    else:
      self.ts_start = datetime.min
    
    if args.ts_end:
      self.ts_end = parse_timestamp(args.ts_end, True)
    else:
      self.ts_end = datetime.max

    if self.ts_end == self.ts_start:
      self.ts_end += timedelta(days=1)
      
    if self.ts_end < self.ts_start:
      print("ERROR: End date is earlier than start date! start =", self.ts_start, ", end=", self.ts_end)
      sys.exit(-1)

    if not os.path.isfile(self.log_fname):
      print("ERROR: Log file not found: ", self.log_fname)
      sys.exit(-1)
    
  def compute_stats(self):
    time_idx = 0
    co2kwh_idx = 1
    energy_idx = 6
    co2_idx = 7
    print("Loading data from log file:", self.log_fname, "\n")
    with open(self.log_fname) as f:
      for line in f:
        if line.startswith("#"):
          continue
        toks = line.split("\t")
        ts = datetime.strptime(toks[time_idx].strip(), TS_FORMAT)
        if ts < self.ts_start or ts > self.ts_end:
          continue
        self.timestamp_min = min(self.timestamp_min, ts)
        self.timestamp_max = max(self.timestamp_max, ts)
        co2kwh = float(toks[co2kwh_idx])
        self.co2kwh_min = min(self.co2kwh_min, co2kwh)
        self.co2kwh_max = max(self.co2kwh_max, co2kwh)
        self.energy += float(toks[energy_idx]) 
        self.co2 += float(toks[co2_idx])
        self.samples += 1 

  def print_stats(self):
    if self.samples> 0:
      print ("Time interval:        ", self.timestamp_min, "-", self.timestamp_max)     
      print ("Duration:             ", self.timestamp_max - self.timestamp_min)     
      print ("CO2 intensity [g/kWh]:", round(self.co2kwh_min), "-", round(self.co2kwh_max))     
      print ("Energy consumed [J]:  ", round(self.energy, 3))     
      print ("Energy consumed [kWh]:", round(self.energy / 3.6e6, 3))     
      print ("CO2 emitted [kg]:     ", round(self.co2 / 1000., 6))  
    else:
      print ("No samples found in the given time interval!")
    print("")   
  
  
def parse_args():
  parser = argparse.ArgumentParser()
  parser.add_argument("-c", dest="cfg_file", default=None, help="Config file name.")
  parser.add_argument("-l", dest="log_fname", default=LOG_FILE, help="Log file name.")
  parser.add_argument("--start", dest="ts_start", default=None, help="Start date/time (format: yy-mm-ddTHH:MM:SS).")
  parser.add_argument("--end", dest="ts_end", default=None, help="End date/time (format: yy-mm-ddTHH:MM:SS).")
  args = parser.parse_args()
  return args

if __name__ == '__main__':

  args = parse_args()

  print("EcoStat v0.0.1\n")

  es = EcoStat(args)
  es.compute_stats()
  es.print_stats()
