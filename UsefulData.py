import sys
import re
import pickle
import os
import configparser
import threading
import time

import ac
import acsys

import ctypes
from ctypes import wintypes

from sim_info_lib.sim_info import info
from sound_player import SoundPlayer

# TODO Fix appname
APP_NAME = "UsefulData"

# FOLDER PATHS
COMPOUNDSPATH = "apps/python/%s/compounds/" % APP_NAME

# ERS MODES TEXT
ERS_MODES = ['Charging', 'Low', 'High', 'Overtake', 'Speed', 'Hotlap']
# ERS COLORS [green to red gradient]
ERS_COLORS = [(.47,1.,.2), (.73,1.,.2), (1,1,.2), (1.,.7,.1), (1.,.33,0), (1.,.0,.0)]
DRS_GAP = 1.0
DRS_STARTS_ON_LAP = 1

#DRS COLORS
DRS_GOOD = (0.25, 1.00, 0.10, 1)
DRS_BAD = (1.,.0,.0, 1)
DRS_AVAILABLE = (1., 1., 0.1, 1)
DRS_POSSIBLE = (0.86, 0.86, 0.86, 1)

audio = ('apps/python/%s/beep.wav' % APP_NAME)
sound_player = SoundPlayer(audio)

#timers
timer0 = 0
timer1 = 0

#tyres stuff
tyreCompoundShort = ""
tyreCompoundCleaned = ""
previousTyreCompoundValue = 0
minimumOptimalTemperature = 0
maximumOptimalTemperature = 0
idealPressureFront = 0
idealPressureRear = 0
tyreCompoundValue = 0
tyreWearValue = [0] * 4
tyreTemperatureValue = [0] * 4
tyreTemperatureValueI = [0] * 4
tyreTemperatureValueM = [0] * 4
tyreTemperatureValueO = [0] * 4
tyrePressureValue = [0] * 4
tyrePracticalTemperatureValue = [0] * 4

#fuel
fuelAmountValue = 0
fuelStartValue = 0
relevantLapsNumber = 0
fuelSpentValue = 0
fuelPerLapValue = 0

carWasInPit = 0
currentLapValue = 0

previousLapValue = 0
lapValue = 0

#drs stuff
drsData = None      # Definitions of DRS zones.
lastList = []  # list of driver data from previous update
totalDrivers = 0
trackLength = 0
lastTime = 0
lastDRSLevel = 0
drsValid = False
inDrsZone = False
drsPenAwarded = False
totalPenalty = 0
soundPlaying = False

#other variables
temperatureTransitionRange = 20.0

# labels and ui data collected
tyreLabels = [None] * 4
tyrePressureLabels = [None] * 4
drsLabel, ersModeLabel, fuelLabel, drsPenaltyLabel = None, None, None, None
compounds, modCompounds  = None, None
carValue, trackConfigValue, trackValue = None, None, None
# filePersonalBest = None

