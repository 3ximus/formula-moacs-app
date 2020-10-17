import sys
import re
import pickle
import os
import configparser
import threading
import hashlib
import time

import ac
import acsys

import platform
if platform.architecture()[0] == '64bit':
    sysdir=os.path.dirname(__file__)+'/stdlib64'
else:
    sysdir=os.path.dirname(__file__)+'/stdlib'
sys.path.insert(0, sysdir)
os.environ['PATH'] = os.environ['PATH'] + ";."

import ctypes
from ctypes import wintypes

from sim_info_lib.sim_info import info
from sound_player import SoundPlayer

APP_NAME = "DRSManager"
FONT_NAME = "Orbitron"
VERSION = '1.6'

# DEFAULT SETTINGS
DRS_ALLOWED_CARS = ['rss_formula_hybrid_2020', 'rss_formula_rss_3_v6', 'af1_f3'] # MANDATORY
SERVERS = []
SOUND_ON = False

# FOLDER PATHS
COMPOUNDSPATH = "apps/python/%s/compounds/" % APP_NAME

# RULES
DRS_GAP = 1.0
DRS_STARTS_ON_LAP = 3

#DRS COLORS
DRS_GOOD = (0.25, 1.00, 0.10, 1)
DRS_BAD = (1.,.0,.0, 1)
DRS_AVAILABLE = (1., 1., 0.1, 1)
DRS_POSSIBLE = (0.86, 0.86, 0.86, 1)

# ERS MODES TEXT
ERS_MODES = ['Charging', 'Low', 'High', 'Overtake', 'Speed', 'Hotlap']
# ERS COLORS [green to red gradient]
ERS_COLORS = [(.47,1.,.2, 1), (.73,1.,.2, 1), (1,1,.2, 1), (1.,.7,.1, 1), (1.,.33,0, 1), (1.,.0,.0, 1)]

audio = ('apps/python/%s/beep.wav' % APP_NAME)
sound_player = SoundPlayer(audio)

# TEXTURES
DRS_GOOD_TEXTURE = "apps/python/%s/ui/drs_good.png" % APP_NAME
DRS_BAD_TEXTURE = "apps/python/%s/ui/drs_bad.png" % APP_NAME
DRS_AVAILABLE_TEXTURE = "apps/python/%s/ui/drs_available.png" % APP_NAME
DRS_POSSIBLE_TEXTURE = "apps/python/%s/ui/drs_possible.png" % APP_NAME
DRS_PENALTY_TEXTURE = "apps/python/%s/ui/drs_penalty_background.png" % APP_NAME

ERS_MODES_TEXTURE = ["apps/python/%s/ui/ers_mode_%d.png" % (APP_NAME, i) for i in range(6)]

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
# tyreWearValue = [0] * 4
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
drsZones = None      # Definitions of DRS zones.
driversList = []
totalDrivers = 0
drsAvailableZones = []
currentDrsZone = -1
drsPenaltyAwardedInZone = False
totalPenalty = 0
soundPlaying = False
lastTime = 0

#other variables
temperatureTransitionRange = 20.0

# labels and ui data collected
tyreLabels = [None] * 4
tyrePressureLabels = [None] * 4
drsLabel, ersLabel, ersModeLabel, ersRecoveryLabel, fuelLabel, drsPenaltyLabel, drsPenaltyBackgroundLabel = None, None, None, None, None, None, None
compounds, modCompounds  = None, None
carValue, trackConfigValue, trackValue = None, None, None
# filePersonalBest = None

