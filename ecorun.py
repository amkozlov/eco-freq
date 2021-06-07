#!/usr/bin/env python3

import os
import sys
from subprocess import call,STDOUT,DEVNULL,CalledProcessError

from ecofreq import SHM_FILE, JOULES_IN_KWH

def read_shm():
  with open(SHM_FILE) as f:
    joules, co2 = [float(x) for x in f.readline().split(" ")]
  return joules, co2

if __name__ == '__main__':

  if not os.path.exists(SHM_FILE):
    print("ERROR: File not found:", SHM_FILE)
    print("Please make sure that EcoFreq service is active!")
    sys.exit(-1)

  cmdline = sys.argv[1:]
  
  start_joules, start_co2 = read_shm()

#  call(cmdline, shell=True)
  call(cmdline)

  end_joules, end_co2 = read_shm()

  diff_joules = end_joules - start_joules
  diff_kwh = diff_joules / JOULES_IN_KWH
  diff_co2 = end_co2 - start_co2

  print("")
  print("energy_j:  ", round(diff_joules, 3))
  print("energy_kwh:", round(diff_kwh, 3))
  print("co2_g:     ", round(diff_co2, 3))


