import copy
from enum import IntEnum, IntFlag
from collections import namedtuple
import time

import pyimclsts.core as core
from . import enumerations as imc_enums
from . import bitfields as imc_bitf

'''
Implementation of mutable and immutable types

Considered operations to be protected:
    - Assignment;
        - Attributes should not be re-assigned to invalid types
    - Access (getter);
        - Reference leakage (when a reference to a mutable object is inadvertently exposed)
    - Initialization.
        - Attributes should not be initialized with invalid types
    - Dynamic creation of attributes
        - Attributes should not be created/added to the module classes (Even if this is not
        dangerous per se, this might induce programming errors)
'''

# "Global" definitions
header_data = namedtuple('header_data', ['sync', 'mgid', 'size', 'timestamp', 'src', 'src_ent', 'dst', 'dst_ent'])
MessageAttributes = namedtuple('MessageAttributes', %MESSAGE_ATTRIBUTES%)

# "Global" variables
_sync_number = %SYNCH_NUMBER%
_default_src = 0x4000 | (core.get_initial_IP() & 0xFFFF)

# "Re-exporting" from core
IMC_message = core.IMC_message

imc_types = %IMC_TYPES%

class base_message(IMC_message):
    
    __slots__ = ['_header', '_footer', 'Attributes']

    def __str__(self) -> str:
        output = ['Message \'' + self.Attributes.name + '\':', 'Fields:']
        for field in self.Attributes.fields:
            value = getattr(self, field)
            if value is not None:
                if type(value) == str:
                    value = '\'' + value + '\''
                
                #Check whether it is an Enumerated type
                elif getattr(getattr(type(self), field), '_field_def').get('unit', None) in ['Enumerated', 'Bitfield']:
                    # check whether the Enum was "validated" by the descriptor
                    if isinstance(value, IntEnum) or isinstance(value, IntFlag):
                        enum_def = getattr(getattr(type(self), field), '_field_def').get('enum-def', None) if getattr(getattr(type(self), field), '_field_def').get('enum-def', None) \
                            else getattr(getattr(type(self), field), '_field_def').get('bitfield-def', None)
                        
                        # check whether it is local or global
                        if not enum_def:
                            value = self.Attributes.abbrev + '.' + str(value)
                        else:
                            value = str(value)
                    else:
                        value = str(value)

                elif isinstance(value, IMC_message):
                    value = ('\n' + str(value)).replace('\n', '\n    ')
                elif type(value) == list:
                    value = ('\n[\n' + '\n'.join([str(v) for v in value]) + '\n]').replace('\n', '\n    ')
                else:
                    value = str(value)
            else:
                value = 'None'

            output.append('  - ' + field + " = " + value)
        output = '\n'.join(output)
        if hasattr(self, '_header'):
            output = repr(self._header) + '\n' + output
        return output

    def __repr__(self) -> str:
        arguments = []
        for field in self.Attributes.fields:
            value = getattr(self, field)            
            if value is not None:
                #Check whether it is an Enumerated type
                if getattr(getattr(type(self), field), '_field_def').get('unit', None) in ['Enumerated', 'Bitfield']:
                    # check whether the Enum was "validated" by the descriptor
                    if isinstance(value, IntEnum) or isinstance(value, IntFlag):
                        enum_def = getattr(getattr(type(self), field), '_field_def').get('enum-def', None) \
                            if getattr(getattr(type(self), field), '_field_def').get('enum-def', None) \
                            else getattr(getattr(type(self), field), '_field_def').get('bitfield-def', None)

                        # check whether it is local or global
                        if enum_def:
                            value = str(value)
                        else:
                            value = self.Attributes.abbrev + '.' + str(value)
                    else:
                        value = repr(value)
                else:
                    value = repr(value)
            else:
                value = 'None'

            arguments.append(field + " = " + value)
        arguments = ', '.join(arguments)
        output = self.Attributes.abbrev + '({})'.format(arguments)
        return output

    def __eq__(self, __o: object) -> bool:
        if isinstance(__o, base_message):
            # if both of them have already defined a '_header'
            if hasattr(self, '_header') and hasattr(__o, '_header'):
                if self._header != __o._header:
                    return False
            # if any of them does not have '_header' -> happens when a message is 
            # inside another, I'll skip and check the contents
            
            if hasattr(self, '_header') and hasattr(__o, '_header'):
                if self._header != __o._header:
                    return False
            fields = self.Attributes.fields
            if any([getattr(self, field) != getattr(__o, field) for field in fields]):
                return False
            return True
        return False

    def _pack_fields(self, *, serial_functions : dict) -> bytes:
        # Check if any field is empty (None) and not type 'message' (checked through the descriptor)
        if any([getattr(self, '_' + field) is None for field in self.Attributes.fields if getattr(getattr(type(self), field), '_field_def').get('type', None) != 'message']):
            raise ValueError('Cannot serialize a message that contains an empty (NoneType) field that is not a message.')
        
        serial_functions = serial_functions

        serialized_fields = []
        for field in self.Attributes.fields:
            # Access variable information through the descriptor
            datatype = getattr(getattr(type(self), field), '_field_def').get('type', None)
            
            # check if it is a "NULL" message
            if datatype == 'message' and getattr(self, '_' + field) is None:
                serialized_fields.append(serial_functions['uint16_t'](65535))
            else:
                serialized_fields.append(serial_functions[datatype](getattr(self, '_' + field)))
        
        return b''.join(serialized_fields)

    def _pack_header(self, *, serial_functions : dict, size : int, src : str = None, src_ent : str = None, dst : str = None, dst_ent : str = None) -> bytes:
        '''Gathers necessary builds the header, stores it in the private variable '_header' and returns the bit string.
        
        The tricky part is: Are the header fields fixed or not, that is, they should be hardcoded or not?
        There may be mutability on their: 1. existence; 2, name; 3. order; 4. type (and size).
        
        We will assume that only 4. can change.
            - As a result a namedTuple is globally defined.'''

        mgid = self.Attributes.id

        # If None or a "default" value, overwrite
        if not hasattr(self, '_header'):
            _timestamp = time.time()
            _src = src if src is not None else _default_src
            _src_ent = src_ent if src_ent is not None else 0xFF
            _dst = dst if dst is not None else 0xFFFF
            _dst_ent = dst_ent if dst_ent is not None else 0xFF
        else:
            _timestamp = self._header.timestamp
            _src = src if src is not None else self._header.src
            _src_ent = src_ent if src_ent is not None else self._header.src_ent
            _dst = dst if dst is not None else self._header.dst
            _dst_ent = dst_ent if dst_ent is not None else self._header.dst_ent
        
        header_fields_values = header_data(sync=_sync_number, mgid=mgid, size=size, timestamp=_timestamp, src=_src, src_ent=_src_ent, dst=_dst, dst_ent=_dst_ent)
        
        self._header = header_fields_values

        return serial_functions['header'](*self._header)
    
    def pack(self, *, is_field_message : bool = False, is_big_endian : bool = True, src : int = None, src_ent : int = None, 
                        dst : int = None, dst_ent : int = None) -> bytes:
        '''Serialize function that optionally overwrites the header, if parameters are provided.'''
        
        serial_functions = core.pack_functions_big if is_big_endian else core.pack_functions_little
        
        s_fields = self._pack_fields(serial_functions=serial_functions)
        
        if not is_field_message:
        
            s_header = self._pack_header(serial_functions=serial_functions, size=(len(s_fields)), src=src, src_ent=src_ent, dst=dst, dst_ent=dst_ent)
            s_message = s_header + s_fields
            
            # footer:
            '''Calculates CRC-16 IBM of a bit string'''
            self._footer = core.CRC16IMB(s_message)
            s_message = s_message + serial_functions['uint16_t'](self._footer)

            return s_message
        return serial_functions['uint16_t'](self.Attributes.id) + s_fields

    def get_timestamp(self) -> float:
        '''Get the timestamp. Returns None if the message has no header yet.'''
        if hasattr(self, '_header'):
            return self._header.timestamp
        return None
    
