'''
    Contains classes that define the role this pyimc instance will perform and
    are intended to be used directly by the user or their abstraction layer

'''
import typing as _typing
import functools as _functools
import inspect as _inspect
import types as _types

import multiprocessing as _multiprocessing
import asyncio as _asyncio
import time as _time

import importlib.util as _import
import sys as _sys
import os as _os

import pyimclsts.core as _core

_module_name = 'pyimc_generated' # and folder name
_location = _os.getcwd() + '/' + _module_name + '/__init__.py'

_spec = _import.spec_from_file_location(_module_name, _location)

_pg = _import.module_from_spec(_spec)
_sys.modules[_module_name] = _pg
_spec.loader.exec_module(_pg)

def unpack(message : bytes, *, is_big_endian : bool = None, is_field_message : bool = False, fast_mode : bool = False) -> _core.IMC_message:
    '''Expects a serializable (= exactly long (header + fields + CRC)) string of bits whose CRC has already been checked
    
    Fast mode skips all type checking performed by the descriptor by directly invoking the constructor.
    '''
    if is_big_endian is None:
        is_big_endian = int.from_bytes(message[:2], byteorder='big') == _pg._base._sync_number
        # Note: is_big_endian is a function parameter to enable recursion
    
    unpack_functions = _core.unpack_functions_big if is_big_endian else _core.unpack_functions_little
    cursor = 0
    
    if not is_field_message:
        # deserialize header
        (m, size) = unpack_functions['header'](message[cursor:])
        deserialized_header = _pg._base.header_data(*m)
        cursor += size
    
        msgid = deserialized_header.mgid
        if msgid not in _pg.messages._message_ids:
            unknown_msg = _pg.messages.Unknown(msgid, contents = message[cursor:-2], endianess = is_big_endian)
            unknown_msg._header = deserialized_header
            return unknown_msg
    else:
        msgid = unpack_functions['uint16_t'](message[cursor:cursor+2])[0]
        cursor += 2
        if msgid not in _pg.messages._message_ids:
            raise KeyError(f'Cannot parse/unpack an unknown inlined message (no information about the size). Add message id {msgid} to extract list')
    
    if fast_mode:
        # get corresponding class
        message_class = getattr(_pg.messages, _pg.messages._message_ids.get(msgid, None))

        fields = [(f, getattr(getattr(type(message_class()), f), '_field_def')['type']) for f in message_class().Attributes.fields]
        arguments = dict()
        for field, t in fields:
            if t == 'message':
                if unpack_functions['uint16_t'](message[cursor:cursor+2])[0] == 65535:
                    cursor += 2
                else:
                    (m, size) = unpack(message[cursor:], is_big_endian=is_big_endian, is_field_message=True, fast_mode=fast_mode)
                    arguments[field] = m
                    cursor += size
            elif t == 'message-list':
                (n, _) = unpack_functions['uint16_t'](message[cursor:])
                cursor += 2
                arguments[field] = []
                for _ in range(n):
                    (m, size) = unpack(message[cursor:], is_big_endian=is_big_endian, is_field_message=True, fast_mode=fast_mode)
                    arguments[field].append(m)
                    cursor += size
            else:
                (m, size) = unpack_functions[t](message[cursor:])
                arguments[field] = m
                cursor += size
        # instantiate class through constructor
        message_class = message_class(**arguments)
        
    else:
        # instantiate empty class
        message_class = getattr(_pg.messages, _pg.messages._message_ids.get(msgid, None))()

        # deserialize fields
        # make a (field, type) tuple list, get information in the descriptor
        fields = [(f, getattr(getattr(type(message_class), f), '_field_def')['type']) for f in message_class.Attributes.fields]
        for field, t in fields:
            if t == 'message':
                if unpack_functions['uint16_t'](message[cursor:cursor+2])[0] == 65535:
                    cursor += 2
                else:
                    (m, size) = unpack(message[cursor:], is_big_endian=is_big_endian, is_field_message=True, fast_mode=fast_mode)
                    cursor += size
                    setattr(message_class, field, m)
            elif t == 'message-list':
                (n, _) = unpack_functions['uint16_t'](message[cursor:])
                cursor += 2
                message_list = []
                for _ in range(n):
                    (m, size) = unpack(message[cursor:], is_big_endian=is_big_endian, is_field_message=True, fast_mode=fast_mode)
                    message_list.append(m)
                    cursor += size
                setattr(message_class, field, message_list)
            else:
                (m, size) = unpack_functions[t](message[cursor:])
                cursor += size
                setattr(message_class, field, m)
    
    if not is_field_message:
        message_class._header = deserialized_header
        return message_class
    else:
        return (message_class, cursor)

