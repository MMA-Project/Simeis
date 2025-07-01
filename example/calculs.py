import math


prixdumarche = 8

def calculate_all_gain(cargo_capacity, pilotrank, traderrank, len_modules, opranks, module_rank, reactor_power, shield_power, planet_distance):
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
    # print(f"Extraction Time: {extraction_time:.2f} seconds | Extraction rate: {extraction_rate:.2f} units/sec")
    travel_time = planet_distance / speed
    # print(f"Travel time: {travel_time:.2f} seconds at speed {speed:.2f} m/s")
    fuelcost =  travel_time*2* fuel_consumption*2
    # print(f"Fuel cost: {fuelcost:.2f} | Fuel usage: {fuel_consumption:.2f} units/sec")
    hullcost = hull_usage * planet_distance*2*0.05
    # print(f"Hull cost: {hullcost:.2f} | Hull usage: {hull_usage:.2f}")
    totaltime = travel_time * 2 + extraction_time
    # print(f"Total time for the operation: {totaltime:.2f} seconds")

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
    # print(f"Total crew wages: {wages:.2f} per second")

    # Calcul du gain total
    fees = 0.26 / (traderrank ** 1.15)
    selling_price = (1 - fees) * prixdumarche
    allgain = (cargo_capacity / 0.75 * selling_price) - fuelcost - hullcost - (wages * totaltime)
    gainratio = allgain/totaltime
    print(f"Gain total: \033[91m{allgain:.2f}\033[0m | Gain par seconde: \033[91m{gainratio:.2f}\033[0m")
    return gainratio



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


# cargo_capacity += 150
# pilotrank += 1
# traderrank += 1
# len_modules += 1
# opranks.append(1)
# module_rank.append(1)
# opranks[0]+= 1
# module_rank[0] += 1
# reactor_power += 1
# shield_power += 1
#planet_distance = 500


def percent_color(p):
    p = max(-100, min(100, p))
    r = int(255 * (1 - max(0, p) / 100))
    g = int(255 * (max(0, p) / 100))
    return f"\033[38;2;{r};{g};0m"


current_gain_ratio = calculate_all_gain(cargo_capacity, pilotrank, traderrank, len_modules, opranks, module_rank, reactor_power, shield_power, planet_distance)
newgainratio = calculate_all_gain(cargo_capacity, pilotrank, traderrank, len_modules, opranks, module_rank, reactor_power, shield_power, planet_distance)
percent_change = newgainratio * 100 / current_gain_ratio - 100
print(f"{percent_color(percent_change)}{percent_change:.2f} %\033[0m de gain par rapport à l'ancienne version")

