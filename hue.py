#!/usr/bin/python3

import sys, os
# Add relative paths for the directory where the adapter is located as well as the parent
sys.path.append(os.path.dirname(__file__))
sys.path.append(os.path.join(os.path.dirname(__file__),'../../base'))

from sofabase import sofabase, adapterbase, configbase
import devices
import definitions

import math
import random
from collections import namedtuple, Counter
import json
from huecolor import ColorHelper, colorConverter
from ahue import Bridge, QhueException, create_new_username
import asyncio
import aiohttp
import datetime


class hue(sofabase):
    
    class adapter_config(configbase):
    
        def adapter_fields(self):
            self.poll_time=self.set_or_default('poll_time', 5)
            self.hue_user=self.set_or_default('hue_user', mandatory=True)
            self.hue_bridge_address=self.set_or_default('hue_bridge_address', mandatory=True)

    class EndpointHealth(devices.EndpointHealth):

        @property            
        def connectivity(self):
            return 'OK' if self.nativeObject['state']['reachable'] else "UNREACHABLE"

    class PowerController(devices.PowerController):

        @property            
        def powerState(self):
            if not self.nativeObject['state']['reachable']:
                return "OFF"
            return "ON" if self.nativeObject['state']['on'] else "OFF"

        async def TurnOn(self, correlationToken='', **kwargs):
            try:
                response=await self.adapter.setHueLight(self.deviceid, { 'on':True })
                await self.adapter.dataset.ingest(response)
                return self.device.Response(correlationToken)
            except:
                self.adapter.log.error('!! Error during TurnOn', exc_info=True)
        
        async def TurnOff(self, correlationToken='', **kwargs):

            try:
                response=await self.adapter.setHueLight(self.deviceid, { 'on':False })
                await self.adapter.dataset.ingest(response)
                return self.device.Response(correlationToken)
            except:
                self.adapter.log.error('!! Error during TurnOff', exc_info=True)
                
    class BrightnessController(devices.BrightnessController):

        @property            
        def brightness(self):
            return int((float(self.nativeObject['state']['bri'])/254)*100)
        
        async def SetBrightness(self, payload, correlationToken='', **kwargs):

            try:
                if int(payload['brightness'])>0:
                    nativeCommand={'on': True, 'bri': self.adapter.percentage(int(payload['brightness']), 255) }
                else:
                    nativeCommand= {'on': False }
                response=await self.adapter.setHueLight(self.deviceid, nativeCommand)
                await self.adapter.dataset.ingest(response)
                return self.device.Response(correlationToken)
 
            except:
                self.adapter.log.error('!! Error setting brightness', exc_info=True)

    class ColorController(devices.ColorController):

        @property            
        def color(self):
            # The real values are based on this {"bri":int(hsbdata['brightness']*255), "sat":int(hsbdata['saturation']*255), "hue":int((hsbdata['hue']/360)*65536)}
            return {"hue":round((int(self.nativeObject['state']["hue"])/65536)*360,1), "saturation":round(int(self.nativeObject['state']["sat"])/255,4), "brightness":round(int(self.nativeObject['state']["bri"])/255,4) }

        async def SetColor(self, payload, correlationToken='', **kwargs):
 
            try:
                if type(payload['color']) is not dict:
                    payloadColor=json.loads(payload['color'])
                else:
                    payloadColor=payload['color']
                nativeCommand={'on':True, 'transitiontime': 1, "bri": int(float(payloadColor['brightness'])*255), "sat": int(float(payloadColor['saturation'])*255), "hue": int((float(payloadColor['hue'])/360)*65536) }
                response=await self.adapter.setHueLight(self.deviceid, nativeCommand)
                await self.adapter.dataset.ingest(response)
                return self.device.Response(correlationToken)

            except:
                self.adapter.log.error('!! Error setting color', exc_info=True)

    class ColorTemperatureController(devices.ColorTemperatureController):

        @property            
        def colorTemperatureInKelvin(self):
            # Hue CT value uses "mireds" which is roughly 1,000,000/ct = Kelvin
            # Here we are reducing the range and then multiplying to round into hundreds
            return int(10000/float(self.nativeObject['state']['ct']))*100

        async def SetColorTemperature(self, payload, correlationToken='', **kwargs):
 
            try:
                # back from CtiK to Mireds for Alexa>Hue
                nativeCommand={'ct' : int(1000000/float(payload['colorTemperatureInKelvin'])) }               
                response=await self.adapter.setHueLight(self.deviceid, nativeCommand)
                await self.adapter.dataset.ingest(response)
                return self.device.Response(correlationToken)
            except:
                self.adapter.log.error('!! Error setting color temperature', exc_info=True)

    #-----
    class GroupEndpointHealth(EndpointHealth):

        @property            
        def connectivity(self):
            return 'OK'

    class GroupPowerController(PowerController):

        @property            
        def powerState(self):
            if not self.nativeObject['state']['any_on']:
                return "OFF"
            return "ON"
            
        async def TurnOn(self, correlationToken='', **kwargs):
            try:
                response=await self.adapter.setHueGroup(self.deviceid, { 'on':True })
                #await self.adapter.dataset.ingest(response)
                return self.device.Response(correlationToken)
            except:
                self.adapter.log.error('!! Error during TurnOn', exc_info=True)
        
        async def TurnOff(self, correlationToken='', **kwargs):

            try:
                response=await self.adapter.setHueGroup(self.deviceid, { 'on':False })
                #await self.adapter.dataset.ingest(response)
                return self.device.Response(correlationToken)
            except:
                self.adapter.log.error('!! Error during TurnOff', exc_info=True)
                
    class GroupBrightnessController(BrightnessController):

        @property            
        def brightness(self):
            return 50

    class GroupColorController(ColorController):

        @property            
        def color(self):
            # The real values are based on this {"bri":int(hsbdata['brightness']*255), "sat":int(hsbdata['saturation']*255), "hue":int((hsbdata['hue']/360)*65536)}
            return {"hue":100, "saturation":100, "brightness":100 }

        async def SetColor(self, payload, correlationToken='', **kwargs):
 
            try:
                if type(payload['color']) is not dict:
                    payloadColor=json.loads(payload['color'])
                else:
                    payloadColor=payload['color']
                nativeCommand={'on':True, 'transitiontime': 1, "bri": int(float(payloadColor['brightness'])*255), "sat": int(float(payloadColor['saturation'])*255), "hue": int((float(payloadColor['hue'])/360)*65536) }
                response=await self.adapter.setHueGroup(self.deviceid, nativeCommand)
                #await self.adapter.dataset.ingest(response, mergeReplace=True)
                return self.device.Response(correlationToken)

            except:
                self.adapter.log.error('!! Error setting color', exc_info=True)


    class GroupColorTemperatureController(ColorTemperatureController):

        @property            
        def colorTemperatureInKelvin(self):
            # Hue CT value uses "mireds" which is roughly 1,000,000/ct = Kelvin
            # Here we are reducing the range and then multiplying to round into hundreds
            return 5000
    
    
    class adapterProcess(adapterbase):
        
        def __init__(self, log=None, loop=None, dataset=None, notify=None, request=None, config=None, **kwargs):
            self.hueColor=colorConverter()
            self.dataset=dataset
            self.dataset.nativeDevices['lights']={}
            self.dataset.nativeDevices['groups']={}
            self.definitions=definitions.Definitions
            self.log=log
            self.config=config
            self.notify=notify
            self.loop=loop
            self.inuse=False

        async def pre_activate(self):
            self.log.info('.. Starting hue')
            self.bridge = Bridge(self.config.hue_bridge_address, self.config.hue_user)
            await self.getHueBridgeData('all')
            
        async def start(self):
            self.polling_task = asyncio.create_task(self.pollHueBridge())
            
        async def pollHueBridge(self):
            self.log.info(".. polling loop every %s seconds for bridge data" % self.config.poll_time)
            while True:
                try:
                    #self.log.info("Polling bridge data")
                    await self.getHueBridgeData('all')
                except:
                    self.log.error('Error fetching Hue Bridge Data', exc_info=True)
                
                await asyncio.sleep(self.config.poll_time)
                    

        async def getHueBridgeData(self, category='all', device=None):
            
            try:
                #self.log.info('Polling %s' % category)
                reqstart=datetime.datetime.now()
                changes=[]
                if category=="all":
                    alldata=await self.getHueAll()
                    if alldata:
                        changes=await self.dataset.ingest({'lights':alldata['lights'], 'sensors':alldata['sensors'], 'groups':alldata['groups']}, mergeReplace=True)

                elif category=="lights":
                    changes=await self.dataset.ingest({'lights': await self.getHueLights(device)}, mergeReplace=True)
                elif category=="groups":
                    await self.dataset.ingest({'groups': await self.getHueGroups()}, mergeReplace=True)
                elif category=="sensors":
                    await self.dataset.ingest({'sensors':await self.getHueSensors()}, mergeReplace=True)
                reqend=datetime.datetime.now()  
                #self.log.info('process time: %s' % (reqend-reqstart).total_seconds())
                return changes

            except:
                self.log.error('Error fetching Hue Bridge Data', exc_info=True)
                return {}


        def percentage(self, percent, whole):
            return int((percent * whole) / 100.0)


        def get(self, category, item):
            try:
                if category=='lights':
                    return self.getHueLights(item)
            except:
                self.log.error('Error handing data request: %s.%s' % (category, item))
                return {}


        async def getHueLights(self, light=None):
            
            try:
                if light:
                    try:
                        return { light : await self.bridge.lights[light]() }
                    except:
                        for cachelight in self.dataset.nativeDevices['lights']:
                            try:
                                if self.dataset.nativeDevices['lights'][cachelight]['name']==light:
                                    return self.bridge.lights[cachelight]()
                            except:
                                pass
                        self.log.info('Could not find light: %s' % light)
                        return None
                else:
                    lightstart=datetime.datetime.now()
                    light_data=await self.bridge.lights()
                    lightend=datetime.datetime.now()
                    self.log.info('.. time to get light data: %s' % (lightend-lightstart).total_seconds())
                    return light_data
            except aiohttp.client_exceptions.ClientConnectorError:
                self.log.error("Error getting hue config. (Failed to connect to hub)")
                
            except:
                self.log.error("Error getting hue config.",exc_info=True)
                return {}

        async def getHueAll(self):
            try:
                allstart=datetime.datetime.now()
                all_data=await self.bridge()
                #self.log.info('.. data size: %s' % len(json.dumps(all_data)))

                allend=datetime.datetime.now()
                if (allend-allstart).total_seconds()>0.5:
                    self.log.info('.. long time to get all data: %s' % (allend-allstart).total_seconds())
                #self.log.info('.. time to get all data: %s' % (allend-allstart).total_seconds())
                return all_data
            except aiohttp.client_exceptions.ClientConnectorError:
                self.log.error("!! Error connecting to hue bridge. (Client Connector Error)")

            except aiohttp.client_exceptions.ServerDisconnectedError:
                self.log.error("!! Error - hue bridge disconnected while retrieving data. (Server Disconnected Error)")

            except aiohttp.client_exceptions.ClientOSError:
                self.log.error("!! Error - hue bridge connection failure - reset by peer.")
            except concurrent.futures._base.TimeoutError:
                self.log.error("!! Error connecting to hue bridge. (Timeout Error)")
            except:
                self.log.error("!! Error getting hue data.",exc_info=True)
            return {}

        async def getHueGroups(self):
            try:
                return await self.bridge.groups()
            except:
                self.log.error("Error getting hue config.",exc_info=True)
                return {}

                
        async def getHueSensors(self):
            try:
                return await self.bridge.sensors()
            except:
                self.log.error("Error getting hue config.",exc_info=True)
                return {}


        async def getHueConfig(self):
            try:
                bridgeconfig=await self.bridge.config()
                # removing items that would spam updates
                del bridgeconfig['whitelist']
                del bridgeconfig['UTC']
                del bridgeconfig['localtime']
                
                return bridgeconfig
            except:
                self.log.error("Error getting hue config.",exc_info=True)
                return {}

        # Set Commands

        async def setHueLight(self, light, data):
        
            try:
                while self.inuse:
                    try:
                        await asyncio.sleep(.2)
                    except concurrent.futures._base.CancelledError:
                        pass
                    
                if light not in self.dataset.nativeDevices['lights']:
                    for alight in self.dataset.nativeDevices['lights']:
                        if self.dataset.nativeDevices['lights'][alight]['name']==light:
                            light=alight
                            break
                        
                self.inuse=True
                response=await self.bridge.lights[int(light)].state(**data)
                #self.log.info('response: %s' % response)
                state={}
                for item in response:
                    if 'success' in item:
                        for successitem in item['success']:
                            prop=successitem.split('/')[4]
                            if prop!='transitiontime':
                                state[prop]=item['success'][successitem]
                
                result={'lights': { light : {'state':state }}}
                #result=await self.getHueBridgeData(category='lights', device=int(light))

                self.inuse=False
                return result

            except:
                self.log.info("Error setting hue light: %s %s" % (light, data),exc_info=True)
                self.inuse=False
                return {}

        async def setHueGroup(self, group, data):
        
            try:
                while self.inuse:
                    try:
                        await asyncio.sleep(.1)
                    except concurrent.futures._base.CancelledError:
                        pass
                        
                    
                if group in self.dataset.nativeDevices['groups']:
                    data['transitiontime']=5
                    self.inuse=True
                    response=await self.bridge.groups[int(group)].action(**data)
                    state={}
                    for item in response:
                        if 'success' in item:
                            for successitem in item['success']:
                                prop=successitem.split('/')[4]
                                if prop!='transitiontime':
                                    state[prop]=item['success'][successitem]
                    
                    #result={'lights': { light : {'state':state }}}
                    result=await self.getHueBridgeData(category='lights')
                    self.inuse=False
                return result

            except:
                self.log.info("Error setting hue light: %s %s" % (group, data),exc_info=True)
                self.inuse=False
                return {}


        # Utility Functions

        async def createHueGroup(self,groupname,lights):
            try:
                huedata=await self.bridge.groups(**{"name":groupname, "lights":lights, "http_method":"post"})
            except:
                self.log.error("Error creating group.",exc_info=True)

        async def deleteHueGroup(self,groupname):
            try:
                huedata=await self.bridge.groups[groupname](**{"http_method":"delete"})
            except:
                self.log.error("Error deleting group.",exc_info=True)
                
        # Adapter Overlays that will be called from dataset
        async def addSmartDevice(self, path):
            
            try:
                device_id=path.split("/")[2]
                device_type=path.split("/")[1]
                endpointId="%s:%s:%s" % ("hue", device_type, device_id)
                if endpointId not in self.dataset.localDevices:  # localDevices/friendlyNam   
                    if device_type=="lights":
                        return await self.addSmartLight(device_id)
                            
                    if device_type=="groups":
                        return await self.addNativeGroup(device_id)

            except:
                self.log.error('Error defining smart device', exc_info=True)
                return False

        async def addSmartLight(self, deviceid):
            
            try:
                nativeObject=self.dataset.nativeDevices['lights'][deviceid]
                device=devices.alexaDevice('hue/lights/%s' % deviceid, nativeObject['name'], displayCategories=['LIGHT'], manufacturerName="Philips Hue", modelName=nativeObject['type'], adapter=self)
                device.PowerController=hue.PowerController(device=device)
                device.EndpointHealth=hue.EndpointHealth(device=device)
                device.StateController=devices.StateController(device=device)
                if nativeObject["type"] in ["Color temperature light", "Extended color light", "Color light"]:
                    device.BrightnessController=hue.BrightnessController(device=device)
                if nativeObject["type"] in ["Color temperature light", "Extended color light"]:
                    device.ColorTemperatureController=hue.ColorTemperatureController(device=device)
                if nativeObject["type"] in ["Extended color light", "Color light"]:
                    device.ColorController=hue.ColorController(device=device)
                
                # return self.dataset.newaddDevice(device) older friendlyname based localDevices
                return self.dataset.add_device(device)
            except:
                self.log.error('Error in AddSmartLight %s' % deviceid, exc_info=True)

        async def addNativeGroup(self, deviceid):
            
            try:
                nativeObject=self.dataset.nativeDevices['groups'][deviceid]
                device=devices.alexaDevice('hue/groups/%s' % deviceid, nativeObject['name'], displayCategories=['GROUP'], manufacturerName="Philips Hue", modelName=nativeObject['type'], hidden=True, adapter=self)
                device.PowerController=hue.GroupPowerController(device=device)
                device.EndpointHealth=hue.GroupEndpointHealth(device=device)
                device.BrightnessController=hue.GroupBrightnessController(device=device)
                device.ColorTemperatureController=hue.GroupColorTemperatureController(device=device)
                device.ColorController=hue.GroupColorController(device=device)

                return self.dataset.add_device(device)
            except:
                self.log.error('Error in AddSmartLight %s' % deviceid, exc_info=True)

                
        async def virtual_group_handler(self, controllers, devicelist):
            try:
                for group in self.dataset.nativeDevices['groups']:
                    groupmembers=[]
                    for link in self.dataset.nativeDevices['groups'][group]['lights']:
                        groupmembers.append("hue:lights:"+link)
                    if Counter(devicelist) == Counter(groupmembers):  
                        response={ "id": "hue:groups:"+group, "name": self.dataset.nativeDevices['groups'][group]['name'], "members":groupmembers }
                        #self.log.info('<< nativegroup response for %s: %s' % (devicelist,response ))
                        return response
            except:
                self.log.error('!! error trying to get virtual group: %s' % devicelist, exc_info=True)
                
            return {}                

if __name__ == '__main__':
    adapter=hue(name='hue')
    adapter.start()
