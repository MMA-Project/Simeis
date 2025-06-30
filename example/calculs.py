import math


prixdumarche = 8

# Initialisation des variables
cargo_capacity = 200
pilotrank = 1
traderrank = 1
len_modules = 1
opranks = [1]
module_rank = [1]
reactor_power = 1
shield_power = 0
planet_distance = 500

# Calculs pour le voyage
speed = pilotrank*reactor_power * 50
hull_usage = 0.05 / (1.0 + math.log(1.0 + shield_power, 3.5))
fuel_consumption = reactor_power
fuel_consumption *= ((5 * 10) - pilotrank) / (5 * 10)

# Calculs pour l'extraction
extraction_rate = 0.0
for i in range(len_modules):
    rank = (opranks[i] - 0) * module_rank[i]
    difficulty = 0.25 ** 2.5
    extraction_rate += (6.25 * (rank / difficulty) ** 0.6)
volume_extracted = cargo_capacity / 0.75
extraction_time = volume_extracted / extraction_rate
print(f"Extraction Time: {extraction_time:.2f} seconds | Extraction rate: {extraction_rate:.2f} units/sec")
travel_time = planet_distance / speed
print(f"Travel time: {travel_time:.2f} seconds at speed {speed:.2f} m/s")
fuelcost =  travel_time*2* fuel_consumption*2
print(f"Fuel cost: {fuelcost:.2f} | Fuel usage: {fuel_consumption:.2f} units/sec")
hullcost = hull_usage * planet_distance*2*0.05
print(f"Hull cost: {hullcost:.2f} | Hull usage: {hull_usage:.2f}")
totaltime = travel_time * 2 + extraction_time
print(f"Total time for the operation: {totaltime:.2f} seconds")

# Calcul des salaires de l'équipage
def crew_wage(member_type, rank):
    base = {
        "Pilot": 5.5,
        "Operator": 0.9,
        "Trader": 2.6,
        "Soldier": 1.5,
    }.get(member_type, 1.0)
    return base * (rank ** 0.85)
crew = [
    {"member_type": "Trader", "rank": traderrank},
    {"member_type": "Pilot", "rank": pilotrank},
] + [
    {"member_type": "Operator", "rank": opranks[i]} for i in range(len_modules)
]
wages = sum(crew_wage(c["member_type"], c["rank"]) for c in crew)
print(f"Total crew wages: {wages:.2f} per second")

# Calcul du gain total
fees = 0.26 / (traderrank ** 1.15)
selling_price = (1 - fees) * prixdumarche
allgain = (cargo_capacity / 0.75 * selling_price) - fuelcost - hullcost - (wages * totaltime)
gainratio = allgain/totaltime
print(f"Gain total: {allgain:.2f} | Gain par seconde: {gainratio:.2f}")


# cargo_capacity += 150
# pilotrank += 1
traderrank += 1
# len_modules += 1
# opranks.append(1)
# module_rank.append(1)
# reactor_power += 1
# shield_power += 1
#planet_distance = 500

# Calculs pour le voyage
speed = pilotrank*reactor_power * 50
hull_usage = 0.05 / (1.0 + math.log(1.0 + shield_power, 3.5))
fuel_consumption = reactor_power
fuel_consumption *= ((5 * 10) - pilotrank) / (5 * 10)

# Calculs pour l'extraction
extraction_rate = 0.0
for i in range(len_modules):
    rank = (opranks[i] - 0) * module_rank[i]
    difficulty = 0.25 ** 2.5
    extraction_rate += 6.25 * (rank / difficulty) ** 0.6
volume_extracted = cargo_capacity / 0.75
extraction_time = volume_extracted / extraction_rate
travel_time = planet_distance / speed
fuelcost =  travel_time* fuel_consumption*2
hullcost = hull_usage * planet_distance*0.05
totaltime = travel_time * 2 + extraction_time

# Calcul des salaires de l'équipage
def crew_wage(member_type, rank):
    base = {
        "Pilot": 5.5,
        "Operator": 0.9,
        "Trader": 2.6,
        "Soldier": 1.5,
    }.get(member_type, 1.0)
    return base * (rank ** 0.85)
crew = [
    {"member_type": "Trader", "rank": traderrank},
    {"member_type": "Pilot", "rank": pilotrank},
] + [
    {"member_type": "Operator", "rank": opranks[i]} for i in range(len_modules)
]
wages = sum(crew_wage(c["member_type"], c["rank"]) for c in crew)

# Calcul du gain total
fees = 0.26 / (traderrank ** 1.15)
selling_price = (1 - fees) * prixdumarche
allgain = (cargo_capacity / 0.75 * selling_price) - fuelcost - hullcost - (wages * totaltime)
newgainratio = allgain/totaltime
print(f"Gain total: {allgain:.2f} | Gain par seconde: {newgainratio:.2f}")
print(f"{newgainratio*100/ gainratio:.2f} % de gain par rapport à l'ancienne version")
