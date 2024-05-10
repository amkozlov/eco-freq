#!/bin/bash

ecohome=`readlink -f $0 | xargs dirname`
servicehome=/lib/systemd/system

co2country=
co2policy=

cfgfile=ecofreq.cfg

os_detect()
{
 if [ `uname -a | grep -c Darwin` -eq 1 ]; then
   os=osx
   echo "macOS is not supported yet, sorry!"
   exit 1
 elif [ `uname -a | grep -c Ubuntu` -eq 1 ]; then
   os=ubuntu
 elif [ `uname -a | grep -c CentOS` -eq 1 ]; then
   os=redhat
 else
   os=unknown
 fi
}

create_config()
{
  if [ -z "$co2country" ];
  then
    read -p "Please enter your country/grid zone code (e.g., DE, GB or US-CAL-CISO): " co2country
    echo ""
  fi

  if [ -z "$co2policy" ];
  then
    read -p "Do you wish to enable power scaling by default? [Y/n]: " yn
    echo ""
    if [[ $yn =~ ^[Nn]$ ]] 
    then
      co2policy=none
    else
      co2policy=default
    fi
  fi
  
  sed -e "s/<CO2POLICY>/$co2policy/" -e "s/<CO2COUNTRY>/$co2country/" ecofreq.cfg.templ > $cfgfile
}



echo -e "EcoFreq installer\n"

if [ `whoami` != root ]; then
    echo -e "Please run this script as root or using sudo!\n"
    exit 1
fi

os_detect

echo -e "Step 1: Installing dependencies...\n"

pip3 install -r requirements.txt

echo -e "Step 2: Prepare config file...\n"

if [ -f "$1" ]; then
  cp $1 $cfgfile
else
  create_config
fi

echo -e "Configuration saved to: $cfgfile\n"

echo -e "Step 3: Register systemd service...\n"

sed -e "s#<ECOFREQ_HOME>#$ecohome#" ecofreq.service > $servicehome/ecofreq.service

addgroup ecofreq

systemctl daemon-reload

systemctl enable ecofreq

systemctl start ecofreq

echo -e "\nInstallation complete!\n"
