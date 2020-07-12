
import mido
import re
import time

def connectMidiInPort(nameRegEx: str):
    ports = mido.get_input_names()
    r = re.compile(nameRegEx)
    for name in ports:
        if r.match(name):
            try:
                portIn = mido.open_input(name)
                return portIn
            except Exception as e:
                print("error connect midi in: {}".format(e))
                return None

fire_in_port = connectMidiInPort("FL STUDIO.*")

try:
    while True:
        msg = fire_in_port.poll()
        if msg is not None:
            print(msg)
        time.sleep(0.001)
except Exception as e:
    print("Something happened: {}".format(e))


