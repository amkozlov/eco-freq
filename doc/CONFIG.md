# EcoFreq config file reference 

## Provider

The `[provider]` section configures APIs that provide real-time carbon and price signal.
Each API can provide one or more metrics, such as `co2` (gCO2/kWh), `price` (ct/kWh) or `index` (discrete "traffic light" signal).
For instance, below we set constant electricity price of 30 ct/kWh, and get real-time carbon intensity from ElectricityMaps every 15 min: 
```
[provider]
co2=electricitymaps
price=const:30
interval=900
```

We can use `all=` to assign the default provider (i.e. all its metrics will be used, unless explicitely overwritten).
For instance, we can use traffic light signal and renewable share from EnergyCharts, carbon intensity from ElectricityMaps, and real-time price from Tibber:
```
[provider]
all=energycharts
co2=electricitymaps
price=tibber
interval=3600
```

For details about specific providers and their settings, see [PROVIDER.md](https://github.com/amkozlov/eco-freq/blob/main/doc/PROVIDER.md)

## Policy

The `[policy]` section defines how to adjust power-relevant settings based on the real-time carbon/price signal.
First, we define which `metric` to use, e.g. `co2` or `price`. Then, we define `control` method, such as `power` (direct power capping),
`frequency` (DVFS), or `cgroup` (utilization capping). By default (`auto`), EcoFreq will use "the best" available control method on the current system.
Finally, we define the exact relationship between (input) metric value and (output) control setting using the so-called `governor`.
For instance, we can use `step` governor to set 80% powercap whenever carbon intensity is above 200 gCO2/kWh, and decrease it further down to 60% above 400 gCO2/kWh:

```
[policy]
Metric=co2
Control=power
DefaultGovernor=step:200=0.8:400=0.6
Governor=default
```

On hybrid systems, we can define separate policies for CPU and GPU in `[cpu_policy]` and `[gpu_policy]` sections, respectively.

For details about specific policies and governors, see [POLICY.md](https://github.com/amkozlov/eco-freq/blob/main/doc/POLICY.md)

## Monitor

EcoFreq supports multiple power/energy monitoring interfaces (`RAPL`, `IPMI`, `nvidia-smi`), and usually can automatically detect which ones are available.
However, you can manually enforce using a specific inteface, and set polling interval in the `[monitor]` section:

```
[monitor]
PowerSensor=rapl
Interval=5
```

## Server

The `[server]` section defines who can use the `ecoctl` command to change EcoFreq settings on-the-fly. It works by changing the ownership of and permissions on the IPC socket file (`/var/run/ecofreq.sock`). By default, this file is owned by `root:ecofreq` with group read/write permissions (`0660`). 

Allow access for members of the `staff` user group:
```
[server]
filegroup=staff
filemode=0o660
```

Allow access for any user (not recommended):
```
[server]
filemode=0o666
```

## Suspend-on-Idle

EcoFreq can automatically detect idling and switch to the low-energy standby mode (suspend-to-RAM).
For instance, to suspend after 15 min (900 s) at <10% CPU utilization, add these lines to your config file:

```
[idle]
IdleMonitor=on
LoadCutoff=0.10
# 1 = 1min average, 2 = 5min, 3 = 15min
LoadPeriod=1
# Switch to low-energy standby mode (suspend) after x seconds of idling
SuspendAfter=900
```
**WARNING**: Before enabling this feature, please check that [Wake-on-LAN](https://wiki.archlinux.org/title/Wake-on-LAN) is enabled. 
Then you can later wake up a suspended system by sending a 'magic packet' (e.g., `wakeonlan <MAC>`).