def acMain(ac_version):
    global DRS_ALLOWED_CARS, SOUND_ON, SERVERS
    global tyreLabels, tyrePressureLabels
    global drsLabel, ersLabel, ersModeLabel, ersRecoveryLabel, fuelLabel, drsPenaltyLabel, drsPenaltyBackgroundLabel

    global drsZones, totalDrivers, trackLength, drsAvailableZones, driversList

    global carValue, trackConfigValue, trackValue

    global compounds, modCompounds

    carValue = ac.getCarName(0)
    trackValue = ac.getTrackName(0)
    trackConfigValue = ac.getTrackConfiguration(0)

    settings = configparser.ConfigParser()
    settings.read("apps/python/%s/config.ini" % APP_NAME)
    if settings.has_section('CARS'):
        DRS_ALLOWED_CARS.extend([c for c in settings['CARS'] if settings['CARS'][c] == '1'])
    if settings.has_section('SETTINGS'):
        SOUND_ON = True if 'sound' in settings['SETTINGS'] and settings['SETTINGS']['sound'] == '1' else False
    if settings.has_section('SERVERS'):
        SERVERS = list(settings['SERVERS'].values())

    drsZones = loadDRSZones()
    totalDrivers = ac.getCarsCount()
    trackLength = getTrackLength()

    driversList = [Driver(i, len(drsZones)) for i in range(totalDrivers)]
    drsAvailableZones = [False] * len(drsZones)

    compounds = configparser.ConfigParser()
    compounds.read(COMPOUNDSPATH + "compounds.ini")
    modCompounds = configparser.ConfigParser()
    modCompounds.read(COMPOUNDSPATH + carValue + ".ini")

    ac.initFont(0, FONT_NAME, 0, 0)

    appWindow = ac.newApp(APP_NAME)
    ac.setTitle(appWindow, "")
    ac.drawBorder(appWindow, 0)
    ac.setIconPosition(appWindow, 0, -10000)
    ac.setSize(appWindow, 280, 70)
    ac.setBackgroundOpacity(appWindow, 0.2)

    # =================================================================================================================
    #                                             TYRE LABELS
    # =================================================================================================================

    tyreLabelFL = ac.addLabel(appWindow, "")
    tyreLabelFR = ac.addLabel(appWindow, "")
    tyreLabelRL = ac.addLabel(appWindow, "")
    tyreLabelRR = ac.addLabel(appWindow, "")
    tyreLabels = [tyreLabelFL, tyreLabelFR, tyreLabelRL, tyreLabelRR]
    for label in tyreLabels:
        ac.setFontSize(label, 15)
        ac.setFontColor(label, 0, 0, 0, 1)
        ac.setFontAlignment(label, "center")
        ac.setSize(label, 15, 23)

    tyrePressureLabelFL = ac.addLabel(appWindow, "PFL")
    tyrePressureLabelFR = ac.addLabel(appWindow, "PFR")
    tyrePressureLabelRL = ac.addLabel(appWindow, "PRL")
    tyrePressureLabelRR = ac.addLabel(appWindow, "PRR")
    tyrePressureLabels = [tyrePressureLabelFL, tyrePressureLabelFR, tyrePressureLabelRL, tyrePressureLabelRR]
    for label in tyrePressureLabels:
        ac.setFontSize(label, 15)
        ac.setFontColor(label, 0.86, 0.86, 0.86, 1)
        ac.setCustomFont(label, FONT_NAME, 0, 0)

    ac.setFontAlignment(tyrePressureLabels[0], "right")
    ac.setFontAlignment(tyrePressureLabels[1], "left")
    ac.setFontAlignment(tyrePressureLabels[2], "right")
    ac.setFontAlignment(tyrePressureLabels[3], "left")

    #position all the labels
    tlpx = 180
    tlpy = 10

    ac.setPosition(tyreLabels[0], tlpx + 5, tlpy + 0)
    ac.setPosition(tyreLabels[1], tlpx + 25, tlpy + 0)
    ac.setPosition(tyreLabels[2], tlpx + 5, tlpy + 28)
    ac.setPosition(tyreLabels[3], tlpx + 25, tlpy + 28)

    ac.setPosition(tyrePressureLabels[0], tlpx, tlpy + 2)
    ac.setPosition(tyrePressureLabels[1], tlpx + 43, tlpy + 2)
    ac.setPosition(tyrePressureLabels[2], tlpx, tlpy + 30)
    ac.setPosition(tyrePressureLabels[3], tlpx + 43, tlpy + 30)

    # =================================================================================================================
    #                                      ERS MODES LABELS
    # =================================================================================================================

    elpx = 15
    elpy = 10

    ersModeLabel = ac.addLabel(appWindow, "🗲0")
    ac.setPosition(ersModeLabel, elpx+50, elpy)
    ac.setFontSize(ersModeLabel, 18)
    ac.setCustomFont(ersModeLabel, FONT_NAME, 0, 0)
    ac.setFontColor(ersModeLabel, 1.0, 1.0, 0.2, 1)
    ac.setFontAlignment(ersModeLabel, "left")

    ersRecoveryLabel = ac.addLabel(appWindow, "")
    ac.setPosition(ersRecoveryLabel, elpx+85, elpy)
    ac.setFontSize(ersRecoveryLabel, 18)
    ac.setCustomFont(ersRecoveryLabel, FONT_NAME, 0, 0)
    ac.setFontColor(ersRecoveryLabel, 1.0, 1.0, 0.2, 1)
    ac.setFontAlignment(ersRecoveryLabel, "left")

    ersLabel = ac.addLabel(appWindow, "ERS:")
    ac.setPosition(ersLabel, elpx, elpy)
    ac.setFontSize(ersLabel, 18)
    ac.setCustomFont(ersLabel, FONT_NAME, 0, 0)
    ac.setFontColor(ersLabel, 1.0, 1.0, 0.2, 1)
    ac.setFontAlignment(ersLabel, "left")

    # =================================================================================================================
    #                                      FUEL LABEL
    # =================================================================================================================

    fuelLabel = ac.addLabel(appWindow, "💧 --.- Laps")
    ac.setPosition(fuelLabel, 15, 36)
    ac.setFontSize(fuelLabel, 18)
    ac.setCustomFont(fuelLabel, FONT_NAME, 0, 0)
    ac.setFontColor(fuelLabel, 0.86, 0.86, 0.86, 1)
    ac.setFontAlignment(fuelLabel, "left")

    # =================================================================================================================
    #                                             DRS LABELS
    # =================================================================================================================

    drsLabel = ac.addLabel(appWindow, "")
    ac.setPosition(drsLabel, -70, 0)
    ac.setSize(drsLabel, 70, 70)
    ac.setVisible(drsLabel, 0)

    drsPenaltyBackgroundLabel = ac.addLabel(appWindow, "")
    ac.setPosition(drsPenaltyBackgroundLabel, 0, 70)
    ac.setSize(drsPenaltyBackgroundLabel, 280, 25)
    ac.setBackgroundTexture(drsPenaltyBackgroundLabel, DRS_PENALTY_TEXTURE)
    ac.setVisible(drsPenaltyBackgroundLabel, 0)

    drsPenaltyLabel = ac.addLabel(appWindow, "")
    ac.setPosition(drsPenaltyLabel, 150, 70)
    ac.setFontSize(drsPenaltyLabel, 18)
    ac.setCustomFont(drsPenaltyLabel, FONT_NAME, 0, 1)
    ac.setFontColor(drsPenaltyLabel, 0.86, 0.86, 0.86, 1)
    ac.setFontAlignment(drsPenaltyLabel, "center")
    ac.setVisible(drsPenaltyLabel, 0)

    # Announce Start
    timer = threading.Timer(10, announceStart)
    timer.start()

    return APP_NAME

