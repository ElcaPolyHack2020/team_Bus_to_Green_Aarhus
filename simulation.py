from time import sleep
import sys
import traci
import traci.constants as tc
import logging
import os


logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.INFO)
logger = logging.getLogger('simulation')

class _BaseSimulation:
    def __init__(self, simulation_steps, sleep_time, pedestrians, bus_depot_start_edge, bus_depot_end_edge, bus_lane=0, n_buses=None):
        self.simulation_steps = simulation_steps
        self.sleep_time = sleep_time
        self.pedestrians = pedestrians
        self.bus_depot_start_edge = bus_depot_start_edge
        self.bus_depot_end_edge = bus_depot_end_edge
        self.bus_lane=bus_lane
        self.n_buses=n_buses

    def update_stats(self):
        """ Update our statistics that we use to determine the score
        """
        pass

    def get_score(self):
        """ Get a score based on the currently available statistics
        """
        pass

    def setup(self):
        """ Things that only have to be done once for that simulation
        """
        pass

    def step(self, time):
        """ Things that are done in every step of the simulation
        """
        pass

    def run(self, output=False):
        # Initialize our algorithms
        self.setup()
        for time in range(self.simulation_steps):
            # Advance the simulation
            traci.simulationStep()
            # Do the next task
            self.step(time)
            # Update the stats that we use for scoring
            self.update_stats()

class _Stage1Scorer(_BaseSimulation):
    N_BUSES_WEIGHT=1
    NOT_ARRIVED_WEIGHT=1


class _StageScorer(_BaseSimulation):
    N_BUSES_WEIGHT=1
    WAIT_TIME_WEIGHT=1
    NOT_ARRIVED_WEIGHT=1
    DRIVEN_DISTANCE_WEIGHT=1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.total_waiting_time = 0
        self.buses = set()
        self.distance_dict = dict()

    
    def update_stats(self):
        person_ids = traci.person.getIDList()
        self.total_waiting_time += sum([1 for id in person_ids if traci.person.getStage(id).type == 1])
        current_bus_list = [id for id in traci.vehicle.getIDList() if id.startswith("bus")]
        self.buses |= set(current_bus_list)

        for id in current_bus_list:
            if not id in self.distance_dict:
                self.distance_dict[id] = (0, None)

            new_dist = self.distance_dict[id][0]
            vehicle_id = self.distance_dict[id][1]
            try: 
                new_dist = traci.vehicle.getDistance(id)
                if vehicle_id==None:
                    vehicle_id = traci.vehicle.getTypeID(id)
            except:
                raise Error("Update Scoring functino not working")

            self.distance_dict[id] = (max(self.distance_dict[id][0], new_dist), vehicle_id)
    

    def get_score(self):
        not_arrived = sum([1 for id in traci.person.getIDList() if "Arrived" not in traci.person.getStage(id).description])
        driven_distance_all = 0
        driven_distance_l = 0
        buses_l = 0

        for dist_vehicle in self.distance_dict.values():
            if dist_vehicle[1] =="BUS_L":
                driven_distance_l += dist_vehicle[0]
                buses_l += 1
            driven_distance_all += dist_vehicle[0]

        stage1 = buses_l*self.N_BUSES_WEIGHT + not_arrived*self.NOT_ARRIVED_WEIGHT

        stage2 =  stage1+ self.total_waiting_time*self.WAIT_TIME_WEIGHT + driven_distance_l * self.DRIVEN_DISTANCE_WEIGHT

        stage3 = len(self.buses)*self.N_BUSES_WEIGHT + not_arrived*self.NOT_ARRIVED_WEIGHT + self.total_waiting_time*self.WAIT_TIME_WEIGHT + driven_distance_all * self.DRIVEN_DISTANCE_WEIGHT
        
        return (stage1, stage2, stage3)