def _get_id_src_src_ent(message : bytes) -> int:
    src_ent = message[16]
    if int.from_bytes(message[:2], byteorder='big') == _pg._base._sync_number:
        id = int.from_bytes(message[2:4], byteorder='big')
        src = int.from_bytes(message[14:16], byteorder='big')
        
        return (id, src, src_ent)
    else:
        id = int.from_bytes(message[2:4], byteorder='little')
        src = int.from_bytes(message[14:16], byteorder='little')
        
        return (id, src, src_ent)

# Re-export some classes:

tcp_interface = _core.tcp_interface
file_interface = _core.file_interface

class _message_bus():
    '''Injected dependency to 'simplify' common functionalities'''
    __slots__ = ['_io_interface', '_timeout', '_big_endian', '_block_outgoing']

    def __init__(self, IO_interface : _core.base_IO_interface, timeout = 60, big_endian=False):
        self._io_interface = IO_interface
        self._timeout = timeout

        # mode to send messages
        self._big_endian = big_endian
        self._block_outgoing = False
    
    def __enter__(self):
        raise NotImplemented
    def __exit__(self, exc_type, exc_value, exc_tb):
        raise NotImplemented
    
    def block_outgoing(self):
        '''Blocks (and discards) outgoing messages'''
        self._block_outgoing = True
    def unblock_outgoing(self):
        '''Unblock outgoing messages'''
        self._block_outgoing = False

    def send(self, message : _pg._base.base_message, *, src : int = None, src_ent : int = None, 
                        dst : int = None, dst_ent : int = None) -> None:
        '''Wrapper around a queue (actually a pipe end).'''
        if not self._block_outgoing:
            self._send(message, src = src, src_ent = src_ent, dst = dst, dst_ent = dst_ent)
            
    def _send(self, message : _pg._base.base_message, *, src : int = None, src_ent : int = None, 
                        dst : int = None, dst_ent : int = None) -> None:
        raise NotImplemented

