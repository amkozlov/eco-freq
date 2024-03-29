# EcoFreq: compute with cleaner energy

[![CC BY-NC-SA 4.0][cc-by-nc-sa-shield]][cc-by-nc-sa]

[cc-by-nc-sa]: http://creativecommons.org/licenses/by-nc-sa/4.0/
[cc-by-nc-sa-shield]: https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-blue.svg

In many regions with a high share of renewables - such as Germany, Spain, UK or California - CO2 emissions per kWh of electricity may vary two-fold within a single day, and up to four-fold within a year. This is due to both, variable production from solar and wind, and variable demand (peak hours vs. night-time/weekends). Hence, reducing energy consumption during these periods of high carbon intesity leads to overproportionate CO2 savings. This is exactly the idea behind EcoFreq: it modulates CPU/GPU power consumption *in realtime* according to the current "greenness" of the grid energy mix. Importantly, this modulation is absolutely transparent to user applications: they will run as usual without interruption, "accelerating" in times when energy comes mostly from renewables, and being throttled when fossil generation increases. 

And it gets even better if you have a [time-of-use electricity tarrif](https://www.irena.org/-/media/Files/IRENA/Agency/Publication/2019/Feb/IRENA_Innovation_ToU_tariffs_2019.pdf?la=en&hash=36658ADA8AA98677888DB2C184D1EE6A048C7470) or onsite solar generation: (being an) EcoFreq can save you a few cents ;)

TL;DR Just look at those awesome plots from [electricitymap.org](https://www.electricitymap.org) and you'll get the idea: 
![](https://github.com/amkozlov/eco-freq/blob/main/img/emap_all.png?raw=true)

## Installation

Prerequisites:
 - Linux system (tested with Ubuntu and CentOS)
 - Python3.7+
 - root privileges (for EcoFreq daemon)
 - (optional) API token -> [Which real-time CO2/price provider to use?](https://github.com/amkozlov/eco-freq/blob/main/config/README.md/) 
 - (optional) [`ipmitool`](https://github.com/ipmitool/ipmitool) to use IPMI power measurements

Please run installer script which will create a config file and register `systemd` service for EcoFreq:

```
sudo ./install.sh
```

## Usage

* For a quick test of EcoFreq on your system without configuration overhead (using mock CO2 provider): 

```
sudo ./ecofreq.py -c config/mock.cfg -l test.log
```

* After installing EcoFreq as a service, you can use standard `systemctl` commands to control it.  

Start:
```
sudo systemctl start ecofreq
```
Stop:
```
sudo systemctl stop ecofreq
```
Show status:
```
sudo systemctl status ecofreq
```

* Report energy and CO2 for a program run (assuming it runs exclusively -> to be improved): 

```
./ecorun.py sleep 5

energy_j:   343.003
energy_kwh: 0.0
co2_g:      0.003
```

* Report energy and CO2 statistics for a local EcoFreq instance (default log file):

```
./ecostat.py

EcoStat v0.0.1

Loading data from log file: /var/log/ecofreq.log

Time interval:               2021-05-18 04:02:59 - 2021-05-23 01:44:38
Duration active:             4 days, 4:35:21
Duration inactive:           17:06:18
CO2 intensity range [g/kWh]: 108 - 387
CO2 intensity mean [g/kWh]:  245
Energy consumed [J]:         134568612.5
Energy consumed [kWh]:       37.38
CO2 emitted [kg]:            9.23712
```

Use non-default log file (e.g., from a remote server):

```
./ecostat.py -l myserver.log
```

For a given time interval:

```
./ecostat.py --start 2021-05-18 --end 2021-05-20
``` 

## Configuration

TODO
