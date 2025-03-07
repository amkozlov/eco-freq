import sys
import json
import urllib.request

class GeoHelper(object):
  API_URL = "http://ipinfo.io"    
  
  @classmethod
  def get_my_geoinfo(self):
    req = urllib.request.Request(self.API_URL)
#    req.add_header("User-Agent", "Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11")

    try:
      resp = urllib.request.urlopen(req).read()
      js = json.loads(resp)
      return js
    except:
      e = sys.exc_info()[0]
      print ("Exception: ", e)
      return None
      
  @classmethod
  def get_my_coords(self):
    try:
      js = self.get_my_geoinfo()
      lat, lon = js['loc'].split(",")
    except:
      e = sys.exc_info()[0]
      print ("Exception: ", e)
      lat, lon = None, None
    return lat, lon
