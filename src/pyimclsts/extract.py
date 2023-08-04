'''
    Extracts the IMC schema from a XML file.
'''

from . import extractutils

import xml.etree.ElementTree as ET
import pathlib

import os
import shutil
import argparse

import urllib.request
import ssl

_target_folder = 'pyimc_generated'

unknown_message = '''
class Unknown(_base.base_message):
    \'\'\'A (received) message whose format is not known. It has valid sync number and valid CRC but could not be parsed.

    Contains a byte string field named 'contents' and a boolean value that indicates if its big or little endian.
    On serialization, it forces the original endianess, regardless of what the user chose to use.
    \'\'\'

    __slots__ = ['_Attributes', '_header', '_footer', '_contents', '_endianess']
    Attributes = _base.MessageAttributes(fields = ('contents','endianess', ), name = "Unknown", id = id, abbrev = "Unknown", description = "A (received) message whose format is not known. It has valid sync number and valid CRC but could not be parsed.", ##ATTRIBUTES##)
    contents = _base.mutable_attr({'name': 'Contents', 'type': 'rawdata'}, "contents")
    endianess = _base.mutable_attr({'name': 'endianess', 'type': 'rawdata'}, "endianess")

    def __init__(self, id, contents = None, endianess = None):
        \'\'\'Class constructor
        
        A (received) message whose format is not known. It has valid sync number and valid CRC but could not be parsed.

        This message class contains the following fields and their respective types:
        contents : rawdata, unit: NOT FOUND
        \'\'\'
        self._contents = contents
        self._endianess = endianess
    
    def _pack_fields(self, *, serial_functions : dict) -> bytes:
        raise NotImplemented

    def pack(self, *, is_field_message : bool = False, is_big_endian : bool = True, src : int = None, src_ent : int = None, 
                        dst : int = None, dst_ent : int = None) -> bytes:
        \'\'\'Serialize function that optionally overwrites the header, if parameters are provided.\'\'\'
        
        serial_functions = _core.pack_functions_big if self._endianess else _core.pack_functions_little
        
        s_fields = self._contents
        
        if not is_field_message:
        
            s_header = self._pack_header(serial_functions=serial_functions, size=(len(s_fields)), src=src, src_ent=src_ent, dst=dst, dst_ent=dst_ent)
            s_message = s_header + s_fields
            
            # footer:
            \'\'\'Calculates CRC-16 IBM of a bit string\'\'\'
            self._footer = _core.CRC16IMB(s_message)
            s_message = s_message + serial_functions['uint16_t'](self._footer)

            return s_message
        return serial_functions['uint16_t'](self._Attributes.id) + s_fields

        '''

help_text = '''This script generates files that contain python classes as described in the IMC message schema.

Regardless of the chosen option, minimal will always be generated.

Provide a file as parameter, that contains a list of messages (abbrev's, one per line) to be white- or blacklisted.
'''

minimal = {'Abort', 'EntityState', 'QueryEntityState', 'EntityInfo', 'QueryEntityInfo', 'EntityList', 'EntityActivationState', 'QueryEntityActivationState', 
           'Heartbeat', 'Announce', 'AnnounceService'}

