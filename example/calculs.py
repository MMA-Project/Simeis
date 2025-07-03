import math

#API Constants
ITER_PERIOD = 20 #ms
REACTOR_SPEED_PER_POWER=50
PILOT_FUEL_SHARE=5
HULL_USAGE_BASE = 0.05
EXRATE_FACT=0.6
EXRATE_DIFF_FACT=2.5
CARGO_EXP_ADD_CAP=150
CARGO_CAP_PRICE=20
SHIELD_PRICE=2500
REACTOR_POWER_PRICE=4000
WAGE_INC_RANK_POWF=0.85
RANK_PRICE_WAGE_MULT=1900
MOD_UPG_POWF_DIV=75

tier1price = 4*2
tier2price = 16*2
tier3price = 46*2
tier4price = 80*2

tier1diff = 0.25
tier2diff = 0.7
tier3diff = 1.9
tier4diff = 2.95

tier1volume = 0.75
tier2volume = 2.5
tier3volume = 3.0
tier4volume = 0.25

tier1opminrank = 0
tier2opminrank = 2
tier3opminrank = 5
tier4opminrank = 9

resources={
    "tier1": {
        "price": tier1price,
        "difficulty": tier1diff,
        "volume": tier1volume,
        "opminrank": tier1opminrank,
    },
    "tier2": {
        "price": tier2price,
        "difficulty": tier2diff,
        "volume": tier2volume,
        "opminrank": tier2opminrank,
    },
    "tier3": {
        "price": tier3price,
        "difficulty": tier3diff,
        "volume": tier3volume,
        "opminrank": tier3opminrank,
    },
    "tier4": {
        "price": tier4price,
        "difficulty": tier4diff,
        "volume": tier4volume,
        "opminrank": tier4opminrank,
    },
}

# Upgrades prices
CargoExpansionPrice = CARGO_CAP_PRICE*CARGO_EXP_ADD_CAP
ShieldPrice = SHIELD_PRICE
ReactorPowerPrice = REACTOR_POWER_PRICE
def crew_wage(member_type, rank):
    base = {
        "Pilot": 5.5,
        "Operator": 0.9,
        "Trader": 2.6,
        "Soldier": 1.5,
    }.get(member_type, 1.0)
    return base * (rank ** WAGE_INC_RANK_POWF)
def get_crew_upgrade_price(member_type, rank):
    base_price = crew_wage(member_type, rank)
    return base_price * RANK_PRICE_WAGE_MULT

def calculate_all_gain(cargo_capacity, pilotrank, traderrank, len_modules, opranks, module_rank, reactor_power, shield_power, planet_distance):
    #Cap
    if shield_power > 2 or traderrank >16:
        return -1
    # Calculs pour le voyage
    speed = pilotrank*reactor_power * REACTOR_SPEED_PER_POWER
    hull_usage = HULL_USAGE_BASE / (1.0 + math.log(1.0 + shield_power, 3.5))
    fuel_consumption = reactor_power
    fuel_consumption *= ((PILOT_FUEL_SHARE * 10) - pilotrank) / (PILOT_FUEL_SHARE * 10)

    # 1. Initialisation
    extraction_rates = {tier: 0.0 for tier in resources}
    volumes_extracted = {tier: 0.0 for tier in resources}

    # 2. Calcul des extraction rates par tier (ressource)
    for i in range(len_modules):
        operator_rank = opranks[i]
        module_level = module_rank[i]

        for tier_name, tier_data in resources.items():
            if operator_rank >= tier_data["opminrank"]:
                rank_effective = (operator_rank - tier_data["opminrank"]) * module_level
                difficulty = tier_data["difficulty"] ** EXRATE_DIFF_FACT
                rate = 6.25 * (rank_effective / difficulty) ** EXRATE_FACT
                extraction_rates[tier_name] += rate

    # 3. Remplir le cargo selon le volume et le taux d'extraction
    remaining_capacity = cargo_capacity
    extraction_time = 0.0

    while remaining_capacity > 0:
        for tier_name, extraction_rate in extraction_rates.items():
            if extraction_rate <= 0:
                continue
            volume_extracted = extraction_rate * resources[tier_name]["volume"] * (ITER_PERIOD / 1000.0)  # Convert ms to seconds
            if remaining_capacity - volume_extracted < 0:
                volume_extracted = remaining_capacity
            volumes_extracted[tier_name] += volume_extracted
            remaining_capacity -= volume_extracted
        extraction_time += (ITER_PERIOD / 1000.0)
    
    # print("Extracted volumes:")
    # for tier_name, volume in volumes_extracted.items():
    #     print(f" - {tier_name}: {volume:.2f} units")
        
    prixdevente = 0.0
    for tier_name, volume in volumes_extracted.items():
        if volume > 0:
            tier_data = resources[tier_name]
            prixdevente += volume / tier_data["volume"] * tier_data["price"]

    print(f"Extraction Time: {extraction_time:.2f} seconds")
    travel_time = planet_distance / speed
    if travel_time < ITER_PERIOD / 1000.0 * 2 or extraction_time < ITER_PERIOD / 1000.0 * 2:
        return -1
    # print(f"Travel time: {travel_time:.2f} seconds at speed {speed:.2f} m/s")
    fuelcost =  travel_time * 2 * fuel_consumption * 2
    # print(f"Fuel cost: {fuelcost:.2f} | Fuel usage: {fuel_consumption:.2f} units/sec")
    hullcost = hull_usage * planet_distance * 2 * 0.05
    # print(f"Hull cost: {hullcost:.2f} | Hull usage: {hull_usage:.2f}")
    totaltime = travel_time * 2 + extraction_time
    # print(f"Total time for the operation: {totaltime:.2f} seconds")
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
    selling_price = (1 - fees) * prixdevente
    allgain = selling_price - fuelcost - hullcost - (wages * totaltime)
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

