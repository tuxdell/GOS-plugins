# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
import ServiceReference
from enigma import iPlayableService, eTimer, eServiceCenter, iServiceInformation, eServiceReference, evfd, eDVBVolumecontrol
import time
from Components.ServiceEventTracker import ServiceEventTracker, InfoBarBase
from Tools.HardwareInfo import HardwareInfo
#from Components.config import config
from Screens.Screen import Screen
from Components.config import *
from Components.ConfigList import ConfigList, ConfigListScreen
from Components.ActionMap import ActionMap
from Components.Label import Label

from Components.Console import Console
import Screens.Standby

FirstTimeRun = True

def standbyCounterChanged(configElement):
    if HardwareInfo().get_device_name() == 'spark7162':
        Console().ePopen('/bin/fp_control -i 46 0') #akcja przez evfd generuje GS przy wychodzeniu
    evfd.getInstance().vfd_write_string("                ")
    print "standbyCounterChanged"

class VFDIcons:
    blank=0
    number=1
    name=2
    program=3
    
    def __init__(self, session):
        # Save Session&Servicelist, Create Timer, Init Services
        self.VFDConsole = Console()
        self.vfdshow = self.name
        self.textLenght = 16
        self.showicons = False
        self.standbyCounter = 0
        self.model = HardwareInfo().get_device_name()
        print "[VFDIcons:%s]" % self.model
        
        config.misc.standbyCounter.addNotifier(standbyCounterChanged, initial_call = False)
        
        self.session = session
        self.service = None
        self.onClose = [ ]
        self.LastVFDtext = ""
        self.LastVFDupdateTime = time.time()
        self.initialVFDupdates = 3

        if self.model == 'spark':
            self.textLenght = 4
            self.showicons = False
            self.__event_tracker = ServiceEventTracker(screen=self,eventmap=
                {
                    iPlayableService.evUpdatedInfo: self.__evUpdatedInfo,
                })
        
            session.nav.record_event.append(self.gotRecordEvent)
        elif self.model == 'spark7162':
            self.textLenght = 8
            self.showicons = True
            self.VFDConsole.ePopen('/bin/fp_control -i 46 0') #akcja przez evfd generuje GS przy wychodzeniu
            self.__event_tracker = ServiceEventTracker(screen=self,eventmap=
                {
                    iPlayableService.evUpdatedInfo: self.__evUpdatedInfo,
                    iPlayableService.evUpdatedEventInfo: self.__evUpdatedEventInfo,
                    iPlayableService.evVideoSizeChanged: self.__evVideoSizeChanged,
                    iPlayableService.evSeekableStatusChanged: self.__evSeekableStatusChanged,
                    iPlayableService.evStart: self.__evStart,
                })
        
            session.nav.record_event.append(self.gotRecordEvent)
        elif self.model == 'arivalink200':
            self.textLenght = 16
            self.showicons = False
            self.__event_tracker = ServiceEventTracker(screen=self,eventmap=
                {
                    iPlayableService.evUpdatedInfo: self.__evUpdatedInfo,
                })
          
        self.mp3Available = False
        self.dolbyAvailable = False
        self.currentVolume = 0
        self.LastVolume = 0
        self.chlist = []
        self.getList()
        
    def __evStart(self):
        print "[VFDIcons:__evStart]"
        self.__evSeekableStatusChanged()    
        
    def __evUpdatedInfo(self):
        global FirstTimeRun
        if FirstTimeRun is True:
            FirstTimeRun = False
            self.VFDConsole.ePopen('/bin/fp_control -dt 1') #nie musimy sprawdzac tunera bo fp_control sam wie co robic :)

        print "[VFDIcons:__evUpdatedInfo]"
        try:
            if config.plugins.VFD.shows.value == 'name':
                self.vfdshow = self.name
            elif config.plugins.VFD.shows.value == 'number':
                self.vfdshow = self.number
            elif config.plugins.VFD.shows.value == 'program':
                self.vfdshow = self.program
            elif config.plugins.VFD.shows.value == 'blank':
                self.vfdshow = self.blank
            else:
                self.vfdshow = self.name
        except:
            self.vfdshow = self.name
        self.checkAudioTracks()
        #jesli vfd nie odswierzony w godzine, to odswierzmy go tak w razie czego
        if time.time() - self.LastVFDupdateTime >= 3600:
            self.LastVFDupdateTime = time.time()
            self.LastVFDtext = ""
        #jesli licznik uspien sie zmienil, to zakladamy, ze nastapilo budzenie, odswierzmy wiec vfd
        if config.misc.standbyCounter.value != self.standbyCounter :
            self.standbyCounter = config.misc.standbyCounter.value
            self.LastVFDtext = ""
        #wyswietlamy nic/numer/nazwe kanalu/tytul programu
        if self.vfdshow == self.blank:
            evfd.getInstance().vfd_write_string("                ")
        elif self.vfdshow == self.number:
            self.writeChannelNumber()
        else:
            self.writeChannelName()
        if self.initialVFDupdates > 0:
                self.LastVFDtext = ""
                self.initialVFDupdates -= 1
        #evfd.getInstance().vfd_write_string("v-%i" % self.currentVolume)
        if self.showicons == True and config.plugins.VFD.icons.value != 'nothing':
            print "config.plugins.VFD.icons.value=%s" % config.plugins.VFD.icons.value
            self.showCrypted()
            self.showDolby()
            self.showMp3()

    def getList(self):
        serviceHandler = eServiceCenter.getInstance()
        services = serviceHandler.list(eServiceReference('1:7:1:0:0:0:0:0:0:0:(type == 1) || (type == 17) || (type == 195) || (type == 25) FROM BOUQUET "bouquets.tv" ORDER BY bouquet'))
        bouquets = services and services.getContent("SN", True)
        for bouquet in bouquets:
            services = serviceHandler.list(eServiceReference(bouquet[0]))
            channels = services and services.getContent("SN", True)
            for channel in channels:
                if not channel[0].startswith("1:64:"):
                    self.chlist.append(channel[1].replace('\xc2\x86', '').replace('\xc2\x87', ''))
                    #print "[VFD] channels: " + channel[1].replace('\xc2\x86', '').replace('\xc2\x87', '')

    def writeChannelNumber(self):
        #print "[writeChannelNumber]"
        servicenumber = "0000"
        servicename = ""
        self.service = self.session.nav.getCurrentlyPlayingServiceReference()
        if not self.service is None:
            service = self.service.toCompareString()
            servicename = ServiceReference.ServiceReference(service).getServiceName().replace('\xc2\x87', '').replace('\xc2\x86', '').ljust(16)
            subservice = self.service.toString().split("::")
            if subservice[0].count(':') == 9:
                servicename = subservice[1].replace('\xc2\x87', '').replace('\xc3\x9f', 'ss').replace('\xc2\x86', '').ljust(16)
            else:
                servicename=servicename
        servicename=servicename.strip()
        if servicename in self.chlist:
            for idx in range(1, len(self.chlist)):
                if servicename == self.chlist[idx-1]:
                    servicenumber = str(idx)
                    break
        else:
            servicenumber = '----'
        #print "[VFD] channelname: " + servicename
        if len(servicenumber) == 1:
            servicenumber = '000' + servicenumber
        elif len(servicenumber) == 2:
            servicenumber = '00' + servicenumber
        elif len(servicenumber) == 3:
            servicenumber = '0' + servicenumber
        
        if self.LastVFDtext != servicenumber:
            evfd.getInstance().vfd_write_string(servicenumber)
            self.LastVFDtext = servicenumber

    def writeChannelName(self):
        #print "[writeChannelName]"
        servicename = ""
        currPlay = self.session.nav.getCurrentService()
        if currPlay != None and self.mp3Available:
            # show the MP3 tag
            servicename = currPlay.info().getInfoString(iServiceInformation.sTagTitle)
        else:
            # show the service name
            self.service = self.session.nav.getCurrentlyPlayingServiceReference()
            if not self.service is None:
                service = self.service.toCompareString()
                servicename = ServiceReference.ServiceReference(service).getServiceName().replace('\xc2\x87', '').replace('\xc2\x86', '').ljust(16)
                subservice = self.service.toString().split("::")
                if subservice[0].count(':') == 9:
                    servicename = subservice[1].replace('\xc2\x87', '').replace('\xc3\x9f', 'ss').replace('\xc2\x86', '').ljust(16)
                else:
                    servicename=servicename
            else:
                print "no Service found"
	#pozbywamy sie polskich znakow - to MUSI zostac przeniesione do sterownika VFD
        servicename = servicename.replace('\xc4\x84', 'A').replace('\xc4\x85', 'a').replace('\xc4\x86', 'C').replace('\xc4\x87', 'C')
        servicename = servicename.replace('\xc4\x98', 'E').replace('\xc4\x99', 'e').replace('\xc5\x81', 'L').replace('\xc5\x82', 'l')
        servicename = servicename.replace('\xc5\x83', 'N').replace('\xc5\x84', 'n').replace('\xc5\x9a', 'S').replace('\xc5\x9b', 's')
        servicename = servicename.replace('\xc5\xb9', 'Z').replace('\xc5\xba', 'z').replace('\xc5\xbb', 'Z').replace('\xc5\xbc', 'z')
        servicename = servicename.replace('\xc3\x93', 'O').replace('\xc3\xb3', 'o')
        if self.model == 'spark':
            servicename=servicename.replace(" ", "") #oszczedzamy jeden znak
            servicename=servicename.replace("e", "E")
            servicename=servicename.replace("o", "O")
            servicename=servicename.replace("l", "L")
            #print "[VFD-Icons] display text:", servicename[0:self.textLenght]
        elif self.model == 'spark7162':
            servicename=servicename.replace("+", "")
            #print "[VFD-Icons] display text:", servicename[0:self.textLenght]

        #finalnie wyswietlamy tekst
        if self.LastVFDtext != servicename[0:self.textLenght]: #zapobiegamy mryganiu wyswietlacza
            evfd.getInstance().vfd_write_string(servicename[0:self.textLenght])
            self.LastVFDtext = servicename[0:self.textLenght]
        return 1

    def showCrypted(self):
        if config.plugins.VFD.icons.value == 'all' :
            print "[showCrypted]"
            service=self.session.nav.getCurrentService()
            if service is not None:
                info=service.info()
                crypted = info and info.getInfo(iServiceInformation.sIsCrypted) or -1
                if crypted == 1 : #set crypt symbol
                    evfd.getInstance().vfd_set_icon(0x13,1)
                else:
                    evfd.getInstance().vfd_set_icon(0x13,0)
    
    def checkAudioTracks(self):
        self.dolbyAvailable = False
        self.mp3Available = False
        self.currentVolume = 0
        service=self.session.nav.getCurrentService()
        if service is not None:
            audio = service.audioTracks()
            if audio:
                n = audio.getNumberOfTracks()
                selectedAudio = audio.getCurrentTrack()
                for x in range(n):
                    i = audio.getTrackInfo(x)
                    description = i.getDescription();
                    if description.find("MP3") != -1:
                        self.mp3Available = True
                    if description.find("AC3") != -1 or description.find("DTS") != -1:
                        self.dolbyAvailable = True
    
    def showDolby(self):
        if config.plugins.VFD.icons.value == 'all' :
            print "[showDolby]"
            if self.dolbyAvailable:
                evfd.getInstance().vfd_set_icon(0x17,1)
            else:
                evfd.getInstance().vfd_set_icon(0x17,0)
        
    def showMp3(self):
        if config.plugins.VFD.icons.value == 'all' :
            print "[showMp3]"
            if self.mp3Available:
                evfd.getInstance().vfd_set_icon(0x15,1)
            else:
                evfd.getInstance().vfd_set_icon(0x15,0)
        
    def __evUpdatedEventInfo(self):
        print "[__evUpdatedEventInfo]"
        
    def getSeekState(self):
        service = self.session.nav.getCurrentService()
        if service is None:
            return False
        seek = service.seek()
        if seek is None:
            return False
        return seek.isCurrentlySeekable()
        
    def __evSeekableStatusChanged(self):
        if config.plugins.VFD.icons.value == 'all' :
            print "[__evSeekableStatusChanged]"
            if self.getSeekState():
                evfd.getInstance().vfd_set_icon(0x1A,1)
            else:
                evfd.getInstance().vfd_set_icon(0x1A,0)
        
    def __evVideoSizeChanged(self):
        if config.plugins.VFD.icons.value == 'all' :
            print "[__evVideoSizeChanged]"
            service=self.session.nav.getCurrentService()
            if service is not None:
                info=service.info()
                height = info and info.getInfo(iServiceInformation.sVideoHeight) or -1
                if height > 576 : #set HD symbol
                    evfd.getInstance().vfd_set_icon(0x11,1)
                else:
                    evfd.getInstance().vfd_set_icon(0x11,0)
        
    def gotRecordEvent(self, service, event):
        recs = self.session.nav.getRecordings()
        nrecs = len(recs)
        if nrecs > 0: #set rec symbol
            #print "[gotRecordEvent] record start"
            if config.plugins.VFD.icons.value != 'nothing' :
                if self.model == 'spark':
                    self.VFDConsole.ePopen('/bin/fp_control -i 0 1')
                else:
                    evfd.getInstance().vfd_set_icon(0x1e,1,1)
        else:
            #print "[gotRecordEvent] record stop"
            if self.model == 'spark':
                self.VFDConsole.ePopen('/bin/fp_control -i 0 0')
            else:
                evfd.getInstance().vfd_set_icon(0x1e,0,1)

