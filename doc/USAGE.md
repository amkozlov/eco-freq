# EcoFreq usage

## ecoctl

* Show EcoFreq status

```
./ecoctl.py
```
```
EcoFreq is RUNNING

= CONFIGURATION =
Log file:     /var/log/ecofreq.log
CO2 Provider: all = ElectricityMapsProvider (interval = 15 sec), price = EnergyChartsProvider (interval = 15 sec)
CO2 Policy:   CPUPowerEcoPolicy (governor = const:15.0W), metric = co2
Idle Policy:  None
Monitors:     PowercapEnergyMonitor (interval = 5 sec), CPUFreqMonitor (interval = 5 sec), IdleMonitor (interval = 5 sec)

= STATUS =
State:                  ACTIVE
Load:                   2.24
Power [W]:              5
CO2 intensity [g/kWh]:  119
Energy price [ct/kWh]:  7.572

= STATISTICS =
Running since:          2024-05-10T21:38:06 (up 0:20:01)
Energy consumed [kWh]:  0.004
CO2 total [kg]:         0.000408
Cost total [EUR]:       0.00027
```

* Show current policy

```
./ecoctl.py policy
```
```
CO2 policy: CPUPowerEcoPolicy(governor = step:100=10.5W:200=7.5W, metric = co2)

CO2-aware power scaling is now ENABLED
```

* Set new policy

```
./ecoctl.py policy const:80%
```
```
Old policy: CPUPowerEcoPolicy(governor = step:100=10.5W:200=7.5W, metric = co2)
New policy: CPUPowerEcoPolicy(governor = const:12.0W, metric = co2)

CO2-aware power scaling is now ENABLED
```

* Show current provider

```
./ecoctl.py provider
```
```
CO2 provider: all = electricitymaps (interval = 15 s), price = energycharts (interval = 15 s)
```


## ecorun


* Run command and report energy/CO2/cost statistics:

```
./ecorun.py <CMD>
```

```
time_s:     10.003
pwr_avg_w:  88.724
energy_j:   887.5
energy_kwh: 0.0
co2_g:      0.098
cost_ct:    0.001
```

* Run command with a non-default policy:

```
./ecorun.py -p maxperf <CMD>
```

```
./ecorun.py -p const:0.8 <CMD>
```

```
./ecorun.py -p cpu:const:2000MHz <CMD>
```

NOTE: Currently, `ecorun` assumes single-user scenario since it measures system-wide energy consumption and changes global EcoFreq state.

## ecostat

* Report energy and CO2 statistics for a local EcoFreq instance (default log file):

```
./ecostat.py
```
```
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

* Use a different log file:

```
./ecostat.py -l myserver.log
```


* Limit time interval:

```
./ecostat.py --start 2024-01-01 --end 2024-02-01
```


