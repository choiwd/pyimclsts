'''
    Contains functions that will be internally used by the IMC binding and are not
    related to the parsing/extract process from the XML file.

    All functions should be "universal" across different versions of IMC.

    Should be a standalone module that depends only on python modules and be
    used as a dependency of higher layers such as _base_templates.py and network.py.

    Obs: There are some "assumptions" here. For example, we assume that the message class
    will have an attribute called '_Attributes', which will have a field called 'fields'.
    Although '_Attributes' is programmatically generated, the field 'fields' is not. It
    is read from IMC definition.
'''

import ifaddr as _ifaddr
import ipaddress as _ipaddress

import struct as _struct
import asyncio as _asyncio

from typing import Any

# be = Big Endian, le = Little Endian

pack_functions_big = {
'int8_t': _struct.Struct('>b').pack,
'uint8_t': _struct.Struct('>B').pack,
'int16_t': _struct.Struct('>h').pack,
'uint16_t': _struct.Struct('>H').pack,
'int32_t': _struct.Struct('>i').pack,
'uint32_t': _struct.Struct('>I').pack,
'int64_t': _struct.Struct('>q').pack,
'fp32_t': _struct.Struct('>f').pack,
'fp64_t': _struct.Struct('>d').pack,
'rawdata': lambda x : _struct.Struct('>H').pack(len(x)) + x,
'plaintext': lambda x : _struct.Struct('>H').pack(len(x)) + x.encode(encoding = 'ascii', errors='surrogateescape'),
'message': lambda x : x.pack(is_field_message=True, is_big_endian=True),
'message-list': lambda x : b''.join([_struct.Struct('>H').pack(len(x)), *[m.pack(is_field_message=True, is_big_endian=True) for m in x]]),
'header': _struct.Struct('>HHHdHBHB').pack # special "type"
}

pack_functions_little = {
'int8_t': _struct.Struct('<b').pack,
'uint8_t': _struct.Struct('<B').pack,
'int16_t': _struct.Struct('<h').pack,
'uint16_t': _struct.Struct('<H').pack,
'int32_t': _struct.Struct('<i').pack,
'uint32_t': _struct.Struct('<I').pack,
'int64_t': _struct.Struct('<q').pack,
'fp32_t': _struct.Struct('<f').pack,
'fp64_t': _struct.Struct('<d').pack,
'rawdata': lambda x : _struct.Struct('<H').pack(len(x)) + x,
'plaintext': lambda x : _struct.Struct('<H').pack(len(x)) + x.encode(encoding = 'ascii', errors='surrogateescape'),
'message': lambda x : x.pack(is_field_message=True, is_big_endian=False),
'message-list': lambda x : b''.join([_struct.Struct('<H').pack(len(x)), *[m.pack(is_field_message=True, is_big_endian=False) for m in x]]),
'header': _struct.Struct('<HHHdHBHB').pack # special "type"
}

unpack_functions_big = {
'int8_t': lambda x : (_struct.Struct('>b').unpack(x[:1])[0], 1),
'uint8_t': lambda x : (_struct.Struct('>B').unpack(x[:1])[0], 1),
'int16_t': lambda x : (_struct.Struct('>h').unpack(x[:2])[0], 2),
'uint16_t': lambda x : (_struct.Struct('>H').unpack(x[:2])[0], 2),
'int32_t': lambda x : (_struct.Struct('>i').unpack(x[:4])[0], 4),
'uint32_t': lambda x : (_struct.Struct('>I').unpack(x[:4])[0], 4),
'int64_t': lambda x : (_struct.Struct('>q').unpack(x[:8])[0], 8),
'fp32_t': lambda x : (_struct.Struct('>f').unpack(x[:4])[0], 4),
'fp64_t': lambda x : (_struct.Struct('>d').unpack(x[:8])[0], 8),
'rawdata': lambda x : (x[2:2 + _struct.Struct('>H').unpack(x[:2])[0]], 2 + _struct.Struct('>H').unpack(x[:2])[0]),
'plaintext': lambda x : (x[2:2 + int.from_bytes(x[:2], byteorder='big')].decode(encoding = 'ascii', errors='surrogateescape'), 2 + int.from_bytes(x[:2], byteorder='big')),
'message': None,
'message-list': None,
'header': lambda x : (_struct.Struct('>HHHdHBHB').unpack(x[:20]), 20), # special "type"
}