percent_change= 100
while percent_change > 0.1:
    current_gain_ratio = calculate_all_gain(
        cargo_capacity, pilotrank, traderrank, len_modules, opranks, module_rank, reactor_power, shield_power, planet_distance
    )

    # Propositions d'amélioration
    up_cargo_capacity = cargo_capacity + 150
    up_pilotrank = pilotrank + 1
    up_traderrank = traderrank + 1
    new_len_modules = len_modules + 1
    new_opranks = opranks + [1]
    new_module_rank = module_rank + [1]
    up_opranks = opranks.copy()
    up_module_rank = module_rank.copy()
    up_opranks[0] += 1
    up_module_rank[0] += 1
    up_reactor_power = reactor_power + 1
    up_shield_power = shield_power + 1

    all_new_percent_change = []

    # Calcul des gains pour chaque amélioration possible
    all_new_percent_change.append(
        ("cargo_capacity", up_cargo_capacity, calculate_all_gain(up_cargo_capacity, pilotrank, traderrank, len_modules, opranks, module_rank, reactor_power, shield_power, planet_distance) * 100 / current_gain_ratio - 100)
    )
    all_new_percent_change.append(
        ("pilotrank", up_pilotrank, calculate_all_gain(cargo_capacity, up_pilotrank, traderrank, len_modules, opranks, module_rank, reactor_power, shield_power, planet_distance) * 100 / current_gain_ratio - 100)
    )
    all_new_percent_change.append(
        ("traderrank", up_traderrank, calculate_all_gain(cargo_capacity, pilotrank, up_traderrank, len_modules, opranks, module_rank, reactor_power, shield_power, planet_distance) * 100 / current_gain_ratio - 100)
    )
    all_new_percent_change.append(
        ("new_modules", new_len_modules, calculate_all_gain(cargo_capacity, pilotrank, traderrank, new_len_modules, new_opranks, new_module_rank, reactor_power, shield_power, planet_distance) * 100 / current_gain_ratio - 100)
    )
    # all_new_percent_change.append(
    #     ("opranks", new_opranks, calculate_all_gain(cargo_capacity, pilotrank, traderrank, len_modules, new_opranks, module_rank, reactor_power, shield_power, planet_distance) * 100 / current_gain_ratio - 100)
    # )
    # all_new_percent_change.append(
    #     ("module_rank", new_module_rank, calculate_all_gain(cargo_capacity, pilotrank, traderrank, len_modules, opranks, new_module_rank, reactor_power, shield_power, planet_distance) * 100 / current_gain_ratio - 100)
    # )
    all_new_percent_change.append(
        ("opranks_mod", up_opranks, calculate_all_gain(cargo_capacity, pilotrank, traderrank, len_modules, up_opranks, module_rank, reactor_power, shield_power, planet_distance) * 100 / current_gain_ratio - 100)
    )
    all_new_percent_change.append(
        ("module_rank_mod", up_module_rank, calculate_all_gain(cargo_capacity, pilotrank, traderrank, len_modules, opranks, up_module_rank, reactor_power, shield_power, planet_distance) * 100 / current_gain_ratio - 100)
    )
    all_new_percent_change.append(
        ("reactor_power", up_reactor_power, calculate_all_gain(cargo_capacity, pilotrank, traderrank, len_modules, opranks, module_rank, up_reactor_power, shield_power, planet_distance) * 100 / current_gain_ratio - 100)
    )
    all_new_percent_change.append(
        ("shield_power", up_shield_power, calculate_all_gain(cargo_capacity, pilotrank, traderrank, len_modules, opranks, module_rank, reactor_power, up_shield_power, planet_distance) * 100 / current_gain_ratio - 100)
    )

    # Trouver l'amélioration avec le plus grand pourcentage de gain
    best_upgrade = max(all_new_percent_change, key=lambda x: x[2])
    upgrade_name, upgrade_value, percent_change = best_upgrade

    # Appliquer l'amélioration correspondante
    if upgrade_name == "cargo_capacity":
        cargo_capacity = upgrade_value
    elif upgrade_name == "pilotrank":
        pilotrank = upgrade_value
    elif upgrade_name == "traderrank":
        traderrank = upgrade_value
    elif upgrade_name == "new_modules":
        len_modules = upgrade_value
        opranks.append(1)
        module_rank.append(1)
    elif upgrade_name == "opranks_mod":
        opranks = upgrade_value
    elif upgrade_name == "module_rank_mod":
        module_rank = upgrade_value
    elif upgrade_name == "reactor_power":
        reactor_power = upgrade_value
    elif upgrade_name == "shield_power":
        shield_power = upgrade_value
    else:
        break  # Sécurité

    print(f"Amélioration: {upgrade_name} -> {upgrade_value} | Gain: {percent_color(percent_change)}{percent_change:.2f}%\033[0m")
    
    
    
print(f"Max cargo capacity: {cargo_capacity}")
print(f"Max pilot rank: {pilotrank}")
print(f"Max trader rank: {traderrank}")
print(f"Max modules: {len_modules}")
print(f"Max operator ranks: {opranks}")
print(f"Max module ranks: {module_rank}")
print(f"Max reactor power: {reactor_power}")
print(f"Max shield power: {shield_power}")