def acMain(ac_version):
    global tyreLabels, tyrePressureLabels
    global drsLabel, ersModeLabel, fuelLabel, drsPenaltyLabel

    global drsData, totalDrivers, trackLength

    global carValue, trackConfigValue, trackValue

    global compounds, modCompounds

    carValue = ac.getCarName(0)
    trackValue = ac.getTrackName(0)
    trackConfigValue = ac.getTrackConfiguration(0)

    drsData = drs()
    totalDrivers = ac.getCarsCount()
    trackLength = getTrackLength()

    compounds = configparser.ConfigParser()
    compounds.read(COMPOUNDSPATH + "compounds.ini")
    modCompounds = configparser.ConfigParser()
    modCompounds.read(COMPOUNDSPATH + carValue + ".ini")

    ac.initFont(0, "Roboto", 1, 1)

    appWindow = ac.newApp(APP_NAME)
    ac.setTitle(appWindow, "")
    ac.drawBorder(appWindow, 0)
    ac.setIconPosition(appWindow, 0, -10000)
    ac.setSize(appWindow, 300, 60)
    ac.setBackgroundOpacity(appWindow, 0.2)

    # =================================================================================================================
    #                                             TYRE LABELS
    # =================================================================================================================

    tyreLabelFL = ac.addLabel(appWindow, "TFL")
    tyreLabelFR = ac.addLabel(appWindow, "TFR")
    tyreLabelRL = ac.addLabel(appWindow, "TRL")
    tyreLabelRR = ac.addLabel(appWindow, "TRR")
    tyreLabels = [tyreLabelFL, tyreLabelFR, tyreLabelRL, tyreLabelRR]
    for label in tyreLabels:
        ac.setFontSize(label, 15)
        ac.setFontColor(label, 0, 0, 0, 1)
        ac.setFontAlignment(label, "center")
        ac.setSize(label, 23, 25)

    tyrePressureLabelFL = ac.addLabel(appWindow, "PFL")
    tyrePressureLabelFR = ac.addLabel(appWindow, "PFR")
    tyrePressureLabelRL = ac.addLabel(appWindow, "PRL")
    tyrePressureLabelRR = ac.addLabel(appWindow, "PRR")
    tyrePressureLabels = [tyrePressureLabelFL, tyrePressureLabelFR, tyrePressureLabelRL, tyrePressureLabelRR]
    for label in tyrePressureLabels:
        ac.setFontSize(label, 15)
        ac.setFontColor(label, 0.86, 0.86, 0.86, 1)

    ac.setFontAlignment(tyrePressureLabels[0], "left")
    ac.setFontAlignment(tyrePressureLabels[1], "right")
    ac.setFontAlignment(tyrePressureLabels[2], "left")
    ac.setFontAlignment(tyrePressureLabels[3], "right")

    #position all the labels
    tlpx = 60
    tlpy = 0

    ac.setPosition(tyreLabels[0], tlpx + 30, tlpy + 0)
    ac.setPosition(tyreLabels[1], tlpx + 57, tlpy + 0)
    ac.setPosition(tyreLabels[2], tlpx + 30, tlpy + 28)
    ac.setPosition(tyreLabels[3], tlpx + 57, tlpy + 28)

    ac.setPosition(tyrePressureLabels[0], tlpx, tlpy + 0)
    ac.setPosition(tyrePressureLabels[1], tlpx + 120, tlpy + 0)
    ac.setPosition(tyrePressureLabels[2], tlpx, tlpy + 28)
    ac.setPosition(tyrePressureLabels[3], tlpx + 120, tlpy + 28)

    # =================================================================================================================
    #                                      ERS MODES LABELS
    # =================================================================================================================

    ersModeLabel = ac.addLabel(appWindow, "🗲 0 0")
    ac.setPosition(ersModeLabel, 10, 20)
    ac.setFontSize(ersModeLabel, 18)
    ac.setCustomFont(ersModeLabel, "Roboto", 0, 0)
    ac.setFontColor(ersModeLabel, 1.0, 1.0, 0.2, 1)
    ac.setFontAlignment(ersModeLabel, "left")

    # =================================================================================================================
    #                                      FUEL LABEL
    # =================================================================================================================

    fuelLabel = ac.addLabel(appWindow, "💧 --.- Laps")
    ac.setPosition(fuelLabel, 10, 0)
    ac.setFontSize(fuelLabel, 18)
    ac.setCustomFont(fuelLabel, "Roboto", 0, 0)
    ac.setFontColor(fuelLabel, 0.86, 0.86, 0.86, 1)
    ac.setFontAlignment(fuelLabel, "left")

    # =================================================================================================================
    #                                             DRS LABELS
    # =================================================================================================================

    drsLabel = ac.addLabel(appWindow, "DRS")
    ac.setPosition(drsLabel, 200, 0)
    ac.setFontSize(drsLabel, 35)
    ac.setCustomFont(drsLabel, "Roboto", 0, 1)
    ac.setFontColor(drsLabel, 0.86, 0.86, 0.86, 1)
    ac.setFontAlignment(drsLabel, "center")

    drsPenaltyLabel = ac.addLabel(appWindow, "")
    ac.setPosition(drsPenaltyLabel, 260, 0)
    ac.setFontSize(drsPenaltyLabel, 18)
    ac.setCustomFont(drsPenaltyLabel, "Roboto", 0, 1)
    ac.setFontColor(drsPenaltyLabel, 0.86, 0.86, 0.86, 1)
    ac.setFontAlignment(drsPenaltyLabel, "left")

    return APP_NAME

