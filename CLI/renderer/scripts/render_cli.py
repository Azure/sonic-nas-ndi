#!/usr/bin/env python3
from jinja2 import Template, Environment, FileSystemLoader
import os
import json
import sys
import gc
import select
import termios
from .rpipe_utils import pipestr
import datetime

# Capture our current directory
#THIS_DIR = os.path.dirname(os.path.abspath(__file__))

global line_count
global ctrl_rfd

# AFB: 12/09/2019: If sonic_cli_output() gets called twice in actioner
# script, then # render_init() is called twice ==> os.fdopen() is called
# twice ==> "OSError: [Errno 9] Bad file descriptor" executing the os.fdopen()
render_init_called = False

def render_init(fd):
    global ctrlc_rfd

    # See Note above.
    global render_init_called
    if render_init_called == True:
        return None

    render_init_called = True

    ctrlc_rd_fd_num = int(fd)
    try:
        ctrlc_rfd = os.fdopen(ctrlc_rd_fd_num, 'r')
    except IOError as e:
        sys.stdout.write("Received error : " + str(e))
    gc.collect()
    return None

def cli_getch():
    # Disable canonical mode of input stream
    # Set min bytes as 1 and read operation as blocking
    fd = sys.stdin.fileno()
    term_settings_old = termios.tcgetattr(fd)
    term_settings_new = termios.tcgetattr(fd)
    term_settings_new[3] = term_settings_new[3] & ~termios.ICANON
    term_settings_new[6][termios.VMIN] = 1
    term_settings_new[6][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW, term_settings_new)
    c = None

    #global ctrc_rfd
    #fds = [fd, ctrlc_rfd]
    fds = [fd]
    try:
        termios.tcflush(fd, termios.TCIFLUSH)
        read_fds, write_fds, excep_fds = select.select(fds, [], [])
        """
        # Return immediately for Ctrl-C interrupt
        if ctrlc_rfd in read_fds:
            return 'q'
        """
        c = os.read(fd, 1)
        termios.tcflush(fd, termios.TCIFLUSH)
    except KeyboardInterrupt:
        return 'q'
    except select.error as e:
        if e[0] == 4: # Interrupted system call
            return 'q'
        else:
            sys.stdout.write("Received error : " + str(e))
    finally:
        termios.tcsetattr(fd, termios.TCSANOW, term_settings_old)
    return c.decode()

def _write(string, disable_page=False):
    """
    This function would take care of complete pagination logic,
    like printing --more--, accepting SPACE, ENTER, q, CTRL-C
    and act accordingly
    """
    global line_count

    page_len_local = int(os.getenv("CLISH_TERM_LEN", '24'))
    terminal = sys.stdout
    # set length as 0 for prints without pagination
    if disable_page is True:
        page_len_local = 0
    if len(string) != 0:
        terminal.write(string + '\n')
        if page_len_local == 0:
            return False
        line_count = line_count + 1
        if line_count == page_len_local:
            terminal.write("--more--")
            while 1:
                terminal.flush()
                c = cli_getch()
                terminal.flush()
                # End of text (ascii value 3) is returned while pressing Ctrl-C
                # key when CLISH executes commands from non-TTY
                # Example : clish_source plugin
                if c == 'q' or ord(c) == 3:
                    terminal.write('\x1b[2K'+'\x1b[0G')
                    line_count = 0
                    #self.is_stopped = True
                    return True
                elif c == ' ':
                    line_count = 0
                    terminal.write('\x1b[2K'+'\x1b[0G')
                    break
                # Carriage return (\r) is returned while pressing ENTER
                # key when CLISH executes commands from non-TTY
                # Example : clish_source plugin
                elif c == '\n' or c == '\r':
                    line_count = page_len_local - 1
                    terminal.write('\x1b[1A'+'\x1b[2K')
                    terminal.flush()
                    break
    return False

def write(t_str, continuation=False):
    global line_count
    if not continuation:
        line_count = 0
    q = False

    render_init(0)
    if t_str != "":
        pipelst = pipestr().read();
        for s_str in t_str.split('\n'):
            if pipelst:
                if pipelst.process_pipes(s_str):
                    q = _write(s_str, pipelst.is_page_disabled())
            else:
                q = _write(s_str)
            if q:
                return True
    return False

def show_cli_output(template_file, response, continuation=False, **kwargs):
    # Create the jinja2 environment.
    # Notice the use of trim_blocks, which greatly helps control whitespace.

    template_path = os.getenv("RENDERER_TEMPLATE_PATH")
    #template_path = os.path.abspath(os.path.join(THIS_DIR, "../render-templates"))

    j2_env = Environment(loader=FileSystemLoader(template_path),extensions=['jinja2.ext.do','jinja2.ext.loopcontrols'])
    j2_env.trim_blocks = True
    j2_env.lstrip_blocks = True
    j2_env.rstrip_blocks = True

    def datetimeformat_rfc3339(time):
        s = datetime.datetime.fromtimestamp(int(time)//1000000000).strftime('%Y-%m-%dT%H:%M:%S')
        return s + "." + (str(int(time)%1000000000))[0:3] + "Z"

    j2_env.globals.update(datetimeformat_rfc3339=datetimeformat_rfc3339)

    def datetimeformat(time):
        return datetime.datetime.fromtimestamp(int(time)).strftime('%Y-%m-%d %H:%M:%S')

    j2_env.globals.update(datetimeformat=datetimeformat)

    full_cmd = os.getenv('USER_COMMAND', None)
    if full_cmd is not None:
        pipestr().write(full_cmd.split())

    if response is not None:
        t_str = (j2_env.get_template(template_file).render(json_output=response, **kwargs))
        return write(t_str, continuation=continuation)
