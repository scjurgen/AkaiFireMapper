#!/usr/bin/env python3

import mido
import re
import time

from mido.ports import MultiPort

midiChannelOut = 1 # corresponds to channel 2 in Logic

class BitmapFont:
    wb = 0
    width = 0
    height = 0
    first = 0
    font_size = [0] * 256
    font_data = []

    def __init__(self, filename):
        with open(filename, "rb") as f:
            self.wb = int.from_bytes(f.read(1), byteorder='big', signed=False)
            self.width = int.from_bytes(f.read(1), byteorder='big', signed=False)
            self.height = int.from_bytes(f.read(1), byteorder='big', signed=False)
            self.first = int.from_bytes(f.read(1), byteorder='big', signed=False)
            for i in range(256):
                self.font_size[i] = int.from_bytes(f.read(1), byteorder='big', signed=False)
            b = f.read(1)
            while b:
                self.font_data.append(int.from_bytes(b, byteorder='big', signed=False))
                b = f.read(1)

    def print_at(self, x: int, y: int, str: str, set_pixel_routine):
        for ch in str:
            c = ord(ch)
            for row in range(self.height):
                b = 0
                ox = x
                bit = 0x80
                cnt = 0
                for xp in range(self.width):
                    if bit == 0x80:
                        b = self.font_data[c * self.height * self.wb + row * self.wb + cnt]
                        cnt += 1
                    if b & bit:
                        set_pixel_routine(ox, y + row, 1)
                    ox += 1
                    bit >>= 1
                    if bit == 0:
                        bit = 0x80
            if c == 32:
                x += int(self.width / 2)
            else:
                x += self.font_size[c]


class AkaiFireBitmap:

    def __init__(self, font_file_name: str):
        self.fnt = BitmapFont(font_file_name)

    bitmapDisplay = [0] * 1171  # the oled has 1171 bytes for xfer: ceil(128*64/7)

    bitMutate = [[13, 0, 1, 2, 3, 4, 5, 6],  # triangle structure for the bits, to hard to compute... ;-)
                 [19, 20, 7, 8, 9, 10, 11, 12],
                 [25, 26, 27, 14, 15, 16, 17, 18],
                 [31, 32, 33, 34, 21, 22, 23, 24],
                 [37, 38, 39, 40, 41, 28, 29, 30],
                 [43, 44, 45, 46, 47, 48, 35, 36],
                 [49, 50, 51, 52, 53, 54, 55, 42]]

    def show(self, port):
        chunkSize = 1171 + 4
        msgData = [0x47, 0x7f, 0x43, 0x0E, chunkSize >> 7, chunkSize & 0x7F, 0, 0x07, 0, 0x7f]
        for i in range(chunkSize - 4):
            msgData.append(self.bitmapDisplay[i])
        colMsg = mido.Message('sysex', data=bytearray(msgData))
        port.send(colMsg)

    def clear(self):
        for i in range(1171):
            self.bitmapDisplay[i] = 0

    def set_pixel(self, x: int, y: int, c: int):
        if x > 127 or x < 0 or y < 0 or y > 63:
            return
        x = x + int(128 * int(y / 8))
        y = int(y % 8)
        rb = self.bitMutate[int(x % 7)][y]
        p = int(int(x / 7) * 8 + int(rb / 7))
        if c > 0:
            self.bitmapDisplay[p] |= 1 << int(rb % 7)
        else:
            self.bitmapDisplay[p] &= ~(1 << int(rb % 7))

    def horizontal_line(self, x: int, y: int, w: int):
        for i in range(w):
            self.set_pixel(x, y, 1)
            x += 1

    def vertical_line(self, x: int, y: int, h: int):
        for i in range(h):
            self.set_pixel(x, y, 1)
            y += 1

    def print_at(self, x: int, y: int, str: str):
        self.fnt.print_at(x, y, str, self.set_pixel)


noteHeight = {}


def noteNames():
    for nStr, h in {'C': 0,
                    'Db': 1, 'C#': 1,
                    'D': 2,
                    'Eb': 3, 'D#': 3,
                    'E': 4,
                    'F': 5,
                    'Gb': 6, 'F#': 6,
                    'G': 7,
                    'Ab': 8, 'G#': 8,
                    'A': 9,
                    'Bb': 10, 'A#': 10,
                    'B': 11}.items():
        for i in range(10):
            noteHeight['{}{}'.format(nStr, i)] = h + (i+2) * 12