def hardcode_message_extractor(message : dict, templates_namespace : str, message_attributes : set) -> str:
    description = message.get('description', '')
    name = message['abbrev']
    
    namespace =  templates_namespace + '.' if templates_namespace else ''

    ws = '    '

    local_enumeration = []
    priv_attrib = ['_Attributes', '_header', '_footer']
    attributes = []
    mutable_attrib = []
    constructor_args = []
    initialization_values = []

    for attribute in message_attributes:
        
        if attribute in message:
            if attribute == 'fields':
                value = '({},)'.format(', '.join(["'{}'".format(x) for x in message[attribute].keys()]))
            else:
                value = str(message[attribute]) if isinstance(message[attribute], int) else '\"' + message[attribute].replace('"','\\"') + '\"'
        else:
            value = '[]' if attribute == 'fields' else 'None'
        attributes.append(attribute + ' = ' + value)
    
    for field in message.get('fields', []):
        priv_attrib.append('_' + field)
        initialization_values.append(2*ws + 'self.' + priv_attrib[-1] + ' = ' + field + '\n')
        constructor_args.append(field + ' = None')
        
        # All fields' contents are mutable
        field_attr = message['fields'][field]
        description = message['fields'][field].get('description', 'No description available').replace('"','\\"')
        if message['fields'][field].get('unit', None) in ['Enumerated', 'Bitfield']:
            description = description + ' ' + message['fields'][field].get('unit', None)
            if message['fields'][field].get('enum-def', None) or message['fields'][field].get('bitfield-def', None):
                description = description + ' (Global).'
            else:
                description = description + ' (Local).'

        mutable_attrib.append('{ws}{field} = {namespace}mutable_attr({definition}, \"{description}\")\n{ws}\'\'\'{description} Type: {type}\'\'\'\n'.format(
            ws = ws,
            field = field,
            namespace = namespace,
            definition = { k:v for k, v in field_attr.items() if k not in ['description', 'values']},
            description = description,
            type = message['fields'][field]['type']))

        # Determine if its a local declaration of a Enumeration/bitfield
        if (message['fields'][field].get('unit', '') == 'Enumerated' and message['fields'][field].get('enum-def', None) is None):
            
            local_enumeration.append(enum_extractor(message['fields'][field], field.upper() , False)
                                    .replace('\n', '\n' + ws))
        if (message['fields'][field].get('unit', '') == 'Bitfield' and message['fields'][field].get('bitfield-def', None) is None):
            
            local_enumeration.append(enum_extractor(message['fields'][field], field.upper(), True)
                                    .replace('\n', '\n' + ws))

    local_enumeration = ''.join(local_enumeration)
    attributes = ', '.join(attributes)
    mutable_attrib = ''.join(mutable_attrib)
    initialization_values = ''.join(initialization_values)
    constructor_args = ', '.join(constructor_args)

    fields_descriptions = []
    for x in message.get('fields', dict()):
        field_description = ws + x + ' : ' + message['fields'][x].get('type', 'NOT FOUND') + ', unit: ' + message['fields'][x].get('unit', 'NOT FOUND')
        
        if message['fields'][x].get('unit', None) in ['Enumerated', 'Bitfield']:
            if message['fields'][x].get('enum-def', None) or message['fields'][x].get('bitfield-def', None):
                field_description = field_description + ' (Global)'
            else:
                field_description = field_description + ' (Local)'

        fields_descriptions.append(field_description)
    
    description = description + '\n\n       This message class contains the following fields and their respective types:\n' + '\n\n        '.join(fields_descriptions)
    # make nested classes (Enums) immutable too?
    class_def = \
'''
class {name}({namespace}base_message):
    \'\'\'{description}\'\'\'
{local_enum}
    __slots__ = {priv_attrib}
    Attributes = {namespace}MessageAttributes({attributes})

{mutable_attrib}
    def __init__(self, {constructor_args}):
        \'\'\'Class constructor
        
        {description}\'\'\'
{constructor_values}
'''.format(namespace = namespace,
name = name,
description = description,
local_enum = local_enumeration,
priv_attrib = priv_attrib,
attributes = attributes,
mutable_attrib = mutable_attrib, 
constructor_values = initialization_values,
constructor_args = constructor_args)
    
    return class_def

def enum_extractor(enum : dict, name : str, isbitfield : bool) -> str:
    '''Builds an IntEnum or IntFlag from enumerations or bitfields of the XML definition.
    Bitfields are stored as integers of powers of 2 (as expected from the definition).
    
    Obs: Though contrary to the documentation recommendation, we will be setting their
    values to support interoperability with other systems.

    Obs: If it starts with a number, it puts an 'x' at the beginning of the string.
    '''

    ws = '    '
    f_name = enum.get('name', '\"NOT FOUND\"')
    prefix = enum.get('prefix', '\"NOT FOUND\"')

    values = []
    if isbitfield:
        values.append(ws + 'EMPTY = 0\n' + ws + '\'\'\'No active flags\'\'\'\n')
    for value in enum['values']:
        if value[0].isdigit():
            values.append(ws + 'x' + value + ' = ' + str(enum['values'][value]['id']))
        else:
            values.append(ws + value + ' = ' + str(enum['values'][value]['id']))
        values.append(ws + '\'\'\'Name: ' + enum['values'][value]['name'] + '\'\'\'' + '\n')
    
    values = '\n'.join(values)
    parent_class = '_enum.IntFlag' if isbitfield else '_enum.IntEnum'
    enum_def = \
