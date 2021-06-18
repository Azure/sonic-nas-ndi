#!/usr/bin/python

import sys
import cli_client as cc
import re

def invoke(func, args):
    body = None
    aa = cc.ApiClient()

    # Gather tech support information into a compressed file
    if func == 'rpc_sonic_show_techsupport_sonic_show_techsupport_info':
        keypath = cc.Path('/restconf/operations/sonic-show-techsupport:sonic-show-techsupport-info')
        if args is None:
            body = {"sonic-show-techsupport:input":{"date": None}}
        else:
            body = {"sonic-show-techsupport:input":{"date": args[0]}}
        return aa.post(keypath, body)
    else:
        print("%Error: not implemented")
        exit(1)


def run(func, args):

    if func != 'rpc_sonic_show_techsupport_sonic_show_techsupport_info':
        print("%Error: Show Techsupport parsing Failed: Invalid "
              "function")
        return

    try:
        api_response = invoke(func, args)

    except ValueError as err_msg:
        print("%Error: An exception occurred while attempting to gather "
              "the requested information via a remote procedure "
              "call: {}".format(err_msg))

    if not api_response.ok():
        # Print the message for a failing return code
        print("CLI transformer error: ")
        print("    status code: {}".format(response.status_code))
        return

    response = api_response.content
    if ((response is None) or
        (not ('sonic-show-techsupport:output' in response)) or
        (response['sonic-show-techsupport:output'] is None)):
        if ('ietf-restconf:errors' in response):
            print(response['ietf-restconf:errors']['error'][0]['error-message'])
        else:
            print("%Error: Command Failure: Unknown failure type")
        return

    output_msg_object = response['sonic-show-techsupport:output']

    if ((output_msg_object['output-status'] is None) or
        (len(output_msg_object['output-status']) is 0)):
        print("%Error: Command Failure: Unknown failure type")
        return

    if not (output_msg_object['output-status'] == "Success"):
        print("%Error: {}".format(output_msg_object['output-status']))
        return

    if ((output_msg_object['output-filename'] is None) or
        (len(output_msg_object['output-filename']) is 0)):
        print("%Error: Command Failure: Unknown failure type")
        return

    # No error code flagged: Normal case handling
    output_message = output_msg_object['output-filename']
    output_file_match = re.search('\/var\/.*dump.*\.gz',
                                  output_message)
    if output_file_match is not None:
        output_filename = output_file_match.group()
        print("Output stored in:  " + output_filename)
    else:
        # Error message with non-error return code
        print(output_message)



if __name__ == '__main__':
    if len(sys.argv) == 3:
	    run(sys.argv[1], sys.argv[2:])
    else:
            run(sys.argv[1], None)