noteNames()

class ContinuesNoteMap:
    def __init__(self, radio: bool, count: int, inHeight: int, outHeight: int, color: int, unsetcolor: int):
        self.count = count
        self.isRadio = radio
        self.unsetcolor = count * [unsetcolor]
        self.status = count * [0]
        self.baseNotesOut = []
        for i in range(outHeight, outHeight + count):
            self.baseNotesOut.append(i)
        self.colors = count * [color]
        self.baseNotesIn = []
        for i in range(inHeight, inHeight + count):
            self.baseNotesIn.append(i)
        self.lastIndex = None

    def midiIn(self, height: int, setColor, sendMappedNoteOn, sendMappedNoteOff) -> bool:
        try:
            index = self.baseNotesIn.index(height)
            if self.isRadio:
                if self.lastIndex is not None:
                    setColor(self.baseNotesIn[self.lastIndex], self.unsetcolor[self.lastIndex])
                    print("sendMappedNoteOff: {}".format(self.baseNotesOut[self.lastIndex]))
                    sendMappedNoteOff(self.baseNotesOut[self.lastIndex])
                if self.lastIndex!=index:
                    self.lastIndex = index
                    setColor(self.baseNotesIn[index], self.colors[index])
                    print("sendMappedNoteOn: {}".format(self.baseNotesOut[index]))
                    sendMappedNoteOn(self.baseNotesOut[index])
                else:
                    self.lastIndex = None
            else:  # toggle
                self.status[index] = 1 - self.status[index]
                if self.status[index] == 1:
                    setColor(self.baseNotesIn[index], self.colors[index])
                    print("sendMappedNoteOn: {}".format(self.baseNotesOut[index]))
                    sendMappedNoteOn(self.baseNotesOut[index])
                else:
                    setColor(self.baseNotesIn[index], self.unsetcolor[index])
                    print("sendMappedNoteOff: {}".format(self.baseNotesOut[index]))
                    sendMappedNoteOff(self.baseNotesOut[index])
            return True
        except Exception as e:
#            print("exception={}".format(e))
            return False

    def reset(self, unsetColor):
        for i in range(self.count):
            unsetColor(self.baseNotesIn[i], self.unsetcolor[i])

class DamageMap:
    def __init__(self):
        self.triggerNote = ContinuesNoteMap(radio=True, count=44, outHeight=noteHeight['B1'], inHeight=54,
                                           color=0x00FFFF, unsetcolor=0x002020)
        self.triggerEfx = ContinuesNoteMap(radio=False, count=8, outHeight=noteHeight['C6'], inHeight=110,
                                           color=0x8000FF, unsetcolor=0x100020)
        self.ampSequencer = ContinuesNoteMap(radio=True, count=4, outHeight=noteHeight['A6'], inHeight=98,
                                             color=0xFF8888, unsetcolor=0x301010)
        self.ampSeqPreset = ContinuesNoteMap(radio=True, count=6, outHeight=noteHeight['D7'], inHeight=102,
                                             color=0x88FF88, unsetcolor=0x103010)

    def midiIn(self, height: int, setColor, sendMappedNoteOn, sendMappedNoteOff) -> bool:
        if self.triggerNote.midiIn(height, setColor, sendMappedNoteOn, sendMappedNoteOff):
            print('triggerEfx handled')
            return True
        if self.triggerEfx.midiIn(height, setColor, sendMappedNoteOn, sendMappedNoteOff):
            print('triggerEfx handled')
            return True
        if self.ampSequencer.midiIn(height, setColor, sendMappedNoteOn, sendMappedNoteOff):
            print('ampSequencer handled')
            return True
        if self.ampSeqPreset.midiIn(height, setColor, sendMappedNoteOn, sendMappedNoteOff):
            print('ampSeqPreset handled')
            return True
        return False

    def reset(self, setColor):
        self.triggerNote.reset(setColor)
        self.triggerEfx.reset(setColor)
        self.ampSequencer.reset(setColor)
        self.ampSeqPreset.reset(setColor)

