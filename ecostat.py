#!/usr/bin/env python3

import sys
from datetime import datetime
import time
import os
import configparser
import argparse
import string

LOG_FILE = "/var/log/ecofreq.log"
TS_FORMAT = "%Y-%m-%dT%H:%M:%S"

def read_value(fname):
    with open(fname) as f:
      return f.readline()

def read_int_value(fname):
  return int(read_value(fname))

def write_value(fname, val):
    if os.path.isfile(fname):
      with open(fname, "w") as f:
        f.write(str(val))
      return True
    else:
      return False
    
class NAFormatter(string.Formatter):
    def __init__(self, missing='NA'):
        self.missing = missing

    def format_field(self, value, spec):
        if value == None: 
          value = self.missing
          spec = spec.replace("f", "s")
        return super(NAFormatter, self).format_field(value, spec)
      
class EcoStat(object):      
  def __init__(self, args):
    self.log_fname = args.log_fname
    self.energy = 0
    self.co2 = 0
    self.co2kwh_min = 1e6
    self.co2kwh_max = 0
    self.timestamp_min = datetime.now()
    self.timestamp_max = datetime.fromtimestamp(0)
    
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
        toks = line.split("\t")
        ts = datetime.strptime(toks[time_idx].strip(), TS_FORMAT)
        self.timestamp_min = min(self.timestamp_min, ts)
        self.timestamp_max = max(self.timestamp_max, ts)
        co2kwh = float(toks[co2kwh_idx])
        self.co2kwh_min = min(self.co2kwh_min, co2kwh)
        self.co2kwh_max = max(self.co2kwh_max, co2kwh)
        self.energy += float(toks[energy_idx]) 
        self.co2 += float(toks[co2_idx]) 

  def print_stats(self):
    print ("Time interval:        ", self.timestamp_min, "-", self.timestamp_max)     
    print ("Duration:             ", self.timestamp_max - self.timestamp_min)     
    print ("CO2 intensity [g/kWh]:", round(self.co2kwh_min), "-", round(self.co2kwh_max))     
    print ("Energy consumed [J]:  ", round(self.energy, 3))     
    print ("Energy consumed [kWh]:", round(self.energy / 3.6e6, 3))     
    print ("CO2 emitted [kg]:     ", round(self.co2 / 1000., 6))  
    print("")   
  
  
def parse_args():
  parser = argparse.ArgumentParser()
  parser.add_argument("-c", dest="cfg_file", default=None, help="Config file name.")
  parser.add_argument("-l", dest="log_fname", default=LOG_FILE, help="Log file name.")
  args = parser.parse_args()
  return args

if __name__ == '__main__':

  args = parse_args()

  print("EcoStat v0.0.1\n")

  es = EcoStat(args)
  es.compute_stats()
  es.print_stats()
