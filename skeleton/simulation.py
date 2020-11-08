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
    def __init__(self, simulation_steps, sleep_time, pedestrians, bus_depot_start_edge, bus_depot_end_edge):
        self.simulation_steps = simulation_steps
        self.sleep_time = sleep_time
        self.pedestrians = pedestrians
        self.bus_depot_start_edge = bus_depot_start_edge
        self.bus_depot_end_edge = bus_depot_end_edge

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

    def run(self):
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
        self.buses |= {id for id in traci.vehicle.getIDList() if id.startswith("bus")}

        for id in [id for id in traci.vehicle.getIDList() if id.startswith("bus")]:
            new_dist = 0
            vehicle_id = None
            try: 
                new_dist = traci.vehicle.getDistance(id)
                vehicle_id = traci.vehicle.getTypeID(id)
            except:
                pass

            if id in self.distance_dict:
                self.distance_dict[id] = (max(self.distance_dict[id][0], new_dist), vehicle_id if self.distance_dict[id][1]==None else self.distance_dict[id][1])
            else:     
                self.distance_dict[id] = (new_dist, vehicle_id)


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

class BusJob:
    def __init__(self, bus):
        logger.info("init of "+self.__class__.__name__)
        self.bus = bus

    def is_done(self):
        raise NotImplementedError()

    def step(self, time):
        logger.info("step of "+self.__class__.__name__)
        pass