class AkaiFireMidiMapper:
    buttons = {
        'VolumeTouch': 16,
        'PanTouch': 17,
        'FilterTouch': 18,
        'ResoTouch': 19,
        'SelectButton': 25,
        'Mode': 26,
        'ChannelRedLeds': 27,
        'PatternUp': 31,
        'PatternDown': 32,  # //1=red
        'Browser': 33,
        'GridLeft': 34,
        'GridRight': 35,
        'SelectUpperRow': 36,
        'Select2ndRow': 37,  # 1=light green 2=bright green
        'Select3rdRow': 38,
        'SelectLowerRow': 39,
        'LedUpperRow': 40,
        'Led2ndRow': 41,  # 1=red 2=green 3=bright red 4=bright green
        'Led3rdRow': 42,
        'LedLowerRow': 43,
        'StepAccent': 44,  # 1=red 2=yellow 3=bright red 4=bright yellow
        'NoteSnap': 45,
        'DrumTap': 46,
        'PerformOverview': 47,
        'Shift': 48,
        'Alt': 49,
        'PatternMetronome': 50,
        'PlayWait': 51,  # 1=light green 2=light yellow 3=green 4=yellow
        'StopCountdown': 52,  # 1=light yellow 2=yellow
        'RecordLoop': 53  # 1=light red  1=light yellow 2=red 3=yellow
    }

    PadButtons = {'RowDown': 102,
                  'Row2': 86,
                  'Row3': 70,
                  'RowUp': 54}

    pots = {'Volume': 16, 'Pan': 17, 'Filter': 18, 'Resonance': 19, 'Select': 118}

    def __init__(self, virtualPortName: str, fontname: str):
        self.fireIn = None
        self.fireOut = None
        self.virtualIn = None
        self.virtualOut = None
        self.display = AkaiFireBitmap(fontname)
        self.map = DamageMap()
        # self.map.midiIn(81,None, None, None)
        while True:
            self.enable_thru(virtualPortName)
            retry_wait = 10
            print("Connection lost, retrying in {} seconds".format(retry_wait))
            time.sleep(retry_wait)

    @staticmethod
    def connectMidiInPort(nameRegEx: str, callback=None):
        ports = mido.get_input_names()
        r = re.compile(nameRegEx)
        for name in ports:
            if r.match(name):
                try:
                    portIn = mido.open_input(name, callback=callback)
                    return portIn
                except Exception as e:
                    print("error connect midi in: {}".format(e))
                    return None
        print("midi in port matching {} not found".format(nameRegEx))

    @staticmethod
    def connectMidiOutPort(nameRegEx: str):
        ports = mido.get_output_names()
        r = re.compile(nameRegEx)
        for name in ports:
            if r.match(name):
                try:
                    portIn = mido.open_output(name)
                    return portIn
                except Exception as e:
                    print("error connect midi out: {}".format(e))
                    return None
        print("midi out port matching {} not found".format(nameRegEx))

    def set_pad_color(self, row: int, column: int, colorRGB: int):
        colData = bytearray([0x47, 0x7f, 0x43, 0x65, 0,
                             4, row * 0x10 + column,
                             (colorRGB >> 17) & 0x7F,
                             (colorRGB >> 9) & 0x7F, (colorRGB >> 1) & 0x7F]);
        colMsg = mido.Message('sysex', data=colData)
        self.fireOut.send(colMsg)

    def exampleScreen(self):
        self.display.print_at(2, 2, "Damage!")
        self.display.vertical_line(0, 32, 32)
        self.display.vertical_line(63, 32, 32)
        self.display.vertical_line(127, 32, 32)
        self.display.horizontal_line(0, 32, 128)
        self.display.horizontal_line(0, 63, 128)
        self.display.show(self.fireOut)

    def setColor(self, note:int, color:int):
        col = int((note - 54) % 16)
        row = int((note - 54) / 16)
        self.set_pad_color(row, col, color)

    def unsetColor(self, note:int):
        self.setColor(note, 0x000000)

    def sendNoteOn(self, note: int):
        print('send note on: {}'.format(note))
        msg = mido.Message('note_on', channel=midiChannelOut, note=note, velocity=120)
        self.virtualOut.send(msg)

    def sendNoteOff(self, note:int):
        print('send note off: {}'.format(note))
        msg = mido.Message('note_on', channel=midiChannelOut, note=note, velocity=0)
        self.virtualOut.send(msg)

    def messageCallbackAkai(self, msg):
        print(msg)
        if msg.type == 'control_change':
            if msg.control == self.pots['Select']:
                if msg.value == 1:
                    self.character += 1
                if msg.value == 127:
                    self.character -= 1
                if self.character < 0:
                    self.character = 0
                if self.character > 255:
                    self.character = 255
                self.display.clear()
                self.display.print_at(10, 10, "{}:{}".format(self.character, chr(self.character)))
                self.display.show(self.fireOut)
        if msg.type == 'note_on':
            if msg.velocity != 0:
                if not self.map.midiIn(msg.note, self.setColor, self.sendNoteOn, self.sendNoteOff):
                    print("not handled, send note")
                    if msg.note in self.buttons.values():
                        msgCol = mido.Message('control_change', control=msg.note, value=self.vals[msg.note])
                        self.vals[msg.note] += 1
                        if self.vals[msg.note] > 10:
                            self.vals[msg.note] = 0
                        self.fireOut.send(msgCol)
                    else:
                        if msg.note >= 54:
                            col = int((msg.note - 54) % 16)
                            row = int((msg.note - 54) / 16)
                            self.vals[msg.note] += 1
                            if self.vals[msg.note] > 1:
                                self.vals[msg.note] = 0
                            self.set_pad_color(row, col, self.vals[msg.note] * 0xffffff)


    def showBeat(self):
        p = int(self.songpos)
        if (p % 24) == 0:
            self.fireOut.send(mido.Message('control_change', control=self.buttons['DrumTap'], value=3))
        if (p % 24) == 2:
            self.fireOut.send(mido.Message('control_change', control=self.buttons['DrumTap'], value=0))

    def messageCallbackVirtual(self, msg):
        if msg.type == 'songpos':
            self.songpos = int(msg.pos) * 6
            print("beat start {}", format(self.songpos))
            self.showBeat()

        if msg.type == 'clock':
            self.songpos += 1
            self.showBeat()

        if msg.type == 'stop':
            self.songpos = None
        print(msg)

    def enable_thru(self, virtualPortName: str):
        fire = 'FL STUDIO FIRE.*'
        self.fireIn = self.connectMidiInPort(fire, self.messageCallbackAkai)
        if self.fireIn is None:
            return
        self.fireOut = self.connectMidiOutPort(fire)
        if self.fireOut is None:
            return

        self.virtualIn = mido.open_input(virtualPortName, virtual=True, callback=self.messageCallbackVirtual)
        if self.virtualIn is None:
            return
        self.virtualOut = mido.open_output(virtualPortName, virtual=True)
        if self.virtualOut is None:
            return

        print("connected {} - {}".format(fire, virtualPortName))
        for row in range(4):
            for col in range(16):
                time.sleep(0.001)
                self.set_pad_color(row, col, 0x000000)
        i = 1
        for height in self.buttons.values():
            msg = mido.Message('control_change', channel=0, control=height, value=0)
            self.fireOut.send(msg)
            i += 1
        self.map.reset(self.setColor)

        msgIsOn = mido.Message('control_change', control=self.buttons['PatternMetronome'], value=1)
        msgIsOff = mido.Message('control_change', control=self.buttons['PatternMetronome'], value=0)
        self.fireOut.send(msgIsOn)
        self.exampleScreen()
        self.character = 50
        self.vals = [0] * 128
        self.songpos = None
        print('Ready')
        try:
            if self.songpos is None:
                cnt = 0
                isOn = False
                while True:
                    cnt += 1
                    if cnt > 10:
                        cnt = 0
                        isOn = not isOn
                        if isOn:
                            self.fireOut.send(msgIsOn)
                        else:
                            self.fireOut.send(msgIsOff)
                    time.sleep(0.05)
            else:
                time.sleep(1)
        except Exception as e:
            print("connection lost", e.what())


if __name__ == '__main__':
    m = AkaiFireMidiMapper('Akai Fire Virtual Mapper', 'fonts/12x16fnt.bin')
