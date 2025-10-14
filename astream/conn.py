from ctypes import *
import os.path
import numpy as np

current_dir_path = os.path.dirname(os.path.realpath(__file__))

class GoSlice(Structure):
    _fields_ = [("data", POINTER(c_void_p)), 
                ("len", c_longlong), ("cap", c_longlong)]

class GoString(Structure):
    _fields_ = [("p", c_char_p), ("n", c_longlong)]



import time
last_time = None

def setupLib(sa_ecf):
    global lib 
    if sa_ecf:
        lib = cdll.LoadLibrary(current_dir_path + "/proxy_module_sa-ecf.so")
    else:
        lib = cdll.LoadLibrary(current_dir_path + "/proxy_module_default.so")

    lib.ClientSetup.argtypes = [c_bool,c_bool,c_bool, c_bool,GoString,GoString]
    lib.DownloadSegment.argtypes = [GoString]
    lib.CloseConnection.argtypes = []
    lib.StartLogging.argtypes = [c_uint]
    lib.StopLogging.argtypes = []
    lib.Connect.argtypes = []
    lib.DownloadSegmentPriority.argtypes = [GoString, c_ubyte]
    lib.PktsFromClient.argtypes = [GoString]

def connectPM():
    lib.Connect()

def setupPM(useQUIC, useMP, useMS, keepAlive, schedulerName, congestionControl='cubic'):
    scheduler = GoString(schedulerName.encode('ascii'), len(schedulerName))
    cc = GoString(congestionControl.encode('ascii'), len(congestionControl))
    lib.ClientSetup(useQUIC, useMP, useMS, keepAlive, scheduler, cc)

def closeConnection():
    lib.CloseConnection()

def download_segment_PM(segment_url):
    segment = GoString(segment_url.encode('ascii'), len(segment_url))
    return lib.DownloadSegment(segment)

def startLogging(period):
    lib.StartLogging(period)

def stopLogging():
    lib.StopLogging()

def download_segment_priority_PM(segment_url, segment_priority):
    segment = GoString(segment_url.encode('ascii'), len(segment_url))
    return lib.DownloadSegmentPriority(segment, segment_priority)

def PktsFromClient(client_domain_url):
    client_domain = GoString(client_domain_url.encode('ascii'), len(client_domain_url))
    return lib.PktsFromClient(client_domain)