VFDIconsInstance = None

########################### DEFINICJA WTYCZKI ################################################

def main(session, **kwargs):
    # Create Instance if none present, show Dialog afterwards
    global VFDIconsInstance
    if VFDIconsInstance is None:
        VFDIconsInstance = VFDIcons(session)

def startSetup(menuid, **kwargs):
    if menuid != "system":
        return [ ]
    return [(_("VFD settings"), mainsetup, "VFDconfig", None)]

def mainsetup(session,**kwargs):
    session.open(VFDSetupMenu)

def Plugins(**kwargs):
     return [ PluginDescriptor(name="VFDIcons", description="Icons in VFD", where = PluginDescriptor.WHERE_SESSIONSTART, fnc=main ),
            PluginDescriptor(name=_("VFD Config"), description=_("VFD settings configurator"), where = PluginDescriptor.WHERE_MENU, fnc=startSetup)
            ]

########################### KONFIGURATOR ################################################
config.plugins.VFD = ConfigSubsection()
config.plugins.VFD.shows =  ConfigSelection(default = "name", choices = [("name", _("Channel name")), ("number", _("Channel number")), ("blank", _("nothing"))])
if HardwareInfo().get_device_name() == 'arivalink200':
    config.plugins.VFD.icons =  ConfigSelection(default = "nothing", choices = [("nothing", _("nothing"))])
else:
    config.plugins.VFD.icons =  ConfigSelection(default = "rec", choices = [("rec", _("REC only")), ("all", _("All")), ("nothing", _("nothing"))])

class VFDSetupMenu(Screen, ConfigListScreen):

    skin = """
    <screen name="VFDSetupMenu" position="center,center" size="540,240" title="VFD" backgroundColor="#31000000" >

            <widget name="config" position="10,10" size="520,195" zPosition="1" transparent="0" backgroundColor="#31000000" scrollbarMode="showOnDemand" />
            <widget name="key_green" position="0,205" zPosition="2" size="250,35" valign="center" halign="center" font="Regular;22" transparent="1" foregroundColor="green" />
            <widget name="key_red" position="250,205" zPosition="2" size="250,35" valign="center" halign="center" font="Regular;22" transparent="1" foregroundColor="red" />

    </screen>"""
    
    def __init__(self, session):
        Screen.__init__(self, session)

        self.onChangedEntry = [ ]
        self.list = [ ]
        ConfigListScreen.__init__(self, self.list, session = session, on_change = self.changedEntry)
        #self.setup_title = _("VFD settings configurator")
        self["actions"] = ActionMap(["SetupActions", "ColorActions"],
            {
                "cancel": self.keyCancel,
                "green": self.keySave,
                "ok": self.keySave,
                "red": self.keyCancel,
            }, -2)

        self["key_green"] = Label(_("Save"))
        self["key_red"] = Label(_("Cancel"))

        #self.runSetup()
        self.onLayoutFinish.append(self.layoutFinished)

    def layoutFinished(self):
        self.setTitle(_("VFD settings configurator"))
        self.runSetup()
        
    def runSetup(self):

        self.list.append(getConfigListEntry(_("VFD displays:"), config.plugins.VFD.shows))
        if HardwareInfo().get_device_name() != 'arivalink200':
            self.list.append(getConfigListEntry(_("Displayed icons on VFD:"), config.plugins.VFD.icons))
        
        self["config"].list = self.list
        self["config"].setList(self.list)

    def keySave(self):
        for x in self["config"].list:
            x[1].save()
        configfile.save()
        self.close()

    def keyCancel(self):
        for x in self["config"].list:
            x[1].cancel()
        self.close()
        
    def keyLeft(self):
        ConfigListScreen.keyLeft(self)
        #if self["config"].getCurrent()[1] == [config.plugins.StandbyLogo.enable , config.plugins.joozekLiveTV.enable, config.hdmicec.volume_forwarding ]:
        #    self.runSetup()

    def keyRight(self):
        ConfigListScreen.keyRight(self)

    def changedEntry(self):
        for x in self.onChangedEntry:
            x()