class ExampleSimulation(_StageScorer):
    """ The example simulation provided by ELCA
    """
    def setup(self):
        n_pedestrians = len(self.pedestrians)
        for bus_index, person in enumerate(self.pedestrians):
            ##logger.info("Generating bus route {}/{}".format(bus_index, n_pedestrians))
            
            bus_id = f'bus_{bus_index}'

            try:
                traci.vehicle.add(vehID=bus_id, typeID="BUS_S", routeID="", depart=person.depart + 240.0, departPos=0, departSpeed=0, personCapacity=4)
                
                traci.vehicle.setRoute(bus_id, [self.bus_depot_start_edge])
                traci.vehicle.changeTarget(bus_id, person.edge_from)
                traci.vehicle.setStop(vehID=bus_id, edgeID=person.edge_from, pos=person.position_from, laneIndex=1, duration=50, flags=tc.STOP_DEFAULT)
                
                traci.vehicle.setRoute(bus_id, [person.edge_from])
                traci.vehicle.changeTarget(bus_id, person.edge_to)
                traci.vehicle.setStop(vehID=bus_id, edgeID=person.edge_to, pos=person.position_to, laneIndex=1, duration=50, flags=tc.STOP_DEFAULT)

            except traci.exceptions.TraCIException as err:
                print("TraCIException: {0}".format(err))
            except Exception as err:
                print("Unexpected error:", sys.exc_info()[0])
                raise err

        traci.vehicle.subscribe('bus_0', (tc.VAR_ROAD_ID, tc.VAR_LANEPOSITION, tc.VAR_POSITION , tc.VAR_NEXT_STOPS ))

class BusJob:
    def __init__(self, bus):
        ##logger.info("init of "+self.__class__.__name__)
        self.bus = bus

    def is_done(self):
        raise NotImplementedError()

    def step(self, time):
        ##logger.info("step of "+self.__class__.__name__)
        pass
    
    def finish(self):
        pass

