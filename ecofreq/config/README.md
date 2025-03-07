# Which real-time CO2 and price provider to use? 

We recommend following region-specific APIs, and provide sample config files for them: 

## CO2

  - Great Britain (UK): [National Grid ESO](https://carbonintensity.org.uk/) -> [ecofreq.cfg.ukgrid](https://github.com/amkozlov/eco-freq/blob/main/config/ecofreq.cfg.ukgrid)
  - Continental Europe: [EnergyCharts](https://energy-charts.info/) -> [ecofreq.cfg.energycharts](https://github.com/amkozlov/eco-freq/blob/main/config/ecofreq.cfg.energycharts) or
                        [ElectricityMaps](https://static.electricitymaps.com/api/docs/index.html) -> [ecofreq.cfg.electricitymaps](https://github.com/amkozlov/eco-freq/blob/main/config/ecofreq.cfg.electricitymaps)
  - Germany, Baden-Württemberg: [StromGedacht](https://www.stromgedacht.de/) -> [ecofreq.cfg.stromgedacht](https://github.com/amkozlov/eco-freq/blob/main/config/ecofreq.cfg.stromgedacht)
  - US: [WattTime](https://www.watttime.org/) -> [ecofreq.cfg.watttime](https://github.com/amkozlov/eco-freq/blob/main/config/ecofreq.cfg.watttime) 
  - Rest of the world: [ElectricityMaps/CO2Signal](https://static.electricitymaps.com/api/docs/index.html) -> [ecofreq.cfg.co2signal](https://github.com/amkozlov/eco-freq/blob/main/config/ecofreq.cfg.co2signal)  

## Price (wholesale)

  - Continental Europe: [EnergyCharts](https://energy-charts.info/)
  - US: [GridStatus.io](https://api.gridstatus.io/docs) -> [ecofreq.cfg.watttime](https://github.com/amkozlov/eco-freq/blob/main/config/ecofreq.cfg.watttime)

## Price (retail)

 - UK: [Octopus](https://octopus.energy/)
 - Germany: [Tibber](https://tibber.com)
 - Germany, Austria: [Awattar](https://www.awattar.at/)