current_gain_ratio = calculate_all_gain(cargo_capacity, pilotrank, traderrank, len_modules, opranks, module_rank, reactor_power, shield_power, planet_distance)

# cargo_capacity += 150
# pilotrank += 1
# traderrank += 1
# len_modules += 1
# opranks.append(1)
# module_rank.append(1)
# opranks[0] += 5
# module_rank[0] += 1
# reactor_power += 1
# shield_power += 1
#planet_distance = 500


def percent_color(p):
    p = max(-100, min(100, p))
    r = int(255 * (1 - max(0, p) / 100))
    g = int(255 * (max(0, p) / 100))
    return f"\033[38;2;{r};{g};0m"


newgainratio = calculate_all_gain(cargo_capacity, pilotrank, traderrank, len_modules, opranks, module_rank, reactor_power, shield_power, planet_distance)
percent_change = newgainratio * 100 / current_gain_ratio - 100
print(f"{percent_color(percent_change)}{percent_change:.2f} %\033[0m de gain par rapport à l'ancienne version")

all_new_percent_change = [("",1,100,0)]  # Liste pour stocker les améliorations possibles
while any(upgrade[2] > 0 for upgrade in all_new_percent_change):
    
    current_gain_ratio = calculate_all_gain(
        cargo_capacity, pilotrank, traderrank, len_modules, opranks, module_rank, reactor_power, shield_power, planet_distance
    )

    # Propositions d'amélioration
    up_cargo_capacity = cargo_capacity + CARGO_EXP_ADD_CAP
    up_pilotrank = pilotrank + 1
    up_traderrank = traderrank + 1
    new_len_modules = len_modules + 1
    new_opranks = opranks + [1]
    new_module_rank = module_rank + [1]
    up_reactor_power = reactor_power + 1
    up_shield_power = shield_power + 1

    all_new_percent_change = []

    # Calcul des gains pour chaque amélioration possible
    if cargo_capacity < 66000:
        all_new_percent_change.append(
            ("cargo_capacity", up_cargo_capacity, abs(calculate_all_gain(up_cargo_capacity, pilotrank, traderrank, len_modules, opranks, module_rank, reactor_power, shield_power, planet_distance) * 100 / current_gain_ratio - 100), CargoExpansionPrice)
        )
    all_new_percent_change.append(
        ("pilotrank", up_pilotrank, calculate_all_gain(cargo_capacity, up_pilotrank, traderrank, len_modules, opranks, module_rank, reactor_power, shield_power, planet_distance) * 100 / current_gain_ratio - 100, get_crew_upgrade_price("Pilot", pilotrank))
    )
    all_new_percent_change.append(
        ("traderrank", up_traderrank, calculate_all_gain(cargo_capacity, pilotrank, up_traderrank, len_modules, opranks, module_rank, reactor_power, shield_power, planet_distance) * 100 / current_gain_ratio  - 100, get_crew_upgrade_price("Trader", traderrank))
    )
    all_new_percent_change.append(
        ("new_modules", new_len_modules, calculate_all_gain(cargo_capacity, pilotrank, traderrank, new_len_modules, new_opranks, new_module_rank, reactor_power, shield_power, planet_distance) * 100 / current_gain_ratio - 100, 4500.0+1710)
    )
    all_new_percent_change.append(
        ("reactor_power", up_reactor_power, calculate_all_gain(cargo_capacity, pilotrank, traderrank, len_modules, opranks, module_rank, up_reactor_power, shield_power, planet_distance) * 100 / current_gain_ratio - 100, ReactorPowerPrice)
    )
    all_new_percent_change.append(
        ("shield_power", up_shield_power, calculate_all_gain(cargo_capacity, pilotrank, traderrank, len_modules, opranks, module_rank, reactor_power, up_shield_power, planet_distance) * 100 / current_gain_ratio - 100, ShieldPrice)
    )
    
    # Pour chaque module, proposer une amélioration individuelle de opranks et module_rank
    for i in range(len_modules):
        up_opranks_i = opranks.copy()
        up_opranks_i[i] += 1
        upopprice=0
        project_opranks_i = up_opranks_i.copy()
        project_opranks_i[i] += 4
        all_new_percent_change.append(
            ("opranks_mod", up_opranks_i, (calculate_all_gain(cargo_capacity, pilotrank, traderrank, len_modules, project_opranks_i, module_rank, reactor_power, shield_power, planet_distance) * 100 / current_gain_ratio - 100), get_crew_upgrade_price("Operator", opranks[i]))
        )
        up_module_rank_i = module_rank.copy()
        up_module_rank_i[i] += 1
        all_new_percent_change.append(
            ("module_rank_mod", up_module_rank_i, calculate_all_gain(cargo_capacity, pilotrank, traderrank, len_modules, opranks, up_module_rank_i, reactor_power, shield_power, planet_distance) * 100 / current_gain_ratio - 100, 4500**((MOD_UPG_POWF_DIV - 1.0 + module_rank[i]) / MOD_UPG_POWF_DIV))
        )
        
    print("Améliorations possibles:")
    for upgrade in all_new_percent_change:
        upgrade_name, upgrade_value, percent_change, upgrade_cost = upgrade
        if percent_change <= 0:
            continue
        print(f"{upgrade_name}: {upgrade_value} | Gain: {percent_color(percent_change)}{percent_change:.2f}%\033[0m | Coût: {upgrade_cost:.2f}")

    # Trouver l'amélioration avec le plus grand pourcentage de gain
    best_upgrade = max(all_new_percent_change, key=lambda x: x[2] / x[3] if x[3] != 0 else float('-inf'))
    upgrade_name, upgrade_value, percent_change, upgrade_cost = best_upgrade if best_upgrade[2] > 0 else (None, None, 0, 0)

    # Appliquer l'amélioration correspondante
    if upgrade_name == "cargo_capacity":
        cargo_capacity = upgrade_value
    elif upgrade_name == "pilotrank":
        pilotrank = upgrade_value
    elif upgrade_name == "traderrank":
        traderrank = upgrade_value
    elif upgrade_name == "new_modules":
        len_modules = upgrade_value
        opranks+=[1]
        module_rank+=[1]
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

    print(f"\033[92mAmélioration: {upgrade_name}\033[0m | Gain: {percent_color(percent_change)}{percent_change:.2f}%\033[0m | Coût: {upgrade_cost:.2f}\033[0m")
    
    
    
print(f"Max cargo capacity: {cargo_capacity}")
print(f"Max pilot rank: {pilotrank}")
print(f"Max trader rank: {traderrank}")
print(f"Max modules: {len_modules}")
print(f"Max operator ranks: {opranks}")
print(f"Max module ranks: {module_rank}")
print(f"Max reactor power: {reactor_power}")
print(f"Max shield power: {shield_power}")