class MoveTo(BusJob):
    """Moves to a given edge and stops at the given position
    """
    def __init__(self, edge, stop_pos=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ##logger.info(["Moving to", edge, stop_pos])
        self.edge = edge
        self.stop_pos = stop_pos
        self.moved = False

    def step(self, time):
        super().step(time)
        if not self.moved:
            self.bus.move_to(self.edge, stop_pos=self.stop_pos)
            self.moved = True

    def is_done(self):
        return self.bus.get_edge() == self.edge and self.bus.is_stopped()

class IDLE(BusJob):
    """Parks the bus next to the road for a given amount of time
    """
    STATE_NOT_STARTED = 0
    STATE_IDLE = 1
    STATE_FINISHED = 2
    def __init__(self, until, *args,pos=None,**kwargs):
        super().__init__(*args, **kwargs)
        ##logger.info(["Sleeping until", until])
        self.until = until
        self.pos = pos
        self.state=self.STATE_NOT_STARTED
    
    def step(self, time):
        super().step(time)
        if self.until - 3 < time: # This - 3 is so that the buses have time to start the next task before the idle finishes. why -3 I don't know...
            self.state = self.STATE_FINISHED
        if self.state == self.STATE_NOT_STARTED:
            self.bus.wait(self.until - time, self.pos, tc.STOP_PARKING)
            self.state = self.STATE_IDLE
    def is_done(self):
        return self.state == self.STATE_FINISHED

class DropOff(BusJob):
    """Stops the bus to let passengers out
    """
    DURATION=0
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_time = None
        self.current_time = None
        
    def step(self, time):
        super().step(time)
        self.current_time = time
        if self.start_time is None:
            self.start_time = time
            self.bus.wait(self.DURATION, type=tc.STOP_DEFAULT)
        
    def is_done(self):
        return self.start_time is not None and self.current_time > self.start_time + self.DURATION
    
class PickUp(BusJob):
    """Picks up a passenger and brings him to the given node and position.
    Important: The bus has to already be located at the pickup point
    Important: It will also kind of drive to the dropoff location but not all the way, I don't know don't ask me, ask the sumo devs.
    Important: No, I am not proud of my code here, i don't think its that clear why it actually works, even I don't fully understand it but sumos ways are what they are
    """
    DURATION=3
    def __init__(self, edge, pos, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.edge=edge
        self.pos=pos
        self.start_time = None
        self.current_time = None
        self.state=0

    def step(self, time):
        super().step(time)
        self.current_time = time
        if self.state==0:
            self.start_time = time
            traci.vehicle.setRoute(self.bus.id, [self.bus.get_edge()])
            traci.vehicle.changeTarget(self.bus.id, self.edge)
            self.bus.wait(self.DURATION, type=tc.STOP_DEFAULT)
            self.bus.move_to(self.edge, self.pos)
        self.state += 1

    def is_done(self):
        return self.start_time is not None and self.current_time > self.start_time + self.DURATION

class Bus:
    """A wrapper for a bus that can hold and queue tasks (=jobs)
    """
    def __init__(self, id, start_edge, end_edge, bus_lane=0, capacity=4,type="BUS_L"):
        self.id = id
        self.start_edge=start_edge
        self.end_edge=end_edge
        self.jobs = []
        self.pedestrians = []
        self.bus_lane = bus_lane
        self.done=False
        self.type=type
        self.capacity=capacity
        self.current_target_edge=start_edge
        self.current_target_pos=1
        traci.vehicle.add(
            vehID=self.id,
            typeID=type,
            routeID="",
            depart=0,
            departPos=0,
            departSpeed=0,
            personCapacity=8
        )
    
    def get_pos(self):
        return traci.vehicle.getLanePosition(self.id)

    def get_edge(self):
        return traci.vehicle.getRoadID(self.id)
    
    def get_distance(self, edge, pos):
        return traci.simulation.getDistanceRoad(self.current_target_edge, self.current_target_pos, edge, pos)

    def get_lane(self):
        return traci.vehicle.getLaneID(self.id)

    def get_lane_idx(self):
        return traci.vehicle.getLaneIndex(self.id)

    def is_stopped(self):
        return traci.vehicle.isStopped(self.id)


    def move_to(self, edge, stop_pos=None):
        """Moves to a given edge and stop position. It will try to go in a circle if the target edge is downstream. I hate that I
        have to implement the logic for that but it is what it is, at least it works.
        """
        try: # Try to do it normally
            traci.vehicle.changeTarget(self.id, edge)
            if stop_pos is not None:
                traci.vehicle.setStop(self.id, edge, stop_pos, self.bus_lane, 0xdeadbeef, tc.STOP_DEFAULT)
        except: # If there was an error, we probably tried to move backwards, so we'll first go to the opposite side of the street and then back to where we are
            # Ideally there would be a nicer way of doing this, as this is also dependent on the opposite node being noted with "-", e.g. "1" and "-1". Also it might crash if there is no opposite node.
            if edge.startswith("-"):
                opposite_edge = edge[1:]
            else:
                opposite_edge = "-"+edge
            self.jobs = [MoveTo(opposite_edge, None, self), MoveTo(edge, stop_pos, self)] + self.jobs

    def wait(self, duration, pos=None, type=tc.STOP_DEFAULT):
        """Waits for a given amount of time at the given position on the current edge. The type is to determine wether we wait on the street or if we park the bus next to the street.
        """
        stops = traci.vehicle.getStops(self.id)
        if len(stops) > 0 and (pos is None or stops[0].endPos==pos):
            traci.vehicle.setStop(self.id, self.get_edge(), stops[0].endPos, self.bus_lane, duration, type)
        else:
            if pos is None:
                pos = self.get_pos()
            for i in range(0,200,10):
                try:
                    traci.vehicle.setStop(self.id, self.get_edge(), pos+i, self.bus_lane, duration, type)
                    break
                except:
                    pass
                
    def step(self, time):
        """Advances the internal simulation by one step
        """
        while len(self.jobs) > 0 and self.jobs[0].is_done():
            self.jobs = self.jobs[1:]

        if not self.done and (len(self.jobs) == 0 or len(traci.vehicle.getNextStops(self.id)) == 0):
            self.jobs = [IDLE(time+10, self)] + self.jobs
            
        if len(self.jobs) > 0:
            self.jobs[0].step(time)
        else:
            traci.vehicle.remove(self.id)

class FixedNBusesSimulation(_StageScorer):
    """Deploys N Buses 
    """
    N_BUSES = 28
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.deployed_buses = set()
        self.next_passenger_index = 0

    def setup(self):
        # Sort passengers by their departure time
        self.pedestrians = sorted(self.pedestrians, key=lambda x:x.depart)

        if self.n_buses is None:
            self.n_buses = self.N_BUSES
        for i in range(self.n_buses):
            bus = Bus(f'bus_{i}', self.bus_depot_start_edge, self.bus_depot_end_edge, bus_lane=self.bus_lane)
            self.deployed_buses.add(bus)

    def step(self, time):
        vehicles = set(traci.vehicle.getIDList())
        for bus in self.deployed_buses:
            if bus.id in vehicles:
                if len(bus.jobs) < 3:
                    if self.next_passenger_index < len(self.pedestrians):
                        p = self.pedestrians[self.next_passenger_index]
                        self.next_passenger_index += 1
                        bus.jobs.append(MoveTo(p.edge_from, p.position_from, bus)) # Go to that passenger
                        bus.jobs.append(IDLE(p.depart, bus)) # Wait until the passenger arrives
                        bus.jobs.append(PickUp(p.edge_to, p.position_to, bus)) # Wait until the passenger arrives
                        bus.jobs.append(MoveTo(p.edge_to, p.position_to, bus)) # Go to the destination
                        bus.jobs.append(DropOff(bus)) # Let passenger exit
                    else:
                        bus.jobs.append(MoveTo(bus.end_edge, 100, bus)) # Go home
                        bus.done = True                
                bus.step(time)

class OptimizedFixedNBusesSimulation(FixedNBusesSimulation):
    """Deploys N Buses, chooses closest passenger next
    """
    DEPARTURE_WEIGHT=40
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reserved_pedestrians = set()
    
    def get_best_distance_pedestrian(self, bus, time):
        best_distance = None
        best_p = None
        for p in self.pedestrians:
            if p.id not in self.reserved_pedestrians and "waiting" in traci.person.getStage(p.id).description:
                distance=bus.get_distance(p.edge_from, p.position_from) + max(0, p.depart-time) * self.DEPARTURE_WEIGHT
                if best_distance is None or -100000 <= distance < best_distance:
                    best_distance = distance 
                    best_p = p
        return best_p

    def step(self, time):
        vehicles = set(traci.vehicle.getIDList())
        pedestrians = set(traci.person.getIDList())

        for bus in self.deployed_buses:
            if bus.id in vehicles:
                if len(bus.jobs) < 2:
                    best_p = self.get_best_distance_pedestrian(bus, time)
                    if best_p is not None:
                        p = best_p
                        self.reserved_pedestrians.add(p.id)
                        bus.current_target_edge = p.edge_to
                        bus.current_target_pos = p.position_to
                        bus.jobs.append(MoveTo(p.edge_from, p.position_from, bus)) # Go to that passenger
                        bus.jobs.append(IDLE(p.depart, bus)) # Wait until the passenger arrives
                        bus.jobs.append(PickUp(p.edge_to, p.position_to, bus)) # Wait until the passenger arrives
                        bus.jobs.append(MoveTo(p.edge_to, p.position_to, bus)) # Go to the destination
                        bus.jobs.append(DropOff(bus)) # Let passenger exit
                    elif len(self.pedestrians) == len(pedestrians): # all passenger reserved
                        bus.jobs.append(MoveTo(bus.end_edge, 100, bus)) # Go home
                        bus.done = True                
                bus.step(time)