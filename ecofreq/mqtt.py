import asyncio
import json

try:
  from aiomqtt import Client, MqttError
  mqtt_found = True
except:
  mqtt_found = False

class MQTTClient(object):
  recv_queue: asyncio.Queue
  send_queue: asyncio.Queue
  
  def __init__(self, config):
    self.hostname = config.get("host", "localhost")
    self.port = None
    self.username = None
    self.password = None
    self.sub_topic = config.get("topic", None)
    self.pub_topic = config.get("pubtopic", None)
    self.pub_fields = config.get("pubfields", None)
    if self.pub_fields:
      self.pub_fields = self.pub_fields.split(",")
        
  async def run(self):
    self.recv_queue = asyncio.Queue()
    self.send_queue = asyncio.Queue()
    while True:
      print('Connecting to MQTT broker...')
      try:
          async with Client(
              hostname=self.hostname,
#                    port=self.port,
              username=self.username,
              password=self.password
          ) as client:
              print('Connected to MQTT broker')

              # Handle pub/sub
              await asyncio.gather(
                  self.handle_sub(client),
                  self.handle_pub(client)
              )
      except MqttError:
          print('MQTT error:')
          await asyncio.sleep(5)  

  async def handle_sub(self, client):
    if not self.sub_topic:
      return
    await client.subscribe(self.sub_topic)
    async for message in client.messages:
      self.recv_queue.put_nowait(message.payload)
    
  async def handle_pub(self, client):
    if not self.pub_topic:
      return
    while True:
      data = await self.send_queue.get()
      payload = json.dumps(data)
#      print(payload)
      await client.publish(self.pub_topic, payload=payload.encode())
      self.send_queue.task_done()

  def get_msg(self):
    try:
      return self.recv_queue.get_nowait()
    except (asyncio.queues.QueueEmpty, AttributeError):
      return None

  def put_msg(self, data):
    if self.pub_fields:
      data = {key: data[key] for key in self.pub_fields} 
    self.send_queue.put_nowait(data)
    
class MQTTManager(object):
  CLMAP = {}

  @classmethod
  def add_client(cls, label, config):
    client = MQTTClient(config)
    cls.CLMAP[label] = client
    return client
  
  @classmethod
  def get_client(cls, label):
    return cls.CLMAP[label]

  @classmethod
  async def run(cls):
    tasks = [asyncio.create_task(c.run()) for c in cls.CLMAP.values()]
    for t in tasks:
      await t
