# EcoFreq installation guide

## Prerequisites

 - Linux system (tested with Ubuntu and CentOS)
 - Python3.8+ with `pip` (`pipx` recommended)
 - (optional) API token -> [Which real-time CO2/price provider to use?](https://github.com/amkozlov/eco-freq/blob/main/config/README.md/) 
 - (optional) [`ipmitool`](https://github.com/ipmitool/ipmitool) to use IPMI power measurements

## Python package

First, install EcoFreq package using `pip` or `pipx`:

```
pipx install ecofreq
```

This will install EcoFreq locally under the current (non-privileged) user. Since power limiting typically requires root privileges, you will need sudo permissions to use all features of EcoFreq ([see details](https://github.com/amkozlov/eco-freq/blob/main/doc/INSTALL.md#Permissions)).

Alternatively, you can install and run EcoFreq under root:
```
sudo pipx install ecofreq
```
This is less secure, but makes configuration simpler. 

## Configuration

Example configuration files are available under: https://github.com/amkozlov/eco-freq/tree/main/config

You can easily create a config file from template using `showcfg` command, e.g.
```
ecofreq -c energycharts showcfg > myecofreq.cfg
```
You can then customize `myecofreq.cfg` by specifying your region, carbon intensity and price provider, API tokens etc.
For details, please see [CONFIG.md](https://github.com/amkozlov/eco-freq/blob/main/doc/CONFIG.md/)

## Daemon

Then, please run installer command which will register `systemd` service and configure permissions for EcoFreq:

```
ecofreq -c myecofreq.cfg install
```

Check that EcoFreq daemon is up and running:
```
ecoctl
```

## Permissions

By default, EcoFreq will try to obtain root permissions (`sudo`) which are (unfortunately) required for most power scaling methods. 
To ensure it also works for the daemon, the installation process described above will automatically create the respective `/etc/sudpers.d/ecofreq` file.

If this is not possible or not desired, you can enforce rootless mode with

```
ecofreq --user
```

Please note, however, that EcoFreq funtionality will be limited in rootless mode.

These limitations can be avoided/relaxed by adjusting permissions for the relevant system files and utilities: TODO
