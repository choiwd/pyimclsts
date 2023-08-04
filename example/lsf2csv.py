import pyimclsts.network as n
import pyimc_generated as pg

import base64
import json

csv_delimiter = '\x01'#'; '
json_delimiter = ', '

# \copy lauvxplore1 from 'output.csv' delimiter E'\x01';

# Jesus Christ, it's become so difficult/ugly to program outside of Haskell...
def tojson(msg_or_value) -> str:
    if isinstance(msg_or_value, pg._base_templates.base_message):
        fields = msg_or_value.Attributes.fields
        values = [tojson(getattr(msg_or_value, f)) for f in fields]
        
        msg_id = f'"Message id" : {msg_or_value.Attributes.id}'

        json_string = json_delimiter.join([msg_id] + [f'"{field}" : {value}' for field, value in zip(fields, values)])
        
        return '{' + json_string + '}' 
    elif isinstance(msg_or_value, list):
        return '[' + json_delimiter.join([tojson(i) for i in msg_or_value]) + ']'
    elif isinstance(msg_or_value, int) or isinstance(msg_or_value, float):
        return str(msg_or_value)
    elif isinstance(msg_or_value, bytes):
        if msg_or_value != b'':
            return f'"{str(base64.b64encode(msg_or_value), encoding="ascii")}"'
        else:
            return 'null'
    else: # plaintext. Remove single quotation marks ('), re-escape escape characters, escape (")
        if msg_or_value:
            #x = repr(json.dumps(msg_or_value.encode("ascii", errors="surrogateescape").decode())[1:-1])[1:-1]
            #return f'"{x}"'
            # convert plaintext to its binary representation, then to its base64 rep.
            # Too much of a hassle to escape characters and deal with invalid ASCII.
            return f'"{str(base64.b64encode(msg_or_value.encode("ascii", errors="surrogateescape")), encoding="ascii")}"'
        else:
            return "null"

def todict(msg_or_value) -> dict:
    if isinstance(msg_or_value, pg._base_templates.base_message):
        fields = list(msg_or_value.Attributes.fields)
        values = [todict(getattr(msg_or_value, f)) for f in fields]
        
        json_dict = { f : v for f, v in zip(["Message id"] + fields, [msg_or_value.Attributes.id] + values) }
        
        return json_dict
    elif isinstance(msg_or_value, list):
        return [todict(i) for i in msg_or_value]
    elif isinstance(msg_or_value, bytes):
        return str(base64.b64encode(msg_or_value), encoding="ascii")
    else:
        return msg_or_value

class writer():
    
    def __init__(self, f : str, b_size : int) -> None:
        '''f is file name, b_size is buffer size in bytes'''

        self.file_name = f
        # erases the file if it exists, creates it otherwise
        with open(f, 'w'):
            pass
        self.buffer_max_size = b_size
        self.buffer = []

        self.buffer_size = 0
    
    def write(self, s : str) -> None:
        self.buffer.append(s)
        self.buffer_size += len(s)

        if self.buffer_size > self.buffer_max_size:
            with open(self.file_name, 'a') as f:
                f.write('\n'.join(self.buffer) + '\n')
                self.buffer = []
                self.buffer_size = 0
            
    def writetocsv(self, msg, callback) -> str:
        # Note: removed sync number. Size kept?
        header = csv_delimiter.join([str(i) for i in list(msg._header)[1:]])
        
        json_string = tojson(msg)
        self.write(header + csv_delimiter + json_string)
    
    def flush(self):
        with open(self.file_name, 'a') as f:
            f.write('\n'.join(self.buffer))
            self.buffer = []
            self.buffer_size = 0

class writer2():
    
    def __init__(self, f : str, b_size : int) -> None:
        '''f is file name, b_size is buffer size in bytes'''

        self.file_name = f
        # erases the file if it exists, creates it otherwise
        with open(f, 'w'):
            pass
            
    def writetocsv(self, msg, callback) -> str:
        # Note: removed sync number. Size kept?
        header = csv_delimiter.join([str(i) for i in list(msg._header)[1:]])
        
        with open(self.file_name, 'a') as f:
            f.write(header + csv_delimiter)
            json.dump(todict(msg), f, ensure_ascii = True)
            f.write('\n')

if __name__ == '__main__':
    
    src_file = 'Data.lsf'
    sub = n.subscriber(n.file_interface(input = src_file))

    w = writer('output.csv', 1E6)
    sub.subscribe_all(w.writetocsv)

    sub.run()
    w.flush()