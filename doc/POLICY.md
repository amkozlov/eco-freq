# Policy = Governor + Control method

In EcoFreq, dynamic power scaling policy consists of two components:
- Governor is a formula to convert the input signal (e.g., `co2` or `price`) to the capacity limit value
- Control method defines how capacity limit is applied (e.g., `power` or `frequency` cap) 

## Control methods

### `power` cap
```
[policy]
control=power
```
This method defines direct power cap for CPU or GPU.
Supported hardware:
* Intel CPUs (Sandy Bridge and later, ca. 2012+) - via RAPL
* AMD CPUs ([Zen3/Zen4 and later](https://github.com/amd/esmi_ib_library?tab=readme-ov-file#supported-hardware)) - via [E-SMI](https://github.com/amd/esmi_ib_library), `e_smi_tool` must be installed under `/opt/e-sms/e_smi/bin/` (default)
* NVIDIA GPUs (most modern consumer and HPC cards) - via  `nvidia-smi -pl` 


### `frequency` cap (DVFS)
```
[policy]
control=frequency
```

### utilization cap (`cgroup`)
```
[cpu_policy]
control=cgroup
cgroup=ef
```


### utilization cap (`docker`) -> EXPERIMENTAL
```
[cpu_policy]
control=docker
containers=my_cool_container,e8f7089b12f1
```



## Governors 

* Constant (`const`)

```
const:80%
const:2000MHz
const:150W
const:12c
```

* Discrete (`list`)

```
list:black=0.5:red=0.5:yellow=0.7:green=max
list:very low=max:low=max:moderate=0.8:high=0.6:very high=0.6
```

* Step function (`step`)

```
step:100=70%:200=50%
```

* Linear function (`linear`)

```
linear:100:500
```

