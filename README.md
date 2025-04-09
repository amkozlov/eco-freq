# EcoFreq: compute with cleaner & cheaper energy

[![CC BY-NC-SA 4.0][cc-by-nc-sa-shield]][cc-by-nc-sa]

[cc-by-nc-sa]: http://creativecommons.org/licenses/by-nc-sa/4.0/
[cc-by-nc-sa-shield]: https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-blue.svg

In many regions with a high share of renewables - such as Germany, Spain, UK or California - CO2 emissions per kWh of electricity may vary two-fold within a single day, and up to four-fold within a year. This is due to both, variable production from solar and wind, and variable demand (peak hours vs. night-time/weekends). Hence, reducing energy consumption during these periods of high carbon intesity leads to overproportionate CO2 savings. This is exactly the idea behind EcoFreq: it modulates CPU/GPU power consumption *in realtime* according to the current "greenness" of the grid energy mix. Importantly, this modulation is absolutely transparent to user applications: they will run as usual without interruption, "accelerating" in times when energy comes mostly from renewables, and being throttled when fossil generation increases. 

And it gets even better if you have dynamic electricity pricing (e.g., [Octopus](https://octopus.energy/smart/agile/), [Tibber](https://tibber.com/en) etc.) or on-site solar panels: (being an) EcoFreq can save you a few cents ;)

**TL;DR Compute faster when electricity is abundant and green, throttle down when it is expensive and dirty:**
![](https://github.com/amkozlov/eco-freq/blob/dev/img/ecofreq_tldr.png?raw=true)

## Installation

Prerequisites:
 - Linux system (tested with Ubuntu and CentOS)
 - Python3.8+ with `pip` (`pipx` recommended)
 - (optional) API token -> [Which real-time CO2/price provider to use?](https://github.com/amkozlov/eco-freq/blob/main/config/README.md/) 
 - (optional) [`ipmitool`](https://github.com/ipmitool/ipmitool) to use IPMI power measurements

First, install EcoFreq package using `pip` or `pipx`:

```
pipx install ecofreq
```

This will install EcoFreq locally under the current (non-privileged) user. Since power limiting typically requires root privileges, you will need sudo permissions to use all features of EcoFreq ([see details](https://github.com/amkozlov/eco-freq/blob/dev/doc/INSTALL.md#Permissions)).

Alternatively, you can install and run EcoFreq under root:
```
sudo pipx install ecofreq
```
This is less secure, but makes configuration simpler. 

For production use, you will likely want to configure EcoFreq daemon to run in the background: ([HOWTO](https://github.com/amkozlov/eco-freq/blob/dev/doc/INSTALL.md#Daemon))

## Usage

* Show information about your system and its power limiting capabilities:

```
ecofreq info
```

* For a quick test of EcoFreq on your system without configuration overhead (using mock CO2 provider): 

```
ecofreq -c mock -l test.log
```

* After [installing EcoFreq as a service](https://github.com/amkozlov/eco-freq/blob/dev/doc/INSTALL.md#Daemon), you can use standard `systemctl` commands to control it. 

```
sudo systemctl start ecofreq
sudo systemctl status ecofreq
sudo systemctl stop ecofreq
```

Command-line tool `ecoctl` allows to query and control the EcoFreq service. 
If you want to run `ecoctl` without `sudo` (recommended), either add your user to the `ecofreq` group,
or [configure socket permissions accordingly](https://github.com/amkozlov/eco-freq/blob/main/doc/CONFIG.md#Server). 

* Show EcoFreq status:

```
ecoctl
```

* Change power scaling policy:

```
ecoctl policy co2:step:100=0.7:200=0.5

ecoctl policy const:50%

ecoctl policy maxperf
```

* Report energy and CO2 for a program run (assuming it runs exclusively -> to be improved): 

```
ecorun sleep 10

time_s:     10.003
pwr_avg_w:  88.724
energy_j:   887.5
energy_kwh: 0.0
co2_g:      0.098
cost_ct:    0.001
```

* Report energy and CO2 statistics for a local EcoFreq instance (default log file):

```
ecostat.py

EcoStat v0.0.1

Loading data from log file: /var/log/ecofreq.log

Time interval:               2022-01-01 00:03:30 - 2022-06-30 23:53:23
Monitoring active:           175 days, 20:24:55
Monitoring inactive:         0:16:44
CO2 intensity range [g/kWh]: 109 - 545
CO2 intensity mean [g/kWh]:  341
Energy consumed [J]:         4358414437.5
Energy consumed [kWh]:       1210.671
= electric car travel [km]:  6053
Total CO2 emitted [kg]:      409.507177

Idle time:                   41 days, 9:43:30
Idle energy [kWh]:           127.437
Idle = e-car travel [km]:    637
Idle CO2 [kg]:               44.531762
```

For more examples, see [USAGE.md](https://github.com/amkozlov/eco-freq/blob/main/doc/USAGE.md/)

## Configuration

See [CONFIG.md](https://github.com/amkozlov/eco-freq/blob/main/doc/CONFIG.md/)

## Citation

Oleksiy Kozlov, Alexandros Stamatakis. **EcoFreq: Compute with Cheaper, Cleaner Energy via Carbon-Aware Power Scaling**, *ISC-2024*.

Open access: https://ieeexplore.ieee.org/document/10528928