def acUpdate(deltaT):
    global timer0, timer1
    global tyreLabels, tyrePressureLabels
    global drsLabel, ersLabel, ersModeLabel, ersRecoveryLabel, fuelLabel, drsPenaltyLabel, drsPenaltyBackgroundLabel
    global carValue, trackConfigValue, trackValue

    global currentLapValue, lapValue, previousLapValue, carWasInPit

    global totalDrivers, trackLength, driversList, totalPenalty, soundPlaying, drsAvailableZones, currentDrsZone, drsPenaltyAwardedInZone, lastTime

    global tyreCompoundShort, tyreCompoundCleaned, previousTyreCompoundValue, minimumOptimalTemperature, maximumOptimalTemperature, idealPressureFront, idealPressureRear
    global tyreTemperatureValue, tyreTemperatureValueI, tyreTemperatureValueM, tyreTemperatureValueO, tyrePressureValue, tyreCompoundValue
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
        tyreCompoundValue = info.graphics.tyreCompound
        tyreTemperatureValue = info.physics.tyreCoreTemperature
        tyreTemperatureValueI = info.physics.tyreTempI
        tyreTemperatureValueM = info.physics.tyreTempM
        tyreTemperatureValueO = info.physics.tyreTempO
        tyrePressureValue = info.physics.wheelsPressure

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
                except:
                    ac.console("Error loading tyre data.")
            elif modCompounds.has_section(carValue + "_" + tyreCompoundCleaned):
                try:
                    idealPressureFront = int(modCompounds.get(carValue + "_" + tyreCompoundCleaned, "IDEAL_PRESSURE_F"))
                    idealPressureRear = int(modCompounds.get(carValue + "_" + tyreCompoundCleaned, "IDEAL_PRESSURE_R"))
                    minimumOptimalTemperature = int(float(modCompounds.get(carValue + "_" + tyreCompoundCleaned, "MIN_OPTIMAL_TEMP")))
                    maximumOptimalTemperature = int(float(modCompounds.get(carValue + "_" + tyreCompoundCleaned, "MAX_OPTIMAL_TEMP")))
                    # ac.console("Tyres: {}, {}psi/{}psi, {}°C-{}°C".format(tyreCompoundValue, idealPressureFront, idealPressureRear, minimumOptimalTemperature, maximumOptimalTemperature))
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

        # =================================================================================================================
        #                                                  DRS
        # =================================================================================================================
        drsAvailableValue = ac.getCarState(0, acsys.CS.DrsAvailable)
        drsEnabledValue = ac.getCarState(0, acsys.CS.DrsEnabled)

        # =================================================================================================================
        #                                        DRS SIMPLE (not races)
        # =================================================================================================================

        if info.graphics.session != 2 and ac.getCarName(0) in DRS_ALLOWED_CARS:
            if drsEnabledValue:
                set_drs_good()
            elif drsAvailableValue:
                set_drs_available()

                if not soundPlaying and SOUND_ON: # use this variable to control drs beep at begining of drs
                    sound_player.play(audio)
                    sound_player.stop()
                    soundPlaying = True
            else:
                soundPlaying = False
                ac.setVisible(drsLabel, 0)

        # =================================================================================================================
        #                                          DRS DATA COLLECTION
        # =================================================================================================================

        if info.graphics.session == 2 and ac.getCarName(0) in DRS_ALLOWED_CARS:

            crossedDetectionZone = -1
            crossedEndZone = -1
            crossedStartZone = -1
            curTime = time.time()
            for i in range(totalDrivers):
                spline = ac.getCarState(i, acsys.CS.NormalizedSplinePosition)
                for zid, zone in enumerate(drsZones):
                    if driver_crossed_zone(driversList[i].last_pos, zone['detection'], spline):
                        driversList[i].drs_detection_times[zid] = curTime
                        if i == 0: # current driver
                            crossedDetectionZone = zid # mark zone crossed by driver (not possible to cross multiple zone)
                    if i == 0 and driver_crossed_zone(driversList[i].last_pos, zone['end'], spline):
                        crossedEndZone = zid
                    if i == 0 and driver_crossed_zone(driversList[i].last_pos, zone['start'], spline):
                        crossedStartZone = zid
                driversList[i].last_pos = spline

        # =================================================================================================================
        #                                          DRS ALLOWANCE MANAGEMENT
        # =================================================================================================================

            # Race Restart
            if info.graphics.completedLaps == 0 and info.graphics.iCurrentTime == 0:
                totalPenalty = 0 # reset penalty
                set_drs_penalty(0)

            # DRS DETECTION Zone crossed
            if crossedDetectionZone != -1:
                if info.graphics.completedLaps + 1 >= DRS_STARTS_ON_LAP: # if this is a valid lap
                    ac.log("Checking Detection Zone: " + str(crossedDetectionZone) + " on lap: " + str(info.graphics.completedLaps))
                    # check if there is any driver within DRS_GAP
                    if any(driversList[0].drs_detection_times[crossedDetectionZone] - driver.drs_detection_times[crossedDetectionZone] <= DRS_GAP and driversList[0].drs_detection_times[crossedDetectionZone] - driver.drs_detection_times[crossedDetectionZone] >= 0 for driver in driversList[1:]):
                        set_drs_possible()
                        drsAvailableZones[crossedDetectionZone] = True

            # DRS END Zone crossed
            if crossedEndZone != -1:
                drsAvailableZones[crossedEndZone] = False
                currentDrsZone = -1
                drsPenaltyAwardedInZone = False
                # if next zone allows for drs already -- for cases where 1 DRS detection is used in 2 zones
                if drsAvailableZones[(crossedEndZone + 1) % len(drsAvailableZones)]: set_drs_possible()
                set_drs_hidden()

            # DRS START Zone crossed
            if crossedStartZone != -1:
                currentDrsZone = crossedStartZone

            # IN DRS ZONE
            if drsAvailableValue:
                if drsAvailableZones[currentDrsZone]:
                    if drsEnabledValue:
                        set_drs_good()
                    else:
                        set_drs_available()
                        if totalPenalty > 0: totalPenalty -= curTime - lastTime
                        set_drs_penalty(totalPenalty)
                else:
                    if drsEnabledValue:
                        set_drs_bad()
                        if not drsPenaltyAwardedInZone:
                            drsPenaltyAwardedInZone = True
                            announcePenalty(ac.getDriverName(0), info.graphics.completedLaps + 1, "Illegal DRS use, Zone %d" % (currentDrsZone))
                        # Add penalty amount
                        if abs(curTime - lastTime) < 1: totalPenalty += curTime - lastTime
                        set_drs_penalty(totalPenalty)
                    else:
                        set_drs_hidden()

            # end of drs update save current values into lasts
            lastTime = curTime

        # =================================================================================================================
        #                                              ERS LABEL
        # =================================================================================================================

        ersRecoveryLevel = info.physics.ersRecoveryLevel
        ersMode = info.physics.ersPowerLevel
        ac.setText(ersModeLabel, "🗲{}".format(ersMode))
        ac.setText(ersRecoveryLabel, "↺{}".format(ersRecoveryLevel))
        ac.setFontColor(ersModeLabel, *ERS_COLORS[ersMode])
        ac.setFontColor(ersLabel, *ERS_COLORS[ersMode])
        ac.setFontColor(ersRecoveryLabel, *ERS_COLORS[ersMode])

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
            # ac.setText(label, "{:.0f}".format(tyrePracticalTemperatureValue[i]))
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

