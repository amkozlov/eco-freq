import pathlib

JOULES_IN_KWH = 3.6e6
OPTION_DISABLED = ["none", "off"]

TS_FORMAT = "%Y-%m-%dT%H:%M:%S"

HOMEDIR = pathlib.Path(__file__).parent
DATADIR = HOMEDIR / "data"
CONFIGDIR = HOMEDIR / "config"
LOG_FILE = "/var/log/ecofreq.log"
SHM_FILE = "/dev/shm/ecofreq"
