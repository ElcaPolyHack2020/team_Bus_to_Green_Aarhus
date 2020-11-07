# Generate random network
netgenerate -r --rand.iterations 10 -o data/rand.net.xml --sidewalks.guess --crossings.guess --tls.guess --tls.guess.threshold 45 --seed $(date +%s)

# Generate traffic
randomTrips.py -n data/rand.net.xml -o data/rand.rou.xml --period 1.5 -e 60
randomTrips.py -n data/rand.net.xml -o data/rand-ped.rou.xml --pedestrians -e 60