class MoveTo(BusJob):
    def __init__(self, edge, stop_pos=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
    STATE_NOT_STARTED = 0
    STATE_IDLE = 1
    STATE_FINISHED = 2
    def __init__(self, until, *args,pos=None,**kwargs):
        super().__init__(*args, **kwargs)
        self.until = until
        self.pos = pos
        self.state=self.STATE_NOT_STARTED
    
    def step(self, time):
        super().step(time)
        if self.until - 3 < time:
            self.state = self.STATE_FINISHED
        if self.state == self.STATE_NOT_STARTED:
            self.bus.wait(self.until - time, self.pos, tc.STOP_PARKING)
            self.state = self.STATE_IDLE
    def is_done(self):
        return self.state == self.STATE_FINISHED

class BusStation(BusJob):
    DURATION=50
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_time = None
        self.current_time = None

    def step(self, time):
        super().step(time)
        self.current_time = time
        if self.start_time is None:
            self.start_time = time
            self.bus.wait(self.DURATION)
        
    def is_done(self):
        return self.start_time is not None and self.current_time > self.start_time + self.DURATION

class Bus:
    def __init__(self, id, start_edge, end_edge, type="BUS_S"):
        self.id = id
        self.start_edge=start_edge
        self.end_edge=end_edge
        self.jobs = []
        traci.vehicle.add(
            vehID=self.id,
            typeID=type,
            routeID="",
            depart=0,
            departPos=0,
            departSpeed=0,
            personCapacity=4
        )
    
    def get_pos(self):
        return traci.vehicle.getLanePosition(self.id)

    def get_edge(self):
        return traci.vehicle.getRoadID(self.id)

    def get_lane(self):
        return traci.vehicle.getLaneID(self.id)

    def get_lane_idx(self):
        return traci.vehicle.getLaneIndex(self.id)

    def is_stopped(self):
        return traci.vehicle.isStopped(self.id)

    def move_to(self, edge, stop_pos=None):
        if stop_pos is not None and self.get_edge() == edge and self.get_pos() > stop_pos:
            if current_edge.startswith("-"):
                opposite_edge = current_edge[1:]
            else:
                opposite_edge = "-"+current_edge
            self.jobs = [MoveTo(opposite_edge, self.bus), MoveTo(edge, self.bus, stop_pos)] + self.jobs
        else:
            traci.vehicle.changeTarget(self.id, edge)
            if stop_pos is not None:
                
                logger.info("Setting Stop at " + str(stop_pos))
                n_stops=len(traci.vehicle.getStops(self.id))
                if n_stops > 0:
                    traci.vehicle.replaceStop(self.id, 0, edge, stop_pos, 1, 10)                
                else:
                    traci.vehicle.setStop(self.id, edge, stop_pos, 1, 10)

    def wait(self, duration, pos=None, type=tc.STOP_DEFAULT):
        stops = traci.vehicle.getStops(self.id)
        if len(stops) > 0 and (pos is None or stops[0].endPos==pos):
            traci.vehicle.replaceStop(self.id, 0, self.get_edge(), stops[0].endPos, 1, duration, type)
        else:
            if pos is None:
                pos = self.get_pos()
            for i in range(0,200,10):
                try:
                    logger.info([duration, pos, type])
                    traci.vehicle.setStop(self.id, self.get_edge(), pos+i, self.get_lane_idx(), duration, type)
                    break
                except:
                    pass
    def step(self, time):
        while len(self.jobs) > 0 and self.jobs[0].is_done():
            logger.info("Job {} is done".format(self.jobs[0].__class__.__name__))
            self.jobs = self.jobs[1:]

        if len(self.jobs) == 0:
            logger.info("Adding IDLE job")
            self.jobs.append(IDLE(time+10, self))

        self.jobs[0].step(time)

class PickupJob:
    STOP_DURATION = 10
    def __init__(self, passenger, bus):
        self.passenger = passenger
        self.bus = bus
        self.bus.set_job(self)
        self.picked_up = False
        self.done=False
        self.first_time = None

    def start(self):
        self.bus.go_to(self.passenger.edge_from, self.passenger.position_from, park=True)

    def step(self, time):
        if self.first_time is None:
            self.first_time = time
        if "Arrived" in traci.person.getStage(self.passenger.id).description:
            self.done = True
        elif time - self.first_time > 50 and not self.picked_up and traci.vehicle.isStopped(self.bus.id) and time >= self.passenger.depart:
            logger.info(["Set True",self.picked_up,traci.vehicle.isStopped(self.bus.id), time >= self.passenger.depart,traci.person.getStage(self.passenger.id).description, self.passenger.id])
            self.picked_up = True
            self.bus.go_to(self.passenger.edge_from, self.passenger.position_from)
            self.bus.go_to(self.passenger.edge_to, self.passenger.position_to)
        else:
            self.bus.go_to(self.passenger.edge_from, self.passenger.position_from, park=True)
            logger.info(["Stuck",self.picked_up,traci.vehicle.isStopped(self.bus.id), time >= self.passenger.depart,traci.person.getStage(self.passenger.id).description, self.passenger.id])

        if time-self.first_time > 1000:
            raise Exception()

class ExampleSimulation(_Stage1Scorer):
    """ The example simulation provided by ELCA
    """
    def setup(self):
        n_pedestrians = len(self.pedestrians)
        for bus_index, person in enumerate(self.pedestrians):
            logger.info("Generating bus route {}/{}".format(bus_index, n_pedestrians))
            
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

class FixedNBusesSimulation(_StageScorer):
    N_BUSES = 1
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.deployed_buses = set()
        self.next_passenger_index = 0

    def setup(self):
        # Sort passengers by their departure time
        self.pedestrians = sorted(self.pedestrians, key=lambda x:x.depart)

        for i in range(self.N_BUSES):
            bus = Bus(f'bus_{i}', self.bus_depot_start_edge, self.bus_depot_end_edge)
            self.deployed_buses.add(bus)
            raise Exception()
            pickup_job = PickupJob(self.pedestrians[self.next_passenger_index], bus)
            pickup_job.start()
            self.next_passenger_index += 1

    def step(self, time):
        for bus in self.deployed_buses:
            bus.step(time)
            if bus.job is None:
                if self.next_passenger_index < len(self.pedestrians):
                    pickup_job = PickupJob(self.pedestrians[self.next_passenger_index], bus)
                    pickup_job.start()
                    logger.info(["Picking up", self.next_passenger_index])
                    self.next_passenger_index += 1
                    input()

