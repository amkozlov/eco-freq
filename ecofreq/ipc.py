import os
import asyncio
import json

class EcoServer(object):
  IPC_FILE="/var/run/ecofreq.sock"
  BUF_SIZE=2048

  def __init__(self, iface, config=None):
    import grp
    self.iface = iface
    self.fmod = 0o660
    gname = "ecofreq"
    if config and "server" in config:
      gname = config["server"].get("filegroup", gname)
      if "filemode" in config["server"]:
        self.fmod = int(config["server"]["filemode"], 8)
    try:
      self.gid = grp.getgrnam(gname).gr_gid
    except KeyError:
      self.gid = -1
  
  async def spin(self):
    self.serv = await asyncio.start_unix_server(self.on_connect, path=self.IPC_FILE)
    if self.gid >= 0:
      os.chown(self.IPC_FILE, -1, self.gid)
    os.chmod(self.IPC_FILE, self.fmod)
    
#    print(f"Server init")    
#    async with self.serv:
    await self.serv.serve_forever()    
    
  async def on_connect(self, reader, writer):
    data = await reader.read(self.BUF_SIZE)
    msg = data.decode()
    # addr = writer.get_extra_info('peername')
    
    # print(f"Received {msg!r}")    

    try:
      req = json.loads(msg)
      cmd = req['cmd']
      args = req['args'] if 'args' in req else {}
      res = self.iface.run_cmd(cmd, args)
      response = json.dumps(res)
    except:
      response = "Invalid message"  
    
    writer.write(response.encode())
    await writer.drain()
    writer.close()

class EcoClient(object):
    
  async def unix_send(self, message):
      try:
        reader, writer = await asyncio.open_unix_connection(EcoServer.IPC_FILE)
      except FileNotFoundError:
        raise ConnectionRefusedError
  
#     print(f'Send: {message!r}')
      writer.write(message.encode())
      await writer.drain()
  
      data = await reader.read(EcoServer.BUF_SIZE)
      # print(f'Received: {data.decode()!r}')
  
      writer.close()
      
      return data.decode()

  def send_cmd(self, cmd, args=None):
    obj = dict(cmd=cmd, args=args)
    msg = json.dumps(obj)
    resp = asyncio.run(self.unix_send(msg))
    try:
      return json.loads(resp)
    except:
      return dict(status='ERROR', error='Exception')
  
  def info(self):
    return self.send_cmd('info')

  def get_policy(self):
    return self.send_cmd('get_policy')

  def set_policy(self, policy):
    return self.send_cmd('set_policy', policy)
  
  def get_provider(self):
    return self.send_cmd('get_provider')
  
  def set_provider(self, provider):
    return self.send_cmd('set_provider', provider)

