from enum import Enum
import threading
import select
import socket
import struct


mutex = threading.RLock()


class MessageType(Enum):
    JOIN_ROOM = 1
    CREATE_ROOM = 2
    LEAVE_ROOM = 3
    LIST_ROOMS = 4
    CONTENT = 5
    CLEAR_CONTENT = 6
    DELETE_ROOM = 7
    CLEAR_ROOM = 8
    LIST_ROOM_CLIENTS = 9
    LIST_CLIENTS = 10
    COMMAND = 100
    TRANSFORM = 101
    DELETE = 102
    MESH = 103
    MATERIAL = 104
    CAMERA = 105
    LIGHT = 106
    MESHCONNECTION = 107
    RENAME = 108
    DUPLICATE = 109
    SEND_TO_TRASH = 110
    RESTORE_FROM_TRASH = 111
    TEXTURE = 112

class LightType(Enum):
    SPOT = 0 # directly mapped from Unity enum
    SUN = 1
    POINT = 2

class SensorFitMode(Enum):
    AUTO = 0
    VERTICAL = 1
    HORIZONTAL = 2

class ClientDisconnectedException(Exception):
    '''When a client is disconnected and we try to read from it.'''

def intToBytes(value, size = 8):
    return value.to_bytes(size, byteorder='little')

def bytesToInt(value):
    return int.from_bytes(value, 'little')

def intToMessageType(value):
    return MessageType(value)

def encodeBool(value):
    if value:        
        return intToBytes(1, 4)
    else:
        return intToBytes(0, 4)

def decodeBool(data, index):
    value = bytesToInt(data[index:index+4])
    if value == 1:
        return True, index+4
    else:
        return False, index+4

def encodeString(value):
    encodedValue = value.encode()
    return intToBytes(len(encodedValue),4) + encodedValue

def decodeString(data, index):
    stringLength = bytesToInt(data[index:index+4])
    start = index+4
    end = start+stringLength
    value = data[start:end].decode()
    return value, end

def encodeFloat(value):
    return struct.pack('f', value)

def decodeFloat(data, index):
    return struct.unpack('f', data[index:index+4])[0], index+4

def encodeInt(value):
    return struct.pack('I', value)

def decodeInt(data, index):
    return struct.unpack('I', data[index:index+4])[0], index+4

def encodeVector2(value):
    return struct.pack('2f', *(value.x, value.y))

def decodeVector2(data, index):
    return struct.unpack('2f', data[index:index+2*4]), index+2*4

def encodeVector3(value):
    return struct.pack('3f', *(value.x, value.y, value.z))

def decodeVector3(data, index):
    return struct.unpack('3f', data[index:index+3*4]), index+3*4

def encodeColor(value):
    if len(value) == 3:
        return struct.pack('4f', *(value[0], value[1], value[2], 1.0))
    else:
        return struct.pack('4f', *(value[0], value[1], value[2], value[3]))

def decodeColor(data, index):
    return struct.unpack('4f', data[index:index+4*4]), index+4*4

def encodeVector4(value):
    return struct.pack('4f', *(value.x, value.y, value.z, value.w))

def decodeVector4(data, index):
    return struct.unpack('4f', data[index:index+4*4]), index+4*4

def encodeStringArray(values):
    buffer = encodeInt(len(values))
    for item in values:
        buffer += encodeString(item)
    return buffer

def decodeStringArray(data, index):
    count = bytesToInt(data[index:index+4])
    index = index + 4
    values = []
    for _ in range(count):
        string, index  = decodeString(data, index)
        values.append(string)
    return values, index

def decodeArray(data, index, schema, inc):
    count = bytesToInt(data[index:index+4])
    start = index+4
    end = start
    values = []
    for _ in range(count):
        end = start+inc
        values.append(struct.unpack(schema, data[start:end]))
        start = end
    return values, end

def decodeFloatArray(data, index):
    return decodeArray(data, index, 'f', 4)

def decodeIntArray(data, index):
    count = bytesToInt(data[index:index+4])
    start = index+4
    values = []
    for _ in range(count):
        end = start+4
        values.extend(struct.unpack('I', data[start:end]))
        start = end
    return values, end

def decodeInt2Array(data, index):
    return decodeArray(data, index, '2I', 2*4)

def decodeInt3Array(data, index):
    return decodeArray(data, index, '3I', 3*4)

def decodeVector3Array(data, index):
    return decodeArray(data, index, '3f', 3*4)

def decodeVector2Array(data, index):
    return decodeArray(data, index, '2f', 2*4)

def readMessage(socket):
    if not socket:
        return None
    r,_,_ = select.select([socket],[],[],0.0001)
    if len(r) > 0:
        try:
            msg = socket.recv(14)
            if len(msg) < 14:
                raise ClientDisconnectedException()
            frameSize = bytesToInt(msg[:8])
            commandId = bytesToInt(msg[8:12])
            messageType = bytesToInt(msg[12:])
            currentSize = frameSize
            msg = b''
            while currentSize != 0:
                tmp = socket.recv(currentSize)
                msg += tmp
                currentSize -= len(tmp)
            return Command(intToMessageType(messageType), msg, commandId)

        except ClientDisconnectedException:
            raise
        except Exception as e:
            print (e)
            raise ClientDisconnectedException()

    return None

def writeMessage(socket, command):
    if not socket:
        return
    size = intToBytes(len(command.data),8)
    commandId = intToBytes(command.id,4)
    mtype = intToBytes(command.type.value,2)

    buffer = size + commandId + mtype + command.data
    remainingSize = len(buffer)
    currentIndex = 0
    while remainingSize > 0:
        _,w,_ = select.select([],[socket],[],0.0001)
        if len(w) > 0:
            sent = socket.send(buffer[currentIndex:])
            remainingSize -= sent
            currentIndex += sent


class Command:
    _id = 100
    def __init__(self, commandType, data = b'', commandId = 0):
        self.data = data or b''
        self.type = commandType
        self.id = commandId
        if commandId == 0:
            self.id = Command._id
            Command._id += 1