unpack_functions_little = {
'int8_t': lambda x : (_struct.Struct('<b').unpack(x[:1])[0], 1),
'uint8_t': lambda x : (_struct.Struct('<B').unpack(x[:1])[0], 1),
'int16_t': lambda x : (_struct.Struct('<h').unpack(x[:2])[0], 2),
'uint16_t': lambda x : (_struct.Struct('<H').unpack(x[:2])[0], 2),
'int32_t': lambda x : (_struct.Struct('<i').unpack(x[:4])[0], 4),
'uint32_t': lambda x : (_struct.Struct('<I').unpack(x[:4])[0], 4),
'int64_t': lambda x : (_struct.Struct('<q').unpack(x[:8])[0], 8),
'fp32_t': lambda x : (_struct.Struct('<f').unpack(x[:4])[0], 4),
'fp64_t': lambda x : (_struct.Struct('<d').unpack(x[:8])[0], 8),
'rawdata': lambda x : (x[2:2 + _struct.Struct('<H').unpack(x[:2])[0]], 2 + _struct.Struct('<H').unpack(x[:2])[0]),
'plaintext': lambda x : (x[2:2 + int.from_bytes(x[:2], byteorder='little')].decode(encoding = 'ascii', errors='surrogateescape'), 2 + int.from_bytes(x[:2], byteorder='little')),
'message': None,
'message-list': None,
'header': lambda x : (_struct.Struct('<HHHdHBHB').unpack(x[:20]), 20) # special "type"
}

crc16_ibm_table_uint = [
      0x0000, 0xC0C1, 0xC181, 0x0140, 0xC301, 0x03C0, 0x0280, 0xC241,
      0xC601, 0x06C0, 0x0780, 0xC741, 0x0500, 0xC5C1, 0xC481, 0x0440,
      0xCC01, 0x0CC0, 0x0D80, 0xCD41, 0x0F00, 0xCFC1, 0xCE81, 0x0E40,
      0x0A00, 0xCAC1, 0xCB81, 0x0B40, 0xC901, 0x09C0, 0x0880, 0xC841,
      0xD801, 0x18C0, 0x1980, 0xD941, 0x1B00, 0xDBC1, 0xDA81, 0x1A40,
      0x1E00, 0xDEC1, 0xDF81, 0x1F40, 0xDD01, 0x1DC0, 0x1C80, 0xDC41,
      0x1400, 0xD4C1, 0xD581, 0x1540, 0xD701, 0x17C0, 0x1680, 0xD641,
      0xD201, 0x12C0, 0x1380, 0xD341, 0x1100, 0xD1C1, 0xD081, 0x1040,
      0xF001, 0x30C0, 0x3180, 0xF141, 0x3300, 0xF3C1, 0xF281, 0x3240,
      0x3600, 0xF6C1, 0xF781, 0x3740, 0xF501, 0x35C0, 0x3480, 0xF441,
      0x3C00, 0xFCC1, 0xFD81, 0x3D40, 0xFF01, 0x3FC0, 0x3E80, 0xFE41,
      0xFA01, 0x3AC0, 0x3B80, 0xFB41, 0x3900, 0xF9C1, 0xF881, 0x3840,
      0x2800, 0xE8C1, 0xE981, 0x2940, 0xEB01, 0x2BC0, 0x2A80, 0xEA41,
      0xEE01, 0x2EC0, 0x2F80, 0xEF41, 0x2D00, 0xEDC1, 0xEC81, 0x2C40,
      0xE401, 0x24C0, 0x2580, 0xE541, 0x2700, 0xE7C1, 0xE681, 0x2640,
      0x2200, 0xE2C1, 0xE381, 0x2340, 0xE101, 0x21C0, 0x2080, 0xE041,
      0xA001, 0x60C0, 0x6180, 0xA141, 0x6300, 0xA3C1, 0xA281, 0x6240,
      0x6600, 0xA6C1, 0xA781, 0x6740, 0xA501, 0x65C0, 0x6480, 0xA441,
      0x6C00, 0xACC1, 0xAD81, 0x6D40, 0xAF01, 0x6FC0, 0x6E80, 0xAE41,
      0xAA01, 0x6AC0, 0x6B80, 0xAB41, 0x6900, 0xA9C1, 0xA881, 0x6840,
      0x7800, 0xB8C1, 0xB981, 0x7940, 0xBB01, 0x7BC0, 0x7A80, 0xBA41,
      0xBE01, 0x7EC0, 0x7F80, 0xBF41, 0x7D00, 0xBDC1, 0xBC81, 0x7C40,
      0xB401, 0x74C0, 0x7580, 0xB541, 0x7700, 0xB7C1, 0xB681, 0x7640,
      0x7200, 0xB2C1, 0xB381, 0x7340, 0xB101, 0x71C0, 0x7080, 0xB041,
      0x5000, 0x90C1, 0x9181, 0x5140, 0x9301, 0x53C0, 0x5280, 0x9241,
      0x9601, 0x56C0, 0x5780, 0x9741, 0x5500, 0x95C1, 0x9481, 0x5440,
      0x9C01, 0x5CC0, 0x5D80, 0x9D41, 0x5F00, 0x9FC1, 0x9E81, 0x5E40,
      0x5A00, 0x9AC1, 0x9B81, 0x5B40, 0x9901, 0x59C0, 0x5880, 0x9841,
      0x8801, 0x48C0, 0x4980, 0x8941, 0x4B00, 0x8BC1, 0x8A81, 0x4A40,
      0x4E00, 0x8EC1, 0x8F81, 0x4F40, 0x8D01, 0x4DC0, 0x4C80, 0x8C41,
      0x4400, 0x84C1, 0x8581, 0x4540, 0x8701, 0x47C0, 0x4680, 0x8641,
      0x8201, 0x42C0, 0x4380, 0x8341, 0x4100, 0x81C1, 0x8081, 0x4040]

