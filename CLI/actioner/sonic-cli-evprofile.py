#!/usr/bin/python3
############################################################################
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

import sys
from rpipe_utils import pipestr
from scripts.render_cli import show_cli_output
import cli_client as cc

def run(func, args):
    aa = cc.ApiClient()

    if func == 'get_evprofile':
        keypath = cc.Path('/restconf/operations/sonic-evprofile:get-evprofile')
        response = aa.post(keypath)
        if response.ok():
            api_response = response.content["sonic-get-evprofile:output"]
            show_cli_output("show_evprofile_rpc.j2", api_response)
        else:
            print(response.error_message())
            return 1

    if func == 'set_evprofile':
        keypath = cc.Path('/restconf/operations/sonic-evprofile:set-evprofile')
        body = { "sonic-evprofile:input": { "file-name": args[0]} }
        response = aa.post(keypath, body)
        if not response.ok():
            print(response.error_message())
            return 1

if __name__ == '__main__':

    pipestr().write(sys.argv)
    func = sys.argv[1]

    run(func, sys.argv[2:])

