#!/usr/bin/env python3
# 
# (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
#
# Author(s): Max Beckett
# Creation Date: 2/16/2016
# 

import enum

class WatchdogStatus(enum.Enum):
    DeleteRequest = '1'
    GetRequest = '2'
    PostRequest = '3'
    PutRequest = '4'
    DeleteSendNetconf = '5'
    GetSendNetconf = '6'
    PostSendNetconf = '7'
    PutSendNetconf = '8'
    DeleteReceiveNetconf = '9'
    GetReceiveNetconf = '10'
    PostReceiveNetconf = '11'
    PutReceiveNetconf = '12'
    DeleteReply = '13'
    GetReply = '14'
    PostReply = '15'
    PutReply = '16'
    
watchdog_mapping = {
    WatchdogStatus.DeleteRequest.value : "Delete Request",
    WatchdogStatus.GetRequest.value : "Get Request",
    WatchdogStatus.PostRequest.value : "Post Request",
    WatchdogStatus.PutRequest.value : "Put Request",
    WatchdogStatus.DeleteSendNetconf.value : "Delete Send Netconf",
    WatchdogStatus.GetSendNetconf.value : "Get Send Netconf",
    WatchdogStatus.PostSendNetconf.value : "Post Send Netconf",
    WatchdogStatus.PutSendNetconf.value : "Put Send Netconf",
    WatchdogStatus.DeleteReceiveNetconf.value : "Delete Receive Netconf",
    WatchdogStatus.GetReceiveNetconf.value : "Get Receive Netconf",
    WatchdogStatus.PostReceiveNetconf.value : "Post Receive Netconf",
    WatchdogStatus.PutReceiveNetconf.value : "Put Receive Netconf",
    WatchdogStatus.DeleteReply.value : "Delete Reply",
    WatchdogStatus.GetReply.value : "Get Reply",
    WatchdogStatus.PostReply.value : "Post Reply",
    WatchdogStatus.PutReply.value : "Put Reply",
}


