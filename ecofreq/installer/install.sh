#!/bin/bash

scriptdir=`readlink -f $0 | xargs dirname`
servicehome=/lib/systemd/system
sudoersfile=/etc/sudoers.d/ecofreq

uninstall=0
usesudo=1
ecocmd=`readlink -f $scriptdir/../ecofreq.py`
#ecouser=$logname
ecogroup=ecofreq
userline=

usage() 
{
  echo "Usage: ./install.sh -e SCRIPT [-c CONFIG]  [-u USER] [-g GROUP] [-n]"
  echo -e "\nOptions:"
  echo -e "\t-e SCRIPT    Full absolute path to the ecofreq.py (e.g. /home/user/.local/bin/ecofreq.py)"
  echo -e "\t-c CONFIG    Configuration file"
  echo -e "\t-u USER      User under which EcoFreq daemon will be started"
  echo -e "\t-g GROUP     Group with access to ecoctl (default: ecofreq)"
  echo -e "\t-n           Run without sudo"
}

#parse options
while getopts "h?e:c:u:g:nU" opt; do
    case "$opt" in
    h|\?)
        usage
        exit 0
        ;;
    e)  ecocmd=$OPTARG
        ;;
    c)  cfgfile=$OPTARG
        ;;
    u)  ecouser=${OPTARG:-$logname}
        ;;
    g)  ecogroup=$OPTARG
        ;;
    n)  usesudo=0
        ;;
    U)  uninstall=1
        ;;
    esac
done

if [ $uninstall -eq 1 ]; then
  rm $sudoersfile

  systemctl stop ecofreq
  systemctl disable ecofreq
  rm $servicehome/ecofreq.service

  echo -e "EcoFreq uninstalled!"

  exit
fi


if [ ! -z $cfgfile ]; then
  cfgabs=`readlink -f $cfgfile`
  ecocmd="$ecocmd -c $cfgabs"
fi

echo -e "Step 1: Create users and groups...\n"

if [ ! -z $ecogroup ]; then
  groupadd -f $ecogroup
fi

if [ ! -z $ecouser ]; then

  ecogroup=${ecogroup:-ecofreq}

  usermod -aG $ecogroup $ecouser

  echo -e "Step 2: Add sudoers.d file to run ecofreq daemon without password...\n"

  echo "$ecouser    ALL = (root:$ecogroup) NOPASSWD: $ecocmd" > $sudoersfile

  userline="User=$ecouser"
else
  usesudo=0
fi

echo -e "Step 3: Register systemd service...\n"

if [ $usesudo -eq 1 ]; then
  ecocmd="sudo $ecocmd"
fi

sed -e "s#<ECOFREQ_CMD>#$ecocmd#" -e "s#User=#$userline#" -e "s#<ECOFREQ_GROUP>#$ecogroup#" $scriptdir/ecofreq.service > $servicehome/ecofreq.service

systemctl daemon-reload

systemctl enable ecofreq

systemctl start ecofreq

echo -e "\nInstallation complete!\n"
