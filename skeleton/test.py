#!/usr/bin/python3

import os
import sys
import xml.etree.ElementTree as ET
import random
import csv

#SUMO_HOME
# os.environ["SUMO_HOME"] = r"C:\Temp\sumo-win64-git\sumo-git"

# Add the traci python library to the tools path
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")

# Load traci
import traci
import traci.constants as tc
from simulation import *

def test(
    sim_cls,
    simulation_steps = 60 * 60,
    seed=30,
    n_pedestrians=10,
    sumo_cfg=os.path.join("test_data","rand.sumocfg"),
    network=os.path.join("test_data","rand.net.xml"),
    bus_depot = '-269',
    gui=False):

    if gui:
        sumoBinary = os.path.join(os.environ['SUMO_HOME'], 'bin', 'sumo-gui')
    else:
        sumoBinary = os.path.join(os.environ['SUMO_HOME'], 'bin', 'sumo')

    sumoCmd = [sumoBinary, "-c", sumo_cfg]
    traci.start(sumoCmd)

    pedestrians = add_pedestrians(seed=seed, net_xml_file=network, max_steps=simulation_steps, n_pedestrians=n_pedestrians)

    simulation = sim_cls(simulation_steps, 0, pedestrians, bus_depot, bus_depot)
    simulation.run()

    score = simulation.get_score()    
    return traci #traci.close()
    return score

def add_pedestrians(seed: int, net_xml_file: str, max_steps: int, n_pedestrians:int):
    pedestrians = generate_random_people(seed=seed, net_xml_file=net_xml_file, max_steps=max_steps,n_pedestrians=n_pedestrians)

    for person in pedestrians:
        id = person.id
        edge_from = person.edge_from
        edge_to = person.edge_to
        position_from = person.position_from
        position_to = person.position_to
        depart = person.depart

        traci.person.add(personID=id, edgeID=edge_from, pos=position_from, depart=depart, typeID='DEFAULT_PEDTYPE')
        stage = traci.simulation.Stage(type=tc.STAGE_DRIVING, line="ANY", edges=[edge_to],
                                       departPos=0, arrivalPos=position_to, description="Driven as passenger")
        traci.person.appendStage(id, stage)
        waitingStage = traci.simulation.Stage(type=tc.STAGE_WAITING, edges=[edge_to], travelTime=200, description="Arrived at destination")
        traci.person.appendStage(id, waitingStage)

    return pedestrians

with open(os.path.join("test_data","firstnames.txt")) as f:
    first_names = [name.strip() for name in f.readlines()]
with open(os.path.join("test_data","lastnames.txt")) as f:
    last_names = [name.strip() for name in f.readlines()]

def random_name(persId):
    h = hash(str(persId))
    first_name = first_names[h%len(first_names)]
    last_name = last_names[(h%(len(first_names)*len(last_names)))//len(first_names)]
    return "{} {}".format(first_name, last_name)

def generate_random_people(seed: int, net_xml_file: str, max_steps: int, n_pedestrians:int):
    tree = ET.parse(net_xml_file)
    root = tree.getroot()

    edges = []
    for edge in root.findall('.//edge'):
        if edge.attrib['id'].startswith(':'):
            continue
        edges.append(edge)

    random.seed(seed)

    people = []
    for i in range(n_pedestrians):
        edge1 = random.choice(edges)
        edge2 = random.choice(edges)
        
        len1 = float(edge1.findall('./lane')[0].attrib['length'])
        len2 = float(edge2.findall('./lane')[0].attrib['length'])
        
        pos1 = random.uniform(len1 * 0.4, len1 * 0.6)
        pos2 = random.uniform(len2 * 0.4, len2 * 0.6)
        
        depart = random.randint(0, max_steps//2)
        
        person = Person(f'{random_name(i)} ({i})', edge1.attrib['id'], edge2.attrib['id'], pos1, pos2, depart)
        people.append(person)
    return people

class Person:
    # init method or constructor
    def __init__(self, id: str, edge_from: str, edge_to: str, position_from: float, position_to: float, depart: float):
        self.id = id
        self.edge_from = edge_from
        self.edge_to = edge_to
        self.position_from = position_from
        self.position_to = position_to
        self.depart = depart

class PedestrianWeight:
    # init method or constructor
    def __init__(self, t0: int, t1: int, weight: float):
        self.t0 = t0
        self.t1 = t1
        self.weight = weight

if __name__ == '__main__':

    score = test(
        FixedNBusesSimulation,
        gui=True,
        n_pedestrians=20
    )
    print("Score:", score)