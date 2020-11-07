# Generate random network
netgenerate -r --rand.iterations 30 -o rand.net.xml --sidewalks.guess --crossings.guess --tls.guess --tls.guess.threshold 45 --seed $(date +%s)

# Generate traffic
randomTrips.py -n rand.net.xml -o rand.rou.xml --period 3 -e 60
