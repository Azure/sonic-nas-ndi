#!/usr/bin/python3
###########################################################################
#
# Copyright 2019 Dell, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
###########################################################################
from rpipe_utils import pipestr
import cli_client as cc
import cli_log as log
from scripts.render_cli import show_cli_output
from natsort import natsorted

def recent_interval(interval):
    if interval == "5min":
       return "5_MINUTES"
    elif interval == "60min":
       return "60_MINUTES"
    elif interval == "24hr":
       return "24_HOURS"	
    else:
       return "5_MINUTES"

def severity(sev):
    if sev == 'warning':
        return "WARNING"
    elif sev == "major":
        return "MAJOR"
    elif sev == "minor":
        return "MINOR"
    elif sev == "critical":
        return "CRITICAL"
    else:
        return "INFORMATIONAL"

def process_cmd_params(args):
    filter = {}

    if len(args) == 6:
        if args[2] == "from" or args[2] == "start":
            filter_param = {"begin":args[3],"end":args[5]}
            if args[2] == "from":
                filter = { "id": filter_param }
            else:
                filter = {"time": filter_param }
    elif len(args) == 4:
        if args[2] == "from" or args[2] == "start":
            filter_param = {"begin":args[3]}
            if args[2] == "from":
                filter = { "id": filter_param }
            else:
                filter = {"time": filter_param }

        elif args[2] == "severity":
            filter = {"severity": severity(args[3])}

        elif args[2] == "recent":
            filter = {"interval": recent_interval(args[3])} 

    return filter

                
def invoke_api(func, args):

   api = cc.ApiClient()
   if func == "get_alarm_all" or \
        func == "get_alarm_detail" or \
        func == "get_alarm_acknowledged":
        path = "/restconf/data/sonic-alarm:sonic-alarm/ALARM/ALARM_LIST"
        return api.get(path)

   elif func == "get_alarm_filter":
        filters = process_cmd_params(args)
        if len(filters):
            path = "/restconf/operations/sonic-alarm:show-alarms"
            body  =  {"sonic-alarm:input":filters}
            return api.post(path, body)
        else:
            path = "/restconf/data/sonic-alarm:sonic-alarm/ALARM/ALARM_LIST"
            return api.get(path)

   elif func == "get_alarm_id":
        if len(args) == 4:
            path = "/restconf/data/sonic-alarm:sonic-alarm/ALARM/ALARM_LIST=" + args[3]
            return api.get(path)

   elif func == "get_alarm_stats":
        path = "/restconf/data/sonic-alarm:sonic-alarm/ALARM_STATS/ALARM_STATS_LIST"
        return api.get(path)

   elif func == "get_event_stats":
        path = "/restconf/data/sonic-event:sonic-event/EVENT_STATS/EVENT_STATS_LIST"
        return api.get(path)
       
   elif func == "get_event_details": 
        path = "/restconf/data/sonic-event:sonic-event/EVENT/EVENT_LIST"
        return api.get(path)

   elif func == "get_event_filter":
        filters = process_cmd_params(args)
        if len(filters):
            path = "/restconf/operations/sonic-event:show-events"
            body  =  {"sonic-event:input":filters}
            return api.post(path, body)
        else:
            path = "/restconf/data/sonic-event:sonic-event/EVENT/EVENT_LIST"
            return api.get(path)

   elif func == "get_event_id":
        if len(args) == 4:
            path = "/restconf/data/sonic-event:sonic-event/EVENT/EVENT_LIST=" + args[3]
            return api.get(path)

   elif func == "alarm_acknowledge":
        if len(args) == 3:
            body = {"sonic-alarm:input": {"id":[args[2]]}}
            path = "/restconf/operations/sonic-alarm:acknowledge-alarms"
            return api.post(path, body)

   elif func == "alarm_unacknowledge":
        if len(args) == 3:
            body = {"sonic-alarm:input": {"id":[args[2]]}}
            path = "/restconf/operations/sonic-alarm:unacknowledge-alarms"
            return api.post(path, body)

def run(func, args):
    try:
        api_response = invoke_api(func, args)
        if api_response is None:
            return
        if api_response.ok():
            response = api_response.content
            if response is None:
                print("Success")
            else:
                if 'sonic-event:output' in response:
                    if response['sonic-event:output']['EVENT']['EVENT_LIST']:
                        event_lst = natsorted(response['sonic-event:output']['EVENT']['EVENT_LIST'], key=lambda t: t["id"])
                        response['sonic-event:output']['EVENT']['EVENT_LIST'] = event_lst 
                        show_cli_output('show_event_summary.j2', response['sonic-event:output'])
                elif 'sonic-event:EVENT_LIST' in response:
                    evt_lst = natsorted(response['sonic-event:EVENT_LIST'], key=lambda t: t["id"])
                    response['sonic-event:EVENT_LIST'] = evt_lst
                    if func == 'get_event_details' or \
                        func == 'get_event_id':
                          show_cli_output('show_event_details.j2', response)
                    else:
                          show_cli_output('show_event_summary.j2', response)
                elif 'sonic-alarm:output' in response:
                    if func == 'alarm_acknowledge' or \
                        func == 'alarm_unacknowledge':
                        if response['sonic-alarm:output']['status']:
                            print("Error: {}" .format(response['sonic-alarm:output']['status-detail']))
                    else:    
                      if response['sonic-alarm:output']['ALARM']['ALARM_LIST']:
                        alarm_lst = natsorted(response['sonic-alarm:output']['ALARM']['ALARM_LIST'], key=lambda t: t["id"])
                        response['sonic-alarm:output']['ALARM']['ALARM_LIST'] = alarm_lst              
                        show_cli_output('show_event_summary.j2', response['sonic-alarm:output'])
                elif 'sonic-alarm:ALARM_LIST' in response:
                    if response['sonic-alarm:ALARM_LIST']:
                        alarm_lst = natsorted(response['sonic-alarm:ALARM_LIST'], key=lambda t: t["id"])
                        response['sonic-alarm:ALARM_LIST'] = alarm_lst              
                        if func == 'get_alarm_detail' or \
                            func == "get_alarm_id":
                            show_cli_output('show_event_details.j2', response)
                        else:
                            show_cli_output('show_event_summary.j2', response, key=func)
                elif 'sonic-alarm:ALARM_STATS_LIST' in response or \
                     'sonic-event:EVENT_STATS_LIST' in response:
                    show_cli_output('show_event_summary.j2', response)

    except ApiException as e:
        print("%ERROR:Transaction failure.")

if __name__ == '__main__':
    log.log_info("Loading sonic_cli_event.py module")
    pipestr().write(sys.argv)
    func = sys.argv[1]

    run(func, sys.argv[2:])
