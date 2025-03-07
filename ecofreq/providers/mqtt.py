from ecofreq.providers.common import EcoProvider
from ecofreq.mqtt import MQTTManager

class MQTTEcoProvider(EcoProvider):
  LABEL="mqtt"

  def __init__(self, config, glob_interval, label):
    EcoProvider.__init__(self, config, glob_interval)
    self.label = label
    self.set_config(config)
    self.mqtt_client = MQTTManager.add_client(self.label, config)

  def set_config(self, config):
    self.topic = config.get("topic", None)

  def get_config(self):
    cfg = super().get_config()
    cfg["topic"] = self.topic
    cfg["label"] = self.label
    return cfg

  def get_data(self):
    data = {}
    val = self.mqtt_client.get_msg()
#    print(val)
    data[self.FIELD_DEFAULT] = float(val) if val is not None else None
#    print(data)
    return data