class message_bus(_message_bus):
    '''
        Send and receives messages as bytes, but exposes them as IMC messages

        Receives a base_IO_interface, which must implement open(), read(), write() and close()
        asynchronous methods.

        Starts another process that continuously reads/writes to the base_IO_interface.
    '''

    __slots__ = ['_child_end', '_parent_end', '_child_process', '_keep_running', '_big_endian']

    def _external_listener_loop(self, child_end, timeout : int, keep_running : _multiprocessing.Value):
        '''All code bellow is executed in a separate process.'''

        async def consume_output(io_interface : _core.base_IO_interface):
            '''Continuously read the pipe end to send messages'''
            
            while keep_running.value:
                try:
                    has_message = child_end.poll()
                    while has_message:
                        message = child_end.recv_bytes()
                        await io_interface.write(message)
                        has_message = child_end.poll()
                finally:
                    pass
                # Yield an exit point to the event loop
                await _asyncio.sleep(0)
            
            print("Writer stream has been closed.")

        async def consume_input(io_interface : _core.base_IO_interface):
            '''Continuously read the socket to deserialize messages'''

            buffer = bytearray()
            while keep_running.value:
                try:
                    # magic number: 6 = sync number + (msgid + msgsize) size in bytes
                    if len(buffer) < 6:
                        buffer += await io_interface.read(6 - len(buffer))

                    if int.from_bytes(buffer[:2], byteorder='little') == _pg._base._sync_number:
                        # get msg size
                        size = int.from_bytes(buffer[4:6], byteorder='little')
                        # magic number: 22 = 20(header size) + 2(CRC) sizes in bytes.
                        read_size = max(size + 22 - len(buffer), 0)
                        buffer += await io_interface.read(read_size)

                        # Validate message, but do not unpack yet
                        unparsed_msg = bytes(buffer[:(size + 22)])
                        if _core.CRC16IMB(unparsed_msg[:-2]) == int.from_bytes(unparsed_msg[-2:], byteorder='little'):
                            child_end.send_bytes(unparsed_msg)
                            # eliminate message from buffer
                            del buffer[:size + 22]
                        else:
                            # deserialization failed:
                            # sync number is not followed by a sound/valid message. Remove it from buffer
                            # to look for next message
                            del buffer[:2]
                    elif int.from_bytes(buffer[:2], byteorder='big') == _pg._base._sync_number:
                        size = int.from_bytes(buffer[4:6], byteorder='big')
                        read_size = max(size + 22 - len(buffer), 0)
                        buffer += await io_interface.read(read_size)

                        unparsed_msg = bytes(buffer[:(size + 22)])
                        if _core.CRC16IMB(unparsed_msg[:-2]) == int.from_bytes(unparsed_msg[-2:], byteorder='big'):
                            child_end.send_bytes(unparsed_msg)
                            del buffer[:size + 22]
                        else:
                            del buffer[:2]
                    else:
                        # buffer does not start with a sync number. Remove it to search
                        # for a valid sync number.
                        del buffer[:2]
                except EOFError as e:
                    print("EOF reached by the stream reader. Waiting for stream writer to finish...")
                    
                    # Unblock the main thread and send an empty byte string. 
                    # (-> signal EOF, so that it won't write anymore)
                    child_end.send_bytes(b'')

                    # Yield to the event loop to let stream writer finish 
                    await _asyncio.sleep(1.5)
                    
                    # Prevent further reads/writes in this process
                    with keep_running.get_lock():
                        keep_running.value = False
                finally:
                    pass
                
                # Yield an exit point to the event loop
                await _asyncio.sleep(0)
            print("Reader stream has been closed.")
        async def main_loop():
            await self._io_interface.open()
            try:
                await _asyncio.gather(consume_input(self._io_interface), consume_output(self._io_interface))
            finally:
                child_end.close()
                print('IO interface has been closed.')
                await self._io_interface.close()

        try:
            _asyncio.run(main_loop())
        except EOFError as e:
            print('No more bytes to read.')
        finally:
            with self._keep_running.get_lock():
                self._keep_running.value = False
            print('Message Bus has been closed.')

    def open(self):
        
        # Using a pipe to establish communication between processes
        self._parent_end, self._child_end = _multiprocessing.Pipe(duplex=True)

        self._keep_running = _multiprocessing.Value('i', True)

        # Start process
        self._child_process = _multiprocessing.Process(target=self._external_listener_loop, 
                                                        args=(self._child_end, self._timeout, self._keep_running))
        self._child_process.start()

        # It is very likely that the main process will run faster than the child process, which
        # may cause some undesirable behaviour, such as, the main process' context manager closes 
        # the connection before the child process' procedures can even start.
        # The naive solution: block the main thread for 0.5 second
        _time.sleep(0.5)
    
    def close(self, max_wait : float = 1) -> None:        
        with self._keep_running.get_lock():
            self._keep_running.value = False
        
        self._child_process.join()
        self._child_process.close()

    def _send(self, message : _pg._base.base_message, *, src : int = None, src_ent : int = None, 
                        dst : int = None, dst_ent : int = None) -> None:
        self._parent_end.send_bytes(message.pack(is_big_endian=self._big_endian, src = src, src_ent = src_ent, 
                        dst = dst, dst_ent = dst_ent))

    def recv(self) -> _pg._base.base_message:
        '''Wrapper around a queue (actually a pipe end). Blocks until a message is available.
        The _external_listener_loop is supposed to send complete messages (as per multiprocessing 
        documentation).'''       
        msg = self._parent_end.recv_bytes()
        
        if msg == b'':
            raise EOFError('Message Bus has been closed.')
        else:
            return msg
            
    def poll(self, timeout : int = 0) -> bool:
        '''Extra function to check whether there are any available messages.
        Check _multiprocessing module pipes.
        '''
        return self._parent_end.poll(timeout=timeout)

    def __enter__(self):
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_value, exc_tb):
        self.close()
        if exc_type == EOFError:
            print('Child process has been closed due to end of file.')
            return True
        print('Child process has been closed.')
        return None