class immutable_attr():
    '''Describes an immutable attribute. The type should be already known at run time, that is,
    included in the class attribute definition of the message (and therefore, it does not need
    to be type checked).
    Additionally, to prevent accidental modification of python mutable types, which may lead to 
    an inconsistent state, it checks whether the attribute is of a immutable type before 
    returning the (reference of) the desired object and if the object is mutable, it returns a 
    deep copy.'''

    def __init__(self, doc : str) -> None:
        self.__doc__ = doc

    def __set_name__(self, owner : any, name : str):
        self._name = '_' + name

    def __get__(self, instance : any, owner : any):
        if instance is None: #some hacky thing to allow docstrings
            return self

        if isinstance(getattr(instance, self._name), (int, float, str, bool, tuple)):
            return getattr(instance, self._name)
        else:
            return copy.deepcopy(getattr(instance, self._name))

    def __set__(self, owner : any, value : any):
        raise AttributeError('Attribute \'{}\' of {} cannot be modified'.format(self._name, type(owner)))
    
    def __delete__(self, __name: str) -> None:
        raise NotImplementedError

class mutable_attr():
    '''Describes a mutable attribute. The type should be already known at run time, that is,
    included in the class attribute definition of the message.
    Additionally, to prevent accidental modification of python mutable types, which may lead to 
    an inconsistent state, it checks whether the attribute is of a immutable type before 
    returning the (reference of) the desired object and if the object is mutable, it returns a 
    deep copy (new and different reference).
    Since it can still be re-assigned, it will be type checked when this operation is carried out.

    Realization: Inside a message: all attributes are immutable, fields attributes are immutable
    fields contents are mutable.
    
    Also, there is no pythonic way of *prohibiting* (ex: type checker) the assignment of a wrong 
    type, which means it *will* fail. So, failure at the descriptor or failure at the packing 
    step... Are failures/exceptions during runtime either way => bad. I'll leave this implementation
    anyway, since this might give better error messages, but it is, all in all, pointless.
    '''

    def __init__(self, field_def : dict, doc : str) -> None:
        self._field_def = field_def
        self.__doc__ = doc

    def __set_name__(self, owner : any, name : str):
        self._priv_name = '_' + name
        self._owner = owner

    def __get__(self, instance : any, owner : any):
        if instance is None: #some hacky thing to allow docstrings
            return self

        # return bare attribute if it is immutable.
        if isinstance(getattr(instance, self._priv_name), (int, float, str, bool, tuple)):
            return getattr(instance, self._priv_name)
        else:
            return copy.deepcopy(getattr(instance, self._priv_name))

    def __set__(self, obj : any, value : any) -> None:
        '''Performs type and boundary checks and throws exceptions'''
        set_value = value
        attribute_type = imc_types.get(self._field_def.get('type', None), None)

        if not attribute_type:
            raise KeyError('Could not find a type declaration for {} in given IMC definition'.format(self._priv_name[1:]))

        # Special and only case of upcasting internally allowed.
        if isinstance(set_value, int) and attribute_type == float:
            set_value = float(set_value)

        if isinstance(set_value, attribute_type):
            '''Obs: Should type casting be implemented? eg.: float -> int
            Type casting/coersion will not be implemented to avoid reinforcing bad
            pratices and increase transparency.
            
            On a 2nd thought, we may allow SOME upcasting, in particular, int -> float'''
            
            # if it is a list, check its elements types.
            if isinstance(set_value, imc_types['message-list']):
                
                for t in set_value:
                    # Check data type
                    if not isinstance(t, imc_types['message']):
                        raise ValueError('Cannot assign {} to attribute \'{}\'. Expected: {} of {}'.format(
                        type(t), self._priv_name[1:], imc_types[self._field_def['type']], 
                        imc_types['message']))
                    
                    # (I have to check the message group?)
                    # Check message-type 
                    if  self._field_def.get('message-type', None) is not None \
                                    and t.Attributes.abbrev != self._field_def.get('message-type', None):
                        raise ValueError('Cannot have {} in the list of attribute \'{}\'. Expected: {} of messages of type \'{}\''.format(
                        type(t), self._priv_name[1:], imc_types[self._field_def['type']],
                        self._field_def.get('message-type', None)))

            # if it is field, check its validity, according to the IMC XML:
            if 'min' in self._field_def:
                if set_value < self._field_def['min']:
                    raise ValueError('The minimum value for attribute {} is {}. Cannot assign {}.'.format(
                        self._priv_name[1:], self._field_def['min'], set_value
                    ))

            if 'max' in self._field_def:
                if set_value > self._field_def['max']:
                    raise ValueError('The maximum value for attribute \'{}\' is {}. Cannot assign {}.'.format(
                        self._priv_name[1:], self._field_def['max'], set_value
                    ))
            
            # Check if its enumerated or bitfield
            if self._field_def.get('unit', None) == 'Enumerated':
                # Tries to get definition from the owner class. If 'enum-def' exists, it refers to a 
                # global definition; returns None, otherwise
                enum_def = self._field_def.get('enum-def', None) 
                
                # if it is global, get class from file. Else, get definition from owner class
                enum_def = getattr(imc_enums, enum_def) if enum_def else getattr(self._owner, self._priv_name[1:].upper())

                set_value = enum_def(set_value)

            if self._field_def.get('unit', None) == 'Bitfield':
                bitdef = self._field_def.get('bitfield-def', None)
                
                bitdef = getattr(imc_bitf, bitdef) if bitdef else getattr(self._owner, self._priv_name[1:].upper())

                set_value = bitdef(set_value)

            # check the size (or crop the object at serialization?)
            setattr(obj, self._priv_name, set_value)
        else:
            raise AttributeError('Cannot assign {} to {}. Expected: {}'.format(
                type(set_value), self._priv_name[1:], imc_types[self._field_def['type']]))