'''
class {name}({parent_class}):
    \'\'\'Full name: {f_name}
    Prefix: {prefix}\'\'\'

{values}
'''.format(name = name, parent_class = parent_class, f_name = f_name, prefix = prefix, values = values)

    return enum_def

def create_init(path):
    generated_files = os.listdir(path)

    file_name = '/__init__.py'
    with open(path + file_name, mode = 'w', encoding='utf-8') as f:
        for name in generated_files:
            if name.find('.py') > 0:
                f.write('from . import {}\n'.format(name[:name.find('.py')]))

if __name__ == '__main__':

    argparser = argparse.ArgumentParser(description=help_text)
    group = argparser.add_mutually_exclusive_group()
    group.add_argument("-w", "--whitelist", help='Messages that will be generated')
    group.add_argument("-b", "--blacklist", help='Messages that will not be generated')
    group.add_argument("-m", "--minimal", action="store_true", help='Generate minimal set only')

    args = argparser.parse_args()

    if args.whitelist is not None or args.blacklist is not None:
        file = args.whitelist if args.whitelist is not None else args.blacklist
        with open(file) as f:
            message_list = {i.strip() for i in f.readlines()}
    elif args.minimal:
        message_list = set()
    
    file = 'IMC.xml'
    try:
        tree = ET.parse(file)
        print(f'Reading {file} from current directory...')
    except FileNotFoundError:
        # Use HTTPS to get IMC.xml file from default repository
        default_repo = 'https://raw.githubusercontent.com/LSTS/imc/master/IMC.xml'
        print(f'Downloading {file} from default repository at {default_repo}.')
        response = urllib.request.urlopen(default_repo, context = ssl.create_default_context())
        IMCxml = response.read()
        print(f'Writing {file}...')
        with open(file, 'wb') as f:
            f.write(IMCxml)
        tree = ET.parse(file)
    
    print('Extracting messages...')

    root = tree.getroot()

    # Split the XML into metadata and messages
    raw_metadata = [x for x in root if x.tag != 'message']
    raw_messages = [x for x in root if x.tag == 'message']

    metadata_encyclopedia = {x.tag : extractutils.recursive_parser(x) for x in raw_metadata}
    metadata_encyclopedia = extractutils.tree_shortener(metadata_encyclopedia,'')

    message_encyclopedia = {int(x.attrib['id']) : extractutils.recursive_parser(x) for x in raw_messages}

    if args.blacklist is not None:
        message_encyclopedia = {k: v for k,v in message_encyclopedia.items() if v['abbrev'] not in [i for i in message_list if i not in minimal]}
    elif args.whitelist is not None or args.minimal:
        message_encyclopedia = {k: v for k,v in message_encyclopedia.items() if v['abbrev'] in message_list.union(minimal)}

    # Automatically built as a list, this key in particular is needed as a dict of lists of ids, but
    # we have to manually reshape/calculate it
    metadata_encyclopedia['categories'] = {cat: [] for cat in metadata_encyclopedia['categories']}
    for (id, msg) in message_encyclopedia.items():
        category = msg.get('category', None)
        metadata_encyclopedia['categories'][category].append((msg.get('id')))
    
    # Hardcode IMC types to python types
    imc_types = dict()
    for t in metadata_encyclopedia['types']['types']:
        # "Deduce" types by their description.
        imc_types[t] =  float if 'float' in metadata_encyclopedia['types']['types'][t]['description'] else \
                        int if 'integer' in metadata_encyclopedia['types']['types'][t]['description'] else \
                        None
    imc_types['rawdata'] = bytes
    imc_types['plaintext'] = str
    imc_types['message'] = '<class \'IMC_message\'>'
    imc_types['message-list'] = list

    # XML variables inspection: Get all possible attributes.
    message_attributes = set()
    for message in message_encyclopedia:
        for attrib in message_encyclopedia[message]:
            message_attributes.add(attrib.replace('-',''))

    fields_attributes = set()
    for message in message_encyclopedia:
        for attrib in message_encyclopedia[message].get('fields', []):
            for child_attrib in message_encyclopedia[message]['fields'][attrib]:
                fields_attributes.add(child_attrib)

    # future flag
    force = True

    if os.path.isdir(_target_folder):
        if os.listdir(_target_folder):
            if force:
                shutil.rmtree(_target_folder)
                os.mkdir(_target_folder)
            else:
                exit('Folder \'{}\' is not empty!'.format(_target_folder))
    else:
        os.mkdir(_target_folder)
    
    os.mkdir(_target_folder + '/categories')

    # Write files
    file_name = 'enumerations.py'
    with open(_target_folder + '/' + file_name, mode = 'w', encoding='utf-8') as f:
        f.write('\'\'\'\nIMC global enumerations definitions.\n\'\'\'\n\n')
        f.write('import enum as _enum\n\n#Enumerations:\n')
        for k, v in metadata_encyclopedia['enumerations'].items():
            f.write(enum_extractor(v, k, False))
    
    file_name = 'bitfields.py'
    with open(_target_folder + '/' + file_name, mode = 'w', encoding='utf-8') as f:
        f.write('\'\'\'\nIMC global bitfields definitions.\n\'\'\'\n\n')
        f.write('import enum as _enum\n\n#Enumerations:\n')
        for k, v in metadata_encyclopedia['bitfields'].items():
            f.write(enum_extractor(v, k, True))
    
    lib_location = pathlib.Path(__file__).parent.resolve()
    file_name = '_base.py'
    with open(str(lib_location) + '/' + file_name, mode = 'r', encoding='utf-8') as f_in:
        base_templates = f_in.read()
        base_templates = base_templates.replace('%SYNCH_NUMBER%', hex(metadata_encyclopedia['header']['fields']['sync']['value']))
        base_templates = base_templates.replace('%IMC_TYPES%', str(imc_types).replace('<class \'', '').replace("'>",'').replace('"',''))
        base_templates = base_templates.replace('%MESSAGE_ATTRIBUTES%', str([s.replace('-','') for s in message_attributes]))

        with open(_target_folder + '/' + file_name, mode = 'w', encoding='utf-8') as f_out:           
            f_out.write(base_templates)

    file_name = 'messages.py'
    with open(_target_folder + '/' + file_name, mode = 'w', encoding='utf-8') as f:
        f.write('\'\'\'\nIMC messages.\n\'\'\'\n\n')
        # write import statements
        f.write('from . import _base\nimport enum as _enum\nimport pyimclsts.core as _core\nfrom . import categories as _categories\n')
        f.write('\n_message_ids = {}\n'.format(str(dict((k, v['abbrev']) for k, v in message_encyclopedia.items()))))
        f.write('\n# Re-export:\nIMC_message = _core.IMC_message\n')
        f.write(unknown_message.replace('##ATTRIBUTES##', ', '.join([i + '= None' for i in message_attributes if i not in {'fields', 'name', 'id', 'abbrev', 'description'}])))

        messages_w_cat = []
        for cat, l in metadata_encyclopedia['categories'].items():
            l_filtered = [x for x in l if x in message_encyclopedia.keys()]
            if l_filtered:
                with open(_target_folder + '/categories/' + cat.replace(' ', '') + '.py', mode = 'w', encoding='utf-8') as f_cat:
                    f_cat.write(f'\'\'\'\nIMC {cat} messages.\n\'\'\'\n\n')
                    # write import statements
                    f_cat.write('from .. import _base\nimport enum as _enum\n')
                    
                    for id in l_filtered:
                        f_cat.write(hardcode_message_extractor(message_encyclopedia[id], '_base', message_attributes))    
                messages_w_cat = messages_w_cat + l_filtered
        
        for k, v in message_encyclopedia.items():
            if k in messages_w_cat:
                f.write('\n\n' + v['abbrev'] + ' = _categories.' + v['category'].replace(' ', '') + '.' + v['abbrev'])
            else:
                f.write(hardcode_message_extractor(v, '_base', message_attributes))
    
    create_init(_target_folder + '/categories')
    create_init(_target_folder)

    # small ugly fix
    with open(_target_folder + '/__init__.py', mode = 'a', encoding='utf-8') as f:
        f.write('from . import categories')

    print('Finished extracting messages.')