class message_bus_st(_message_bus):
    '''
        Send and receives messages as bytes, but exposes them as IMC messages

        Receives a base_IO_interface, which must implement open(), read(), write() and close()
        asynchronous methods.

        DOES NOT start another process. Runs in the main process.
    '''

    __slots__ = ['_writer_queue', '_reader_queue', '_keep_running', '_big_endian', '_task']
    
    async def open(self):
        self._keep_running = True

        self._writer_queue = _asyncio.Queue()
        self._reader_queue = _asyncio.Queue()

        async def consume_output(io_interface : _core.base_IO_interface):
            '''Continuously read the pipe end to send messages'''
            
            while self._keep_running:
                try:
                    # flush queue or wait.
                    while not self._writer_queue.empty():
                        message = await self._writer_queue.get()
                        await io_interface.write(message)
                    else:
                        await _asyncio.sleep(0.5)
                finally:
                    pass
            
            print("Writer stream has been closed.")

        async def consume_input(io_interface : _core.base_IO_interface):
            '''Continuously read the socket to deserialize messages'''
            
            buffer = bytearray()
            while self._keep_running:
                try:
                    # magic number: 6 = sync number + (msgid + msgsize) size in bytes
                    if len(buffer) < 6:
                        buffer += await io_interface.read(6 - len(buffer))

                    if int.from_bytes(buffer[:2], byteorder='little') == _pg._base._sync_number:
                        # get msg size
                        size = int.from_bytes(buffer[4:6], byteorder='little')
                        # magic number: 22 = 20(header size) + 2(CRC) sizes in bytes.
                        read_size = max(size + 22 - len(buffer), 0)
                        buffer += await io_interface.read(read_size)

                        # Validate message, but do not unpack yet
                        unparsed_msg = bytes(buffer[:(size + 22)])
                        if _core.CRC16IMB(unparsed_msg[:-2]) == int.from_bytes(unparsed_msg[-2:], byteorder='little'):
                            await self._reader_queue.put(unparsed_msg)
                            # eliminate message from buffer
                            del buffer[:size + 22]
                        else:
                            # deserialization failed:
                            # sync number is not followed by a sound/valid message. Remove it from buffer
                            # to look for next message
                            del buffer[:2]
                    elif int.from_bytes(buffer[:2], byteorder='big') == _pg._base._sync_number:
                        size = int.from_bytes(buffer[4:6], byteorder='big')
                        read_size = max(size + 22 - len(buffer), 0)
                        buffer += await io_interface.read(read_size)

                        unparsed_msg = bytes(buffer[:(size + 22)])
                        if _core.CRC16IMB(unparsed_msg[:-2]) == int.from_bytes(unparsed_msg[-2:], byteorder='big'):
                            await self._reader_queue.put(unparsed_msg)
                            del buffer[:size + 22]
                        else:
                            del buffer[:2]
                    else:
                        # buffer does not start with a sync number. Remove it to search
                        # for a valid sync number.
                        del buffer[:2]
                except EOFError as e:
                    print("EOF reached by the stream reader. Waiting for stream writer to finish...")
                    
                    # Unblock the main thread and send an empty byte string. 
                    # (-> signal EOF, so that it won't write anymore)
                    await self._reader_queue.put(b'')

                    # Yield to the event loop to let stream writer finish 
                    await _asyncio.sleep(1.5)
                    
                    # Prevent further reads/writes in this process
                    self._keep_running = False
                finally:
                    pass
                await _asyncio.sleep(0)
            print("Reader stream has been closed.")
        async def main_loop():
            await self._io_interface.open()
            try:
                await _asyncio.gather(consume_input(self._io_interface), consume_output(self._io_interface))
            finally:
                print('IO interface has been closed.')
                await self._io_interface.close()

        self._task = _asyncio.create_task(main_loop())
    
    def close(self, max_wait : float = 1) -> None:
        self._keep_running = False
        self._task.cancel()
        print('Message Bus has been closed.')

    def _send(self, message : _pg._base.base_message, *, src : int = None, src_ent : int = None, 
                        dst : int = None, dst_ent : int = None) -> None:
        self._writer_queue.put_nowait(message.pack(is_big_endian=self._big_endian, src = src, src_ent = src_ent, 
                        dst = dst, dst_ent = dst_ent))

    async def recv(self) -> _pg._base.base_message:
        '''Wrapper around a queue (actually a pipe end). Blocks until a message is available.
        The _external_listener_loop is supposed to send complete messages (as per multiprocessing 
        documentation).'''

        msg = await self._reader_queue.get()
        
        if msg == b'':
            raise EOFError('No more bytes to read.')
        else:
            return msg
            
    def poll(self, timeout : int = 0) -> bool:
        '''Extra function to check whether there are any available messages.
        '''
        return not self._reader_queue.empty()
    
    def __exit__(self, exc_type, exc_value, exc_tb):
        self.close()
        if exc_type == EOFError:
            print('Message bus event loop has been closed due to end of file.')
            return True
        print('Message bus event loop has been closed.')
        return None