def CRC16IMB(message : bytes) -> int:
    result = 0
    for m in message:
            result = (result >> 8) ^ crc16_ibm_table_uint[((result ^ m) & 0xFF)]
    return result

def get_initial_IP() -> int:
    '''Returns the 1st non-localhost IPv4 if it exists. Else, returns localhost
    
    obs: Returns as int.
    '''
    ipv4_list = [IP.ip for interface in _ifaddr.get_adapters() for IP in interface.ips if isinstance(IP.ip, str)]
    
    for ip in ipv4_list:
        if ip != '127.0.0.1':
            return int(_ipaddress.IPv4Address(ip))
    return int(_ipaddress.IPv4Address('127.0.0.1'))

async def _async_wrapper(func, *args) -> Any:
    return func(*args)

class IMC_message():
    '''IMC message parent/root class.'''
    __slots__ = []
    
    '''Empty message to break circular reference.

    Initially, there was 'base_message' and the descriptor 'mutable_attr', which contained a reference
    to a dictionary 'imc_types' that pointed back to base message. This is/was necessary to allow type 
    checking a message whose field may contain other messages, that is, the message class must have a
    descriptor object (as per protocol) and to check if it is of type 'message', it must have a reference 
    to the 'message' class. However, this leads to the cyclic reference:
            
            'base_message' -> descriptor -> dictionary -> 'base_message'.
    
    Although python may be able to handle circular references, we choose not to.

    Therefore, to circumvent this issue, an empty message is added to break this cycle.
            'IMC_message' <- base_message -> descriptor
            'IMC_message' <- dictionary   <- descriptor
    
    Because a parent class does not point to its child classes, there is no cycle.
    '''
    pass

class base_IO_interface:
    '''
        An 'abstract'* class that describes the basic implementation of an I/O interface.

        * Not really abstract as in Java, but consider it so. 
        I will not use abc and its decorators.
    '''
    __slots__ = ['_input', '_output', '_o', '_i']

    def __init__(self, input : Any = None, output : Any = None) -> None:
        self._input = input
        self._output = output

    async def open(self) -> None:
        raise NotImplementedError
    
    async def read(self, n_bytes : int) -> bytes:
        raise NotImplementedError
        
    async def write(self, byte_string : bytes) -> None:
        raise NotImplementedError
    
    async def close(self) -> None:
        raise NotImplementedError

class file_interface(base_IO_interface):
    '''
        A minimal implementation of a file interface. Receives an input
        file name and (optionally) an output file name, to which it appends.
    '''
    __slots__ = ['_input', '_output', '_o', '_i']

    def __init__(self, input : Any = None, output : Any = None) -> None:
        self._input = input
        self._output = output

    async def open(self) -> None:
        self._o = open(self._output, 'ab') if self._output is not None else None
        self._i = open(self._input, 'rb')
    
    async def read(self, n_bytes : int) -> bytes:
        r = self._i.read(n_bytes)
        if r == b'':
            raise EOFError('End of File reached')
        return r
        
    async def write(self, byte_string : bytes) -> None:
        if self._o is not None:
            self._o.write(byte_string)
    
    async def close(self) -> None:
        if self._o is not None:
            self._o.close()
        self._i.close()

class tcp_interface(base_IO_interface):
    '''
        A minimal implementation of a TPC interface. It wraps a
        connection established with the asyncio module.
    '''
    __slots__ = ['_ip', '_port', '_reader', '_writer']

    def __init__(self, ip : str, port : int) -> None:
        self._ip = ip
        self._port = port

    async def open(self) -> None:
        self._reader, self._writer = await _asyncio.open_connection(self._ip, self._port)
    
    async def read(self, n_bytes : int) -> bytes:
        r = await self._reader.read(n_bytes)
        if r == b'':
            raise EOFError('Connection returned empty byte string')
        return r
        
    async def write(self, byte_string : bytes) -> None:
        self._writer.write(byte_string)
        await self._writer.drain()
    
    async def close(self) -> None:
        self._writer.close()
        await self._writer.wait_closed()
