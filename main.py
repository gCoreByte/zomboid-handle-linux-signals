#!/usr/bin/env python3

import subprocess
import threading
import os
import sys
import signal
from enum import Enum

# Global Zomboid process to allow easier handling between threads
process: subprocess.Popen

# Additional flags to control execution between threads
# Remember to use locking
flags = {'RESTART': True, 'KILLED': False}

# Change our directory to the installation directory if not there already
INSTDIR = os.path.dirname(os.path.realpath(__file__))
os.chdir(INSTDIR)


class JavaVersion(Enum):
    AMD64 = '64'
    I386 = '32'


class StdinWriter:
    def __init__(self):
        self.data = ''

    def write(self, data):
        self.data += data

    def readline(self):
        if self.data:
            line, self.data = self.data.split('\n', 1)
            return line + '\n'
        else:
            return ''


def read_input():
    """
    Controls sending input between the process and the wrapper.
    Allows adding custom commands (such as restart).
    :return:
    """
    global process
    while True:
        input_data = input()
        # Restart command
        if input_data.lower().strip() == 'restart':
            flags['RESTART'] = True
            process.stdin.write('quit\n')
            process.stdin.flush()
            return
        if input_data.lower().strip() == 'quit':
            process.stdin.write(input_data + "\n")
            process.stdin.flush()
            return
        if flags['KILLED']:
            return
        process.stdin.write(input_data + "\n")
        process.stdin.flush()


def capture_output():
    """
    Handles printing the output from the Zomboid process.
    Allows adding extra filtering.
    :return:
    """
    global process
    for line in process.stdout:
        if flags['KILLED']:
            return
        print(line.rstrip())


def start_zomboid_instance(zomboid_command):
    """
    Starts the Zomboid server and 2 extra threads to handle input and output
    :param zomboid_command: Command to start the server
    :return:
    """
    global process
    process = subprocess.Popen(
        zomboid_command.strip(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    input_thread = threading.Thread(target=read_input, daemon=True)
    input_thread.start()

    output_thread = threading.Thread(target=capture_output, daemon=True)
    output_thread.start()

    process.wait()

    input_thread.join()
    output_thread.join()
    print('Exited cleanly.')


def detect_java_bit():
    """
    Helper function to detect java version.
    :return: Java version or none
    """
    version = subprocess.check_output(['java', '-version'], stderr=subprocess.STDOUT).decode().lower()

    if "64-bit" in version:
        return JavaVersion.AMD64

    if "32-bit" in version:
        return JavaVersion.I386

    return None


def set_environment_variables(bit):
    """
    This function is a near perfect copy of the original start-shell.sh script
    :param bit:
    :return:
    """
    os.environ["PATH"] = f'{INSTDIR}/jre64/bin:{os.environ["PATH"]}'
    ld_lib_path = os.environ.get("LD_LIBRARY_PATH", "")
    os.environ["LD_PRELOAD"] = f'{os.environ.get("LD_PRELOAD", "")}:libjsig.so'

    if bit == JavaVersion.AMD64:
        os.environ["LD_LIBRARY_PATH"] = \
            f'{INSTDIR}/linux64:{INSTDIR}/natives:{INSTDIR}:{INSTDIR}/jre64/lib/amd64:{ld_lib_path}'

        executable = f"{INSTDIR}/ProjectZomboid64"
    elif bit == JavaVersion.I386:
        os.environ["LD_LIBRARY_PATH"] = \
            f'{INSTDIR}/linux32:{INSTDIR}/natives:{INSTDIR}:{INSTDIR}/jre/lib/i386:{ld_lib_path}'

        executable = f"{INSTDIR}/ProjectZomboid32"
    else:
        raise Exception('Java version is invalid.')

    return executable


def handle_signal(_signum, _frame):
    """
    Handles SIGINT and SIGTERM to force the server to exit cleanly.
    :param _signum:
    :param _frame:
    :return:
    """
    original_stdin = sys.stdin
    sys.stdin = StdinWriter()
    sys.stdin.write('quit')
    flags['KILLED'] = True
    sys.stdin = original_stdin


def main():
    """
    Main function, checks Java version and handles loop
    :return:
    """
    java_bit = detect_java_bit()
    if java_bit:
        print(f"{java_bit}-bit java detected")
        executable = set_environment_variables(java_bit)
        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)
        while flags['RESTART']:
            flags['RESTART'] = False
            start_zomboid_instance(f'{executable} {" ".join(sys.argv[1:])}')
    else:
        print("Couldn't determine 32/64 bit of java")
        sys.exit(1)


if __name__ == "__main__":
    main()