def loadDRSZones():
    zones = []
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
            for zone in config.sections():
                zone_info = {
                    "detection": float(config[zone]['DETECTION']),
                    "start": float(config[zone]['START']),
                    "end": float(config[zone]['END'])
                }
                zones.append(zone_info)
        else:
            ac.console(APP_NAME + ": could not find drs_zones.ini file")
            return False
    except Exception as e:
        ac.console(APP_NAME + ": Error in loadDrsZones: %s" % e)
    return zones

class Driver:
    def __init__(self, id, n_drs_zones):
        self.id = id
        self.last_pos = 0
        self.drs_detection_times = [0] * n_drs_zones

def driver_crossed_zone(last, zone, current):
    '''Check if detection is between current and last'''
    if current < last: # crossed start/finish line
        return last < zone or zone <= current
    return last < zone <= current

def set_drs_bad():
    global drsLabel
    ac.setBackgroundTexture(drsLabel, DRS_BAD_TEXTURE)
    ac.setVisible(drsLabel, 1)

def set_drs_possible():
    global drsLabel
    ac.setBackgroundTexture(drsLabel, DRS_POSSIBLE_TEXTURE)
    ac.setVisible(drsLabel, 1)

def set_drs_available():
    global drsLabel
    ac.setBackgroundTexture(drsLabel, DRS_AVAILABLE_TEXTURE)
    ac.setVisible(drsLabel, 1)

