#!/bin/bash

ecohome=`readlink -f $0 | xargs dirname`
servicehome=/lib/systemd/system

co2policy=
co2country=
co2token=

cfgfile=ecofreq.cfg

echo -e "EcoFreq installer\n"

if [ `whoami` != root ]; then
    echo -e "Please run this script as root or using sudo!\n"
    exit
fi

echo -e "Step 1: Prepare config file...\n"

if [ -z "$co2token" ]; 
then
  read -p "Please enter your CO2Signal API token (get it for free here: https://co2signal.com/): " co2token
  echo ""
fi

if [ -z "$co2country" ];
then
  read -p "Please enter your country/grid zone code [autodetect]: " co2country
  echo ""
  if [ -z "$co2country" ];
  then
    co2country=auto
  fi
fi

if [ -z "$co2policy" ];
then
  read -p "Do you wish to enable power scaling by default? [Y/n]: " yn
  echo ""
  if [[ $yn =~ ^[Nn]$ ]] 
  then
    co2policy=none
  else
    co2policy=linear
  fi
fi

sed -e "s/<CO2POLICY>/$co2policy/" -e "s/<CO2COUNTRY>/$co2country/" -e "s/<CO2TOKEN>/$co2token/" ecofreq.cfg.templ > $cfgfile

echo -e "Configuration saved to: $cfgfile\n"

echo -e "Step 2: Register systemd service...\n"

sed -e "s#<ECOFREQ_HOME>#$ecohome#" ecofreq.service > $servicehome/ecofreq.service

sudo systemctl daemon-reload

sudo systemctl enable ecofreq

sudo systemctl start ecofreq

echo -e "\nInstallation complete!\n"
