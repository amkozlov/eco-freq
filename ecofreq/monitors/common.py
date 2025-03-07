class Monitor(object):
  def __init__(self, config):
    self.interval = int(config["monitor"]["interval"])
    self.period_samples = 0
    self.total_samples = 0
    
  def reset_period(self):
    self.period_samples = 0

  # subclasses must override this to call actual update routine
  def update_impl(self):
    pass
  
  def update(self):
    self.update_impl() 
    self.period_samples += 1
    self.total_samples += 1
    
  # subclasses must override this
  def get_stats(self):
    return {}