class subscriber:

    __slots__ = ['_msg_manager', '_subscriptions', '_subscripted_all', '_periodic', '_call_once', '_use_mp', '_peers', '_src2name', '_keep_running']

    def __init__(self, IO_interface : _core.base_IO_interface, *,big_endian=False, use_mp = False) -> None:
        self._use_mp = use_mp
        if self._use_mp:
            self._msg_manager = message_bus(IO_interface, big_endian)
        else:
            self._msg_manager = message_bus_st(IO_interface, big_endian)
        self._subscriptions = dict()
        self._subscripted_all = []
        self._periodic = []
        self._call_once = []

        # a dictionary of {vehicle name : {'src' : 1, 'entities' : { 1 : 'Entity name'...} ...}}
        # However, it can temporarily contains int keys denoting src to (temporarily) store information
        # of vehicles of unknown name
        self._peers = dict()
        # a dictionary of {2: 'vehicle name'}
        self._src2name = dict()
        
        self.subscribe_async(self._abort, _pg.messages.Abort)
        
        self.call_once(self._queryEntityList, delay=1)
        self.periodic_async(self._queryEntityList, period=300)
        self.subscribe_async(self._update_peers, _pg.messages.EntityInfo)
        self.subscribe_async(self._update_peers, _pg.messages.EntityList)
        self.subscribe_async(self._update_peers, _pg.messages.Announce)

    async def _periodic_wrapper_coro(self, _period : float, f : _typing.Callable, send_callback : _typing.Callable[[_core.IMC_message], None]):
        loop = _asyncio.get_running_loop()
        while True:
            last_exec = loop.time()
            await f(send_callback)
            now = loop.time()
            await _asyncio.sleep(max(last_exec - now + _period, 0))
                
    async def _periodic_wrapper(self, _period : float, f : _typing.Callable, send_callback : _typing.Callable[[_core.IMC_message], None]):
        loop = _asyncio.get_running_loop()
        f(send_callback)
        while True:
            await _asyncio.sleep(_period)
            loop.call_later(_period, f, send_callback)

    async def _event_loop(self):
        msg_mgr = self._msg_manager
        try:
            if self._use_mp:
                msg_mgr.open()
            else:
                await msg_mgr.open()
            loop = _asyncio.get_running_loop()

            for f, delay in self._call_once:
                if delay is not None:
                    loop.call_later(delay, f, msg_mgr.send)
                else:
                    f(msg_mgr.send)
            
            # Binding references to background task objects so that they are not garbage collected
            tasks = []
            for f, period in self._periodic:
                if _inspect.iscoroutinefunction(f):
                    tasks.append(loop.create_task(self._periodic_wrapper_coro(period, f, msg_mgr.send)))
                elif callable(f):
                    tasks.append(loop.create_task(self._periodic_wrapper(period, f, msg_mgr.send)))
                else:
                    print(f'Warning: Given function {f} is neither _typing.Callable nor a coroutine.')

            while self._keep_running:
                msg = msg_mgr.recv() if self._use_mp else await msg_mgr.recv()
                mgid, src, src_ent = _get_id_src_src_ent(msg)
                if mgid in self._subscriptions:
                    desel_message = unpack(msg, fast_mode=True)
                    for f in self._subscriptions[mgid]:
                        if self._validate_call(src, src_ent, f[1], f[2]):
                            await f[0](desel_message, msg_mgr.send)
                
                [await f[0](unpack(msg, fast_mode=True), msg_mgr.send) for f in self._subscripted_all if self._validate_call(src, src_ent, f[1], f[2])]
                # Offer an exit point
                await _asyncio.sleep(0)
        except EOFError:
            print('Stream has ended.')
        finally:
            msg_mgr.close()

    async def _abort(self, msg, send_callback):
        if msg._header is not None:
            my_src = 0x4000 | (_core.get_initial_IP() & 0xFFFF)
            if msg._header.dst == my_src:
                loop = _asyncio.get_running_loop()
                loop.close()

    def _update_peers(self, msg : _typing.Union[_pg.messages.EntityList, _pg.messages.Announce, _pg.messages.EntityInfo], send_callback):
        if msg._header is not None:
            src = msg._header.src
            
            if isinstance(msg, _pg.messages.EntityList):
                if msg.op == msg.OP.REPORT:
                    entList =  [i.split(sep='=') for i in msg.list.split(sep=';')]
                    entList = {k : int(v) for [k, v] in entList}

                    name = self._src2name.get(src, None)
                    if name is not None:
                        # if it exists, update; else, create entry
                        if self._peers.get(name, None) is not None:
                            self._peers[name]['EntityList'] = entList
                        else:
                            self._peers[name] = {'EntityList' : entList}
                    else:
                        if self._peers.get(src, None) is not None:
                            self._peers[src]['EntityList'] = entList
                        else:
                            self._peers[src] = {'EntityList' : entList}
            
            elif isinstance(msg, _pg.messages.EntityInfo):
                name = self._src2name.get(src, None)
                
                if name is not None:
                    # if it exists, update; else, create entry
                    if self._peers.get(name, None) is not None:
                        self._peers[name]['EntityList'][msg.label] = msg.id
                    else:
                        self._peers[name] = {'EntityList' : {msg.label : msg.id}}
                else:
                    if self._peers.get(src, None) is not None:
                        self._peers[src]['EntityList'][msg.label] = msg.id
                    else:
                        self._peers[src] = {'EntityList' : {msg.label : msg.id}}

            elif isinstance(msg, _pg.messages.Announce):
                name = msg.sys_name

                self._src2name[src] = name
                
                temp_value = self._peers.pop(src, None)
                # check if an int key exists. If it does upgrade it to a normal entry
                if temp_value is not None:
                    self._peers[name] = temp_value
                    self._peers[name]['src'] = src
                else:
                    # if it exists, update; else, create entry
                    if self._peers.get(name, None) is not None:
                        self._peers[name]['src'] = src
                    else:
                        self._peers[name] = {'src' : src}
        else:
            pass
    
    def _get_src(self, vehicle_name : str):
        return self._peers[vehicle_name].get('src', None) if self._peers.get(vehicle_name, None) is not None else None
    
    def _get_src_ent(self, vehicle_name : str, entityName : str):
        entityList = self._peers[vehicle_name].get('EntityList', None) if self._peers.get(vehicle_name, None) is not None else None
        if entityList is not None:
            return entityList.get(entityName, None)
        return None
    
    def _queryEntityList(self, send):
        query = _pg.messages.EntityList(op=_pg.messages.EntityList.OP.QUERY, list='')
        send(query)
    
    def _validate_call(self, src, src_ent, desired_src : str, desired_src_ent : str) -> bool:
        if desired_src is None and desired_src_ent is None:
            return True
        else:
            correct_src = src == self._get_src(desired_src) 
            correct_src_ent = src_ent == self._get_src_ent(desired_src, desired_src_ent)
            
            if (correct_src or correct_src_ent) and (desired_src is None or desired_src_ent is None):
                return True
            elif correct_src and correct_src_ent:
                return True
            
        return False
    
    def subscribe_async(self, callback : _typing.Callable[[_core.IMC_message, _typing.Callable[[_core.IMC_message], None]], None], msg_id : _typing.Union[int, _core.IMC_message, str, _types.ModuleType] = None, *, src : str = None, src_ent : str = None):
        '''Appends the callback to the list of subscriptions to a message.
        msg_id can be provided as an int, the class of the message, its instance or a category (string (camel case) or module).
        src and src_ent should be provided as strings.
        
        When a parameters is None, then it is interpreted as 'all'.

        The main loop calls the function and pass the message and a callback to send messages.
        The return value is discarded and the function must have exactly two parameters (the message and the callback)
        and must not have additional parameters, to avoid unintended behavior*.
        
        *Due to python's pass-by-assignment, the argument values are evaluated when a function is called.
        This means that even if we pass, say "x", to the .subscribe_async method and then try to
        pass "x" to the callback, we can only pass x's value at the moment .subscribe_async was called.
        This means that if we subscribe, for example, f(x) and somewhere a function g "updates" x, and then call
        f(x) again, f will be called with x's first value.
        This could be bypassed using mutable data structures, but let's not delve into that.

        Tip: If the original function really needs arguments, wrap it with functools.partial.
        Tip2: Use a class instance to keep shared values across different calls. See followRef.py.
        '''
        key = None
        if isinstance(msg_id, _core.IMC_message):
            key = msg_id.Attributes.id
        elif isinstance(msg_id, int):
            key = msg_id
        elif _inspect.isclass(msg_id):
            if issubclass(msg_id, _core.IMC_message):
                key = msg_id().Attributes.id
        elif isinstance(msg_id, str):
            module = getattr(_pg.categories, msg_id)
            self.subscribe_async(callback, module, src=src, src_ent=src_ent)
        elif isinstance(msg_id, _types.ModuleType):
            msgs = [j for j in [getattr(msg_id, i) for i in dir(msg_id) if _inspect.isclass(getattr(msg_id, i))] if issubclass(j, _core.IMC_message)]
            for m in msgs:
                self.subscribe_async(callback, m, src=src, src_ent=src_ent)
        elif msg_id is None:
            pass
        else:
            print(f'Warning: Given message id {msg_id} is not a known message.')
        
        
        # There is either an explicit subscription (the key is not None) or 'all'
        # (msg_id is None). There cannot be both nor neither.
        if (key is not None) ^ (msg_id is None):
            c = None
            if _inspect.iscoroutinefunction(callback):
                c = callback
            elif callable(callback):
                c = _functools.partial(_core._async_wrapper, callback)
            else:
                print(f'Warning: Given function {callback} is neither callable nor a coroutine.')
            
            if c is not None:
                if msg_id is None:
                    self._subscripted_all.append((c, src, src_ent))
                else:
                    if self._subscriptions.get(key, None) is not None:
                        self._subscriptions[key].append((c, src, src_ent))
                    else:
                        self._subscriptions[key] = [(c, src, src_ent)]

    def periodic_async(self, callback : _typing.Callable[[_core.IMC_message], None], period = float):
        '''Add callback to a list to be called every period seconds. Function must take
        a send callback as parameter. This callback can be used to send messages.'''
        self._periodic.append((callback, period))

    def subscribe_mp(self, callback : _typing.Callable[[_core.IMC_message, _typing.Callable[[_core.IMC_message], None]], None], msg_id : _typing.Union[int, _core.IMC_message, str, _types.ModuleType] = None, *, src : str = None, src_ent : str = None):
        '''Calls a function and pass the message and a callback to send messages to it.
        Runs the given callback in a different process and should be used only with heavy load
        functions.
        '''
        raise NotImplemented

    def call_once(self, callback : _typing.Callable[[_typing.Callable[[_core.IMC_message], None]], None], delay : float = None):
        '''Calls the given callbacks as soon as the main loop starts or according to their delay in seconds.
        Callback parameters must be exactly one callback (that can be used to send messages).'''
        self._call_once.append((callback, delay))

    def print_information(self):
        '''Looks for (and asks for, when applicable) the first Announce and EntityList messages and print them.
        
        Executes no other subscription.
        '''
        
        _subscriptions_temp = self._subscriptions
        _subscripted_all_temp = self._subscripted_all
        _periodic_temp = self._periodic
        _call_once_temp = self._call_once

        self._subscriptions = dict()
        self._subscripted_all = []
        self._periodic = []
        self._call_once = []

        self.call_once(self._queryEntityList, delay=1)
        self.periodic_async(self._queryEntityList, period=10)
        
        msgs = dict()
        def printmsg(msg, cb):
            if isinstance(msg, _pg.messages.Announce):
                msgs['Announce'] = msg
            if isinstance(msg, _pg.messages.EntityList) and msg.op == _pg.messages.EntityList.OP.REPORT:
                msgs['EntityList'] = msg
            if len(msgs) >= 2:
                self.stop()
        
        self.subscribe_async(printmsg, _pg.messages.Announce)
        self.subscribe_async(printmsg, _pg.messages.EntityList)

        self.run()

        for i in msgs.values():
            print(i)
            print('\n')
        
        self._subscriptions = _subscriptions_temp
        self._subscripted_all = _subscripted_all_temp
        self._periodic = _periodic_temp
        self._call_once = _call_once_temp

    def stop(self):
        '''Signals the subscriber to immediately stop.'''
        self._keep_running = False
    
    def run(self):
        '''Starts the event loop of the subscriber. 
        
        That is: Open the IO_interface, wraps and runs the callbacks that have been subscribed to messages.
        Since it uses asyncio, it blocks the whole interpreter.
        '''
        self._keep_running = True
        _asyncio.run(self._event_loop())