def set_drs_good():
    global drsLabel
    ac.setBackgroundTexture(drsLabel, DRS_GOOD_TEXTURE)
    ac.setVisible(drsLabel, 1)

def set_drs_hidden():
    global drsLabel
    ac.setVisible(drsLabel, 0)

def set_drs_penalty(totalPenalty):
    global drsPenaltyLabel, drsPenaltyBackgroundLabel
    if totalPenalty > 1:
        ac.setText(drsPenaltyLabel, "Penalty: +%ds" % totalPenalty)
        ac.setVisible(drsPenaltyLabel, 1)
        ac.setVisible(drsPenaltyBackgroundLabel, 1)
    else:
        ac.setVisible(drsPenaltyLabel, 0)
        ac.setVisible(drsPenaltyBackgroundLabel, 0)

def getTrackLength():
    try:
        trackLengthFloat = ac.getTrackLength(0)

        return trackLengthFloat
    except Exception as e:
        ac.console(APP_NAME + ": Error in getTrackLength: %s" % e)
        ac.log(APP_NAME + ": Error in getTrackLength: %s" % e)
        return 0

def announcePenalty(driver_name, lap, detail):
    if SERVERS and any(ac.getServerName().startswith(x) for x in SERVERS):
        try:
            ac.sendChatMessage(APP_NAME + " %s : %s penalty on Lap: %d: %s" % (VERSION, driver_name, lap, detail))
        except Exception as e:
            ac.log(APP_NAME + ": Error in announce penalty: %s" % e)

def announceTotalPenalty(driver_name, lap):
    if SERVERS and any(ac.getServerName().startswith(x) for x in SERVERS):
        global totalPenalty
        ac.sendChatMessage(APP_NAME + " %s : %s ended Lap: %d with total penalty of %d seconds." % (VERSION, driver_name, lap, totalPenalty))

def announceStart():
    if SERVERS and any(ac.getServerName().startswith(x) for x in SERVERS):
        driver_name = ac.getDriverName(0)
        digest = hashlib.md5(open("apps/python/%s/%s.py" % (APP_NAME, APP_NAME), 'rb').read()).hexdigest()
        ac.sendChatMessage(APP_NAME + " %s : %s --> %s" % (VERSION, driver_name, digest))

