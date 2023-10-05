'''
    Contains functions to help develop/build the IMC binding, but are not used
    after the binding is complete.
'''

from typing import Any
import xml.etree.ElementTree as ET

def recursive_parser(element) -> dict:
    #print(element.attrib.get('id', None))
    node = {}
    if element.tag == 'description':
        # Check if it is empty... It happens =/
        if element.text:  # not empty
            # Clean the string (remove double whitespaces and line breaks)
            node[element.tag] = " ".join(element.text.split())
        else:
            node[element.tag] = ""
        return node

    # Operation over every node
    for a in element.attrib:
        if element.attrib[a].isdigit() or element.attrib[a].startswith('0x'):
            node[a] = int(element.attrib[a], 0)
        else:
            try: # Jesus Christ, forgive me for I have sinned
                node[a] = float(element.attrib[a])
            except ValueError:
                node[a] = element.attrib[a]
            
    # if the tag of child node belongs to a dummy_tag, merge them 
    # into the parent's name key (xml tag), preserving each entry
    children = []
    for child in element:
        if child.tag == 'description':
            # Check if it is empty... It happens =/
            if child.text: # not empty
                # Clean the string (remove double whitespaces and line breaks)
                node[child.tag] = " ".join(child.text.split())
            else:
                node[child.tag] = ""
        else:
            children.append(recursive_parser(child))

    # make a dictionary indexed by the abbrev or the name of the attributes
    dict_children = {}
    for child in children:
        key = child.get('abbrev', None)
        if not key:
            name = child.get('name', None)
            del child['name']
        else:
            name = child.get('abbrev', None)
            del child['abbrev']
        
        dict_children[name] = child
        
    # if the children values are empty, use a list instead
    if not all(dict_children.values()):
        dict_children = list(dict_children)

    # check if its an empty list to avoid having an empty key
    if dict_children:
        # fetch the common tag among the children. (They are always(?) the same, except for 'description')
        new_tag = list(filter(lambda x : x.tag != 'description', list(element)))[0].tag
        node[new_tag + 's'] = dict_children     # shameless exploit of English morphology
        #node[element.tag] = dict_children

    return node

def recursive_print(node : dict, ws : str = '' ) -> None:
    ws_ = "  " + ws
    for key in node.keys():
        if isinstance(node[key], dict):
            print(ws_ + str(key) + ' : ')
            recursive_print(node[key], ws_)
        else:
            print(ws_ + key + ' : ' + str(node[key]))

def tree_shortener(tree : dict, name : Any) -> dict:
    '''Removes tree levels that consists of a single node.'''
    new_tree = dict()

    if isinstance(tree, dict):
        if len(tree) == 1:
            key = list(tree.keys())[0]
            
            if key == 'description': # leave this one untouched.
                return tree

            new_tree = tree[key]
            return new_tree
        
        for (key, value) in tree.items():
            new_tree[key] = tree_shortener(value, key)
    else:
        return tree

    return new_tree

if __name__ == '__main__':
    file = 'IMC.xml'

    tree = ET.parse(file)
    root = tree.getroot()

    # Split the XML into metadata and messages
    raw_metadata = [x for x in root if x.tag != 'message']
    raw_messages = [x for x in root if x.tag == 'message']

    # test variables
    x = raw_metadata[1]
    y = x[1]

    metadata_encyclopedia = {x.tag : recursive_parser(x) for x in raw_metadata}
    message_catalog = {int(x.attrib['id']) : recursive_parser(x) for x in raw_messages}

    recursive_print(message_catalog[1])
    recursive_print(metadata_encyclopedia['types'])
    d = filter(lambda x: x['id'] == 552, message_catalog)