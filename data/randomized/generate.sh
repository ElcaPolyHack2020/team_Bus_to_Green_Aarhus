# Generate random network
netgenerate -r --rand.iterations 30 -o rand.net.xml --sidewalks.guess --crossings.guess --seed 30

# Generate traffic
randomTrips.py -n rand.net.xml -o rand.rou.xml --period 3 -e 3600
