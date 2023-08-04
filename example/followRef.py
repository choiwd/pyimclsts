import pyimclsts.network as p
import pyimc_generated as pg
import random 

class FollowRef_Vehicle():
    '''
    Minimal implementation to start a Follow Reference manuever
    '''
    __slots__ = ['EstimatedState', 'FollowRefState', 'peers', 'target', 'request_id']
    
    def __init__(self, target : str) -> None:
        '''target is the name of the vehicle as in Announce messages'''
        self.EstimatedState = None
        self.FollowRefState = None
        
        self.target = target
        self.peers = dict()

    def request_followRef(self, send_callback):
        if self.FollowRefState is None:
            request = pg.messages.PlanControl()
            
            fr = pg.messages.FollowReference()
            fr.control_src = 0xFFFF #0x4000 | (pg.core.get_initial_IP() & 0xFFFF)
            fr.control_ent = 0xFF
            fr.timeout = 10
            fr.loiter_radius = 0
            fr.altitude_interval = 0

            request.type = pg.messages.PlanControl.TYPE.REQUEST
            request.op = pg.messages.PlanControl.OP.START
            self.request_id = random.randint(0, 0xFFFF)
            request.request_id = self.request_id
            request.plan_id = "MyPlan-pyimctrans"
            request.flags = pg.messages.PlanControl.FLAGS.IGNORE_ERRORS
            request.arg = fr
            request.info = "MyPlan"
            
            print("Requesting Follow Reference Manuever...")
            print(request)
            send_callback(request, dst = self.peers.get(self.target, 0xFFFF))

    def send_refs(self, send_callback):
        if self.EstimatedState is not None:
            referenceToFollow = pg.messages.Reference()

            referenceToFollow.flags = pg.messages.Reference.FLAGS.LOCATION | pg.messages.Reference.FLAGS.SPEED | pg.messages.Reference.FLAGS.Z
            referenceToFollow.speed = pg.messages.DesiredSpeed(value=50, speed_units=pg.enumerations.SpeedUnits.PERCENTAGE)
            referenceToFollow.z = pg.messages.DesiredZ(value=1, z_units=pg.enumerations.ZUnits.DEPTH)
            referenceToFollow.lat = self.EstimatedState.lat + 0.001
            referenceToFollow.lon = self.EstimatedState.lon
            referenceToFollow.radius = 0

            send_callback(referenceToFollow, dst = self.peers.get(self.target, 0xFFFF))

    def update_vehicle_state(self, msg : pg.messages.EstimatedState, send_callback):
        self.EstimatedState = msg

    def update_plan_state(self, msg : pg.messages.FollowRefState, send_callback):
        self.FollowRefState = msg
    
    def update_peers(self, msg : pg.messages.Announce, send_callback):
        self.peers[msg.sys_name] = msg._header.src

if __name__ == '__main__':
    
    conn = p.tcp_interface('localhost', 6006)
    vehicle = FollowRef_Vehicle('lauv-xplore-2')

    sub = p.subscriber(conn)

    # Set a delay, so that we receive the Announcements
    sub.call_once(vehicle.request_followRef, 5)

    sub.subscribe_async(vehicle.update_peers, pg.messages.Announce)
    sub.subscribe_async(vehicle.update_vehicle_state, pg.messages.EstimatedState)
    sub.subscribe_async(vehicle.update_plan_state, pg.messages.FollowReference)

    sub.periodic_async(vehicle.send_refs, 1)

    #sub.periodic_async(lambda _ : print(vehicle.peers), 1)

    sub.run()