def acUpdate(deltaT):
    global timer0, timer1
    global tyreLabels, tyrePressureLabels
    global drsLabel, ersModeLabel, fuelLabel, drsPenaltyLabel
    global carValue, trackConfigValue, trackValue

    global currentLapValue, lapValue, previousLapValue, carWasInPit
    
    global totalDrivers, trackLength, lastTime, lastList
    global drsValid, lastDRSLevel, inDrsZone, drsPenAwarded, totalPenalty, soundPlaying

    # global currentLapValueMinutes, currentLapValueSeconds, lastLapValue, lastLapValueMinutes, lastLapValueSeconds, bestLapValue, previousBestLapValue, bestLapValueMinutes, bestLapValueSeconds, personalBestLapValue, previousPersonalBestLapValue, personalBestLapValueMinutes, personalBestLapValueSeconds, lapValidityValue, lapWasInvalid

    global tyreCompoundShort, tyreCompoundCleaned, previousTyreCompoundValue, minimumOptimalTemperature, maximumOptimalTemperature, idealPressureFront, idealPressureRear
    global tyreWearValue, tyreTemperatureValue, tyreTemperatureValueI, tyreTemperatureValueM, tyreTemperatureValueO, tyrePressureValue, tyreCompoundValue
    global temperatureTransitionRange, tyrePracticalTemperatureValue
    global fuelAmountValue, fuelStartValue, relevantLapsNumber, fuelSpentValue, fuelPerLapValue

    global compounds, modCompounds

    timer0 += deltaT
    timer1 += deltaT
        
    # Once per second
    if timer0 > 1:
        timer0 = 0

        # =================================================================================================================
        #                                    GET A BUNCH OF INFO
        # =================================================================================================================
        statusValue = info.graphics.status

        tyreCompoundValue = info.graphics.tyreCompound
        tyreWearValue = info.physics.tyreWear
        tyreTemperatureValue = info.physics.tyreCoreTemperature
        tyreTemperatureValueI = info.physics.tyreTempI
        tyreTemperatureValueM = info.physics.tyreTempM
        tyreTemperatureValueO = info.physics.tyreTempO
        tyrePressureValue = info.physics.wheelsPressure

        totalLapsValue = info.graphics.numberOfLaps
        fuelAmountValue = info.physics.fuel

        if ac.isCarInPitline(0):
            carWasInPit = 1

        # =================================================================================================================
        #                                   SET IDEAL TYRE PRESSURES AND TEMPERATURES
        # =================================================================================================================
        if previousTyreCompoundValue != tyreCompoundValue:
            previousTyreCompoundValue = tyreCompoundValue
            tyreCompoundShort = tyreCompoundValue[tyreCompoundValue.find("(")+1:tyreCompoundValue.find(")")]
            tyreCompoundCleaned = re.sub('\_+$', '', re.sub(r'[^\w]+', '_', tyreCompoundValue)).lower()
            
            if compounds.has_section(carValue + "_" + tyreCompoundCleaned):
                try:
                    idealPressureFront = int(compounds.get(carValue + "_" + tyreCompoundCleaned, "IDEAL_PRESSURE_F"))
                    idealPressureRear = int(compounds.get(carValue + "_" + tyreCompoundCleaned, "IDEAL_PRESSURE_R"))
                    minimumOptimalTemperature = int(compounds.get(carValue + "_" + tyreCompoundCleaned, "MIN_OPTIMAL_TEMP"))
                    maximumOptimalTemperature = int(compounds.get(carValue + "_" + tyreCompoundCleaned, "MAX_OPTIMAL_TEMP"))
                    ac.console("Tyres: {}, {}psi/{}psi, {}°C-{}°C".format(tyreCompoundValue, idealPressureFront, idealPressureRear, minimumOptimalTemperature, maximumOptimalTemperature))
                except:
                    ac.console("Error loading tyre data.")
            elif modCompounds.has_section(carValue + "_" + tyreCompoundCleaned):
                try:
                    idealPressureFront = int(modCompounds.get(carValue + "_" + tyreCompoundCleaned, "IDEAL_PRESSURE_F"))
                    idealPressureRear = int(modCompounds.get(carValue + "_" + tyreCompoundCleaned, "IDEAL_PRESSURE_R"))
                    minimumOptimalTemperature = int(float(modCompounds.get(carValue + "_" + tyreCompoundCleaned, "MIN_OPTIMAL_TEMP")))
                    maximumOptimalTemperature = int(float(modCompounds.get(carValue + "_" + tyreCompoundCleaned, "MAX_OPTIMAL_TEMP")))
                    ac.console("Tyres: {}, {}psi/{}psi, {}°C-{}°C".format(tyreCompoundValue, idealPressureFront, idealPressureRear, minimumOptimalTemperature, maximumOptimalTemperature))
                except:
                    ac.console("Error loading mod tyre data.")
            else:
                ac.console("Tyres: {}, no data found".format(tyreCompoundValue))

    # 10 times per second
    if timer1 > 0.1:
        timer1 = 0

        currentLapValue = info.graphics.iCurrentTime
        lapValue = ac.getCarState(0, acsys.CS.LapCount)
        lapProgressValue = ac.getCarState(0, acsys.CS.NormalizedSplinePosition)
        drsAvailableValue = ac.getCarState(0, acsys.CS.DrsAvailable)
        drsEnabledValue = ac.getCarState(0, acsys.CS.DrsEnabled)

        # =================================================================================================================
        #                                                  DRS
        # =================================================================================================================
        drsAvailableValue = ac.getCarState(0, acsys.CS.DrsAvailable)
        drsEnabledValue = ac.getCarState(0, acsys.CS.DrsEnabled)

        # =================================================================================================================
        #                                        DRS SIMPLE (not races)
        # =================================================================================================================
        
        if info.graphics.session != 2:
            if drsEnabledValue:
                ac.setFontColor(drsLabel, 0.25, 1.00, 0.10, 1)
                ac.setVisible(drsLabel, 1)
            elif drsAvailableValue:
                ac.setFontColor(drsLabel, 1.00, 1.00, 0.10, 1)
                ac.setVisible(drsLabel, 1)

                if not soundPlaying: # use this variable to control drs beep at begining of drs
                    sound_player.play(audio)
                    sound_player.stop()
                    # timer = threading.Timer(0.1, sound_player.stop)
                    # timer.start()
                    soundPlaying = True

            else:
                soundPlaying = False
                ac.setVisible(drsLabel, 0)

        # =================================================================================================================
        #                                          DRS DATA COLLECTION
        # =================================================================================================================
        
        if info.graphics.session == 2:

            curTime = time.time()
            clientCrossedDRS = -1 # index of DRS zone crossed during this update

            driverList = []
            for index in range(totalDrivers):
                driver = {
                    "spline":       ac.getCarState(index, acsys.CS.NormalizedSplinePosition),
                    "lastDRS":      0,
                    "DRStime":      0
                    }

                if len(lastList) > index:
                    # if lastList contains items copy items and check for DRS zone crossings
                    lastTick = lastList[index] # details about driver form last update
                    # copy relevant data
                    if lastTick is not None:
                        driver["lastDRS"] = lastTick["lastDRS"]
                        driver["DRStime"] = lastTick["DRStime"]

                    #spline distance travelled
                    splineDist = driver["spline"] - lastTick["spline"]

                    for id, zone in enumerate(drsData.zones):
                        # loop over DRS data
                        # check for crossing of any drs detection line
                        if splineDist > -0.8:
                            #not a new lap
                            if driver["spline"] >= zone["detection"] and lastTick["spline"] < zone["detection"]:
                                #driver crossed DRS detect line
                                driver["lastDRS"] = id
                                if index == 0:
                                    clientCrossedDRS = id
                                elapsedTime = curTime - lastTime
                                distTravelled = splineDist * trackLength
                                avgSpd = elapsedTime/distTravelled
                                distToLine = (zone["detection"] - lastTick["spline"]) * trackLength

                                #set crossed time via interpolation
                                driver["DRStime"] = lastTime + distToLine * avgSpd
                                break

                        elif zone["detection"] < 0.1:
                            #new lap and zone just after S/F
                            if driver["spline"] >= zone["detection"] and lastTick["spline"]-1 < zone["detection"]:
                                #driver crossed DRS detect line
                                driver["lastDRS"] = id
                                if index == 0:
                                    clientCrossedDRS = id
                                elapsedTime = curTime - lastTime
                                distTravelled = (driver["spline"] + (1-lastTick["spline"])) * trackLength
                                avgSpd = elapsedTime/distTravelled
                                distToLine = (driver["spline"] - zone["detection"]) * trackLength

                                #set crossed time via interpolation
                                driver["DRStime"] = curTime - distToLine * avgSpd
                                break

                        elif zone["detection"] > 0.9:
                            #new lap and zone just before S/F
                            if driver["spline"] + 1 >= zone["detection"] and lastTick["spline"] < zone["detection"]:
                                #driver crossed DRS detect line
                                driver["lastDRS"] = id
                                if index == 0:
                                    clientCrossedDRS = id
                                elapsedTime = curTime - lastTime
                                distTravelled = (driver["spline"] + (1-lastTick["spline"])) * trackLength
                                avgSpd = elapsedTime/distTravelled
                                distToLine = (zone["detection"] - lastTick["spline"]) * trackLength

                                #set crossed time via interpolation
                                driver["DRStime"] = lastTime + distToLine * avgSpd
                                break

                driverList.append(driver)


        # =================================================================================================================
        #                                          DRS ALLOWANCE MANAGEMENT
        # =================================================================================================================
        
            # Check if client crossed detection and within drsGap of another car
            if clientCrossedDRS != -1:
                myCar = driverList[0]
                drsValid = False
                inDrsZone = True
                drsPenAwarded = False

                #DRS from lap x
                if info.graphics.completedLaps+1 >= DRS_STARTS_ON_LAP:
                    #check for 1s rule
                    for index, car in enumerate(driverList):
                        if index == 0:
                            continue
                        if car["lastDRS"] == myCar["lastDRS"] and myCar["DRStime"] - car["DRStime"] <= DRS_GAP:
                            drsValid = True
                            ac.console("And I can use it:  car %d, gap %f. Me: %f other %f" % (index, (myCar["DRStime"] - car["DRStime"]), myCar["DRStime"], car["DRStime"]))
                            ac.setFontColor(drsLabel, *DRS_POSSIBLE)
                            ac.setVisible(drsLabel, 1)
                            break

            elif inDrsZone:
                # Didnt cross a line and in a zone so check to see if I leave it and DRS used only if valid
                zone  = drsData.zones[driverList[0]["lastDRS"]] # data of DRS zone in at last step

                # Check DRS used correctly and penalty not already awarded for this zone
                if info.physics.drs > 0 and drsValid is False:

                    ac.setFontColor(drsLabel, *DRS_BAD)
                    ac.setVisible(drsLabel, 1)
                    totalPenalty += curTime - lastTime
                    if totalPenalty > 0:
                        ac.setText(drsPenaltyLabel, "Penalty: +%ds" % totalPenalty)
                        ac.setVisible(drsPenaltyLabel, 1)

                    if not drsPenAwarded:
                        drsPenAwarded = True
                        ac.console(APP_NAME + ": Illegal DRS use.")
                        announcePenalty(ac.getDriverName(0), info.graphics.completedLaps + 1, "Illegal DRS use, Zone %d" % (driverList[0]["lastDRS"] + 1))

                    if not soundPlaying:
                        sound_player.play(audio)
                        soundPlaying = True

                # Saftey check for end line near S/F. (not sure necessary)
                if zone["end"] > 0.95 and driverList[0]["spline"] < 0.1:
                    inDrsZone = False
                    drsValid = False
                    drsPenAwarded = False

                    ac.setVisible(drsLabel, 0)
                    sound_player.stop()
                    soundPlaying = False
                    ac.console("OFF")

                # Turn off zone when leave
                if driverList[0]["spline"] >= zone["end"] and lastList[0]["spline"] < zone["end"]:
                    inDrsZone = False
                    drsValid = False
                    drsPenAwarded = False

                    ac.setVisible(drsLabel, 0)
                    sound_player.stop()
                    soundPlaying = False
                    ac.console("OFF")

                # Play a beep when crossing start line and DRS valid
                if drsValid and driverList[0]["spline"] >= zone["start"] and lastList[0]["spline"] < zone["start"]:
                    sound_player.play(audio)
                    #stop in 0.5s (double beep)
                    timer = threading.Timer(0.5, sound_player.stop)
                    timer.start()

                if drsAvailableValue and drsValid and not drsEnabledValue and totalPenalty > 0:
                    totalPenalty -= curTime - lastTime
                    ac.setText(drsPenaltyLabel, "Penalty: +%ds" % totalPenalty)
                    if totalPenalty < 0:
                        ac.setVisible(drsPenaltyLabel, 0)

                if not drsEnabledValue and drsAvailableValue:
                    if drsValid:
                        ac.setFontColor(drsLabel, *DRS_AVAILABLE)
                    else: # turn of the sound
                        ac.setVisible(drsLabel, 0)
                        sound_player.stop()
                        soundPlaying = False

                if drsEnabledValue and drsValid:
                    ac.setFontColor(drsLabel, *DRS_GOOD)


            elif info.physics.drs > 0:
                #enabled DRS at start of race or through back to pit
                if lastDRSLevel == 0:
                    ac.console(APP_NAME + ": Illegal DRS use.")
                    announcePenalty(ac.getDriverName(0), info.graphics.completedLaps + 1, "Illegal DRS use, DRS opened without crossing detection line (Start or backToPit)")

            # end of update save current values into lasts
            lastTime = curTime
            lastList = driverList
            lastDRSLevel = info.physics.drs

        # =================================================================================================================
        #                                              ERS LABEL
        # =================================================================================================================

        ersRecoveryLevel = info.physics.ersRecoveryLevel
        ersMode = info.physics.ersPowerLevel
        ac.setText(ersModeLabel, "🗲 {} {}".format(ERS_MODES[ersMode], ersRecoveryLevel))
        ac.setFontColor(ersModeLabel, ERS_COLORS[ersMode][0], ERS_COLORS[ersMode][1], ERS_COLORS[ersMode][2], 1)
        
        # =================================================================================================================
        #                                              FUEL LABEL
        # =================================================================================================================

        if fuelPerLapValue:
            ac.setText(fuelLabel, "💧 {:.1f} Laps".format(fuelAmountValue / fuelPerLapValue))

        # =================================================================================================================
        #                                          TYRE TEMPERATURES
        # =================================================================================================================

        for i in range(4):
            tyrePracticalTemperatureValue[i] = 0.25 * ((tyreTemperatureValueI[i] + tyreTemperatureValueM[i] + tyreTemperatureValueO[i]) / 3) + 0.75 * tyreTemperatureValue[i]

        for i, label in enumerate(tyreLabels):
            ac.setText(label, "{:.0f}".format(tyrePracticalTemperatureValue[i]))
            if minimumOptimalTemperature and maximumOptimalTemperature:
                if int(round(tyrePracticalTemperatureValue[i])) >= minimumOptimalTemperature and int(round(tyrePracticalTemperatureValue[i])) <= maximumOptimalTemperature:
                    ac.setBackgroundColor(label, 0.17, 1, 0)
                elif int(round(tyrePracticalTemperatureValue[i])) < minimumOptimalTemperature:
                    idealTemperatureDifference = min(temperatureTransitionRange, minimumOptimalTemperature - tyrePracticalTemperatureValue[i]) / temperatureTransitionRange
                    ac.setBackgroundColor(label, max(0, 0.17 - idealTemperatureDifference / 5.88), max(0.51, 1 - idealTemperatureDifference / 1.96), min(1, 0 + idealTemperatureDifference))
                elif int(round(tyrePracticalTemperatureValue[i])) > maximumOptimalTemperature:
                    idealTemperatureDifference = min(temperatureTransitionRange, tyrePracticalTemperatureValue[i] - maximumOptimalTemperature) / temperatureTransitionRange
                    ac.setBackgroundColor(label, min(1, 0.17 + idealTemperatureDifference / 0.83), max(0.17, 1 - idealTemperatureDifference / 0.83), 0)
            else:
                ac.setBackgroundOpacity(label, 0)
            ac.setBackgroundOpacity(label, 1) # background colors start to hyde for some reason so this is needed
        
        for i, label in enumerate(tyrePressureLabels):
            if idealPressureFront and idealPressureRear:
                if i < 2: # front
                    ac.setText(label, "{:+.1f}".format(tyrePressureValue[i] - idealPressureFront))
                else: # rear
                    ac.setText(label, "{:+.1f}".format(tyrePressureValue[i] - idealPressureRear))
            else:
                ac.setText(label, "{:.0f}".format(tyrePressureValue[i]))
        
    # =================================================================================================================
    #                                     CALCULATE AT LAP ENDING OR LAP START
    # =================================================================================================================

    #Display/calculate on lap start
    if currentLapValue > 500 and currentLapValue < 1000:
        carWasInPit = 0
        fuelStartValue = fuelAmountValue

    #Display/calculate on lap finish
    if previousLapValue < lapValue:
        # announce any penalty at the end of a lap
        if totalPenalty > 0:
            announceTotalPenalty(ac.getDriverName(0), info.graphics.completedLaps + 1)
        previousLapValue = lapValue

        #Fuel per lap
        if fuelAmountValue < fuelStartValue and not carWasInPit:
            relevantLapsNumber += 1
            fuelSpentValue += fuelStartValue - fuelAmountValue
            fuelPerLapValue = fuelSpentValue / relevantLapsNumber


