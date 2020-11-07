from time import sleep
import sys
import traci
import traci.constants as tc
import logging

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

    def step(self):
        """ Things that are done in every step of the simulation
        """
        pass

    def run(self):
        # Initialize our algorithms
        self.setup()
        for s in range(self.simulation_steps):
            # Advance the simulation
            traci.simulationStep()
            # Do the next task
            self.step()
            # Update the stats that we use for scoring
            self.update_stats()

class _Stage1Scorer(_BaseSimulation):
    N_BUSES_WEIGHT=1000
    NOT_ARRIVED_WEIGHT=1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.not_arrived_persons = 0
        self.buses = set()
    
    def update_stats(self):
        self.buses|={id for id in traci.vehicle.getIDList() if id.startswith("bus")}
    
    def get_score(self):
        not_arrived = sum([1 for id in traci.person.getIDList() if "Arrived" not in traci.person.getStage(id).description])
        return len(self.buses)*self.N_BUSES_WEIGHT + not_arrived*self.NOT_ARRIVED_WEIGHT

class _Stage2Scorer(_BaseSimulation):
    N_BUSES_WEIGHT=1000
    WAIT_TIME_WEIGHT=1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.total_waiting_time = 0
        self.buses = set()
    
    def update_stats(self):
        person_ids = traci.person.getIDList()
        self.total_waiting_time += sum([1 for id in person_ids if traci.person.getStage(id).type == 1])
        self.buses|={id for id in traci.vehicle.getIDList() if id.startswith("bus")}
    
    def get_score(self):
        return len(self.buses)*self.N_BUSES_WEIGHT + self.total_waiting_time*self.WAIT_TIME_WEIGHT

class ExampleSimulation(_Stage1Scorer):
    """ The example simulation provided by ELCA
    """
    def setup(self):
        n_pedestrians = len(self.pedestrians)
        for bus_index, person in enumerate(self.pedestrians):
            logger.info("Generating bus route {}/{}".format(bus_index, n_pedestrians))
            
            bus_id = f'bus_{bus_index}'
            bus_index += 1

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
        