# END OF AC_UPDATE
# ========================================================================================

class drs:
    def __init__(self):
        self.zones = []
        self.loadZones()
        self.valid = False

    def loadZones(self):
        try:
            track_name = ac.getTrackName(0)
            track_config = ac.getTrackConfiguration(0)
            if track_config is not None:
                drsIni = "content\\tracks\\%s\\%s\\%s" % (
                    track_name, track_config, "data\\drs_zones.ini")
            else:
                drsIni = "content\\tracks\\%s\\%s" % (
                    track_name, "data\\drs_zones.ini")
            drsExists = os.path.isfile(drsIni)

            if drsExists:
                config = configparser.ConfigParser()
                config.read(drsIni)
                # ac.log('zone sections: %s' % str(config.sections()))
                for zone in config.sections():
                    zone_info = {
                        "detection": float(config[zone]['DETECTION']),
                        "start": float(config[zone]['START']),
                        "end": float(config[zone]['END'])
                    }
                    ac.console(APP_NAME + ': zone %s' % str(zone_info))
                    self.zones.append(zone_info)
            else:
                ac.console(APP_NAME + ": could not find drs_zones.ini file")
                return False
        except Exception as e:
            ac.console(APP_NAME + ": Error in loadDrsZones: %s" % e)

def getTrackLength():
    try:
        trackLengthFloat = ac.getTrackLength(0)

        return trackLengthFloat
    except Exception as e:
        ac.console(APP_NAME + ": Error in getTrackLength: %s" % e)
        ac.log(APP_NAME + ": Error in getTrackLength: %s" % e)
        return 0

def announcePenalty(driver_name, lap, detail):
    try:
        ac.sendChatMessage(APP_NAME + ": %s was given a penalty, Lap: %d: %s" % (driver_name, lap, detail))
    except Exception as e:
        ac.log(APP_NAME + ": Error in announce penalty: %s" % e)

def announceTotalPenalty(driver_name, lap):
    global totalPenalty
    ac.sendChatMessage(APP_NAME + ": %s ended Lap: %d with total penalty of %d seconds." % (driver_name, lap, totalPenalty))

