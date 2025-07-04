PORT=8080
#URL=f"http://103.45.247.164:{PORT}"
URL=f"http://127.0.0.1:{PORT}"

import os
import sys
import math
import time
import json
import string
import urllib.request
import threading
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.console import Console, Group
from rich.live import Live
from vispy import app, scene
import numpy as np
from collections import defaultdict

class SimeisError(Exception):
    pass

# Théorème de Pythagore pour récupérer la distance entre 2 points dans l'espace 3D
def get_dist(a, b):
    return math.sqrt(((a[0] - b[0]) ** 2) + ((a[1] - b[1]) ** 2) + ((a[2] - b[2]) ** 2))

# Check if types are present in the list
def check_has(alld, key, *req):
    alltypes = [c[key] for c in alld.values()]
    return all([k in alltypes for k in req])

def get_ship_logger(sid):
    os.makedirs("logs", exist_ok=True)
    log_file = open(f"logs/ship_{sid}.log", "w", encoding="utf-8", buffering=1)
    return Console(file=log_file, force_terminal=True)


def estimate_gain(kind, id, data):
    if kind == "module":
        current_rank = data["modules"][id]["rank"]
        new_rank = current_rank + 1
        if new_rank > 20:
            return 0.0
        gain_ratio = (new_rank*100  / current_rank) if current_rank > 0 else 200.0
        return (gain_ratio-100)/len(data["modules"])
    elif kind == "newmodule":
        current_modules = len(data["modules"]) 
        new_modules = current_modules + 1
        gain_ratio = (new_modules * 100 / current_modules) if current_modules > 0 else 200.0
        if len(data["modules"])*10000 >= data["cargo"]["capacity"]:
            return 0.0
        return gain_ratio - 100

    elif kind == "crew":
        current_rank = data["crew"][id]["rank"]
        new_rank = current_rank + 1
        if "Pilot" == data["crew"][id]["member_type"] and new_rank > 5:
            return 0.0
        if "Operator" == data["crew"][id]["member_type"] and new_rank > 45:
            return 0.0
        gain_ratio = (new_rank*100  / current_rank) if current_rank > 0 else 200.0
        return (gain_ratio-100)/len(data["modules"])
    
    elif kind == "trader":
        rank = data["crew"][id]["rank"]
        current_fee = 0.26 / (rank ** 1.15)
        new_fee = 0.26 / ((rank + 1) ** 1.15)
        if new_fee <= 0.01:
            return 0
        gain_ratio = (new_fee * 100 / current_fee) if current_fee > 0 else 200.0
        return 100-gain_ratio
    elif kind == "ship":
        current_ships = len(data["ships"]) 
        new_ships = current_ships + 1
        gain_ratio = (new_ships * 100 / current_ships) if current_ships > 0 else 200.0
        return gain_ratio - 100
    elif kind == "shipupgrade":
        if id == "ReactorUpgrade":
            current = data["reactor_power"]
            new = current + 1
            if new > 50: return 0
        elif id == "CargoExpansion":
            current = data["cargo"]["capacity"]
            new = current + 150
            if new > 800000: return 0
        elif id == "HullUpgrade":
            current = data["hull_decay_capacity"]
            new = current 
        elif id == "Shield":
            current = data["shield_power"]
            new = current + 0.01
            if new > 2: return 0
        else:
            return 0.0
        gain_ratio = (new*100 / current) if current > 0 else 110.0
        return gain_ratio-100

    return 0.0

class Game:
    def __init__(self, username):
        # Init connection & setup player
        assert self.get("/ping")["ping"] == "pong"
        print("[*] Connection to server OK")
        self.setup_player(username)

        # Useful for our game loops
        self.pid = self.player["playerId"] # ID of our player
        self.sids = []  # List of all ships we own
        self.username = "".join([c for c in username if c in string.ascii_letters + string.digits]).lower() # Sanitize username
        self.sta = None    # ID of our station

    def get(self, path, **qry):
        if hasattr(self, "player"):
            qry["key"] = self.player["key"]

        tail = ""
        if len(qry) > 0:
            tail += "?"
            tail += "&".join([
                "{}={}".format(k, urllib.parse.quote(v)) for k, v in qry.items()
            ])

        qry = f"{URL}{path}{tail}"
        reply = urllib.request.urlopen(qry, timeout=1)

        data = json.loads(reply.read().decode())
        err = data.pop("error")
        if err != "ok":
            raise SimeisError(err)

        return data

    # If we have a file containing the player ID and key, use it
    # If not, let's create a new player
    # If the player has lost, print an error message
    def setup_player(self, username, force_register=False):
        # Sanitize the username, remove any symbols
        username = "".join([c for c in username if c in string.ascii_letters + string.digits]).lower()

        # If we don't have any existing account
        if force_register or not os.path.isfile(f"./{username}.json"):
            player = self.get(f"/player/new/{username}")
            with open(f"./{username}.json", "w") as f:
                json.dump(player, f, indent=2)       
            print(f"[*] Created player {username}")
            self.player = player

        # If an account already exists
        else:
            with open(f"./{username}.json", "r") as f:
                self.player = json.load(f)
            print(f"[*] Loaded data for player {username}")

        # Try to get the profile
        try:
            player = self.get("/player/{}".format(self.player["playerId"]))

        # If we fail, that must be that the player doesn't exist on the server
        except SimeisError:
            # And so we retry but forcing to register a new account
            return self.setup_player(username, force_register=True)

        # If the player already failed, we must reset the server
        # Or recreate an account with a new nickname
        if player["money"] <= 0.0:
            print("!!! Player already lost, please restart the server to reset the game")
            sys.exit(0)

    def buy_first_ship(self, sta):
        # Get all the ships available for purchasing in the station
        available = self.get(f"/station/{sta}/shipyard/list")["ships"]
        # Get the cheapest option
        cheapest = sorted(available, key = lambda ship: ship["price"])[0]
        print("[💰] Purchasing the first ship for {} credits".format(cheapest["price"]))
        # Buy it
        self.get(f"/station/{sta}/shipyard/buy/" + str(cheapest["id"]))

    def buy_mining_module(self, modtype, sta, sid, logger):
        # Buy the mining module
        all = self.get(f"/station/{sta}/shop/modules")
        mod_id = self.get(f"/station/{sta}/shop/modules/{sid}/buy/{modtype}")["id"]
        logger.log("[💰] Bought a {} module for our ship {} (ID: {})".format(modtype, sid, mod_id))

        # Check if we have the crew assigned on this module
        # If not, hire an operator, and assign it to the mining module of our ship
        ship = self.get(f"/ship/{sid}")
        if not check_has(ship["crew"], "member_type", "Operator"):
            op = self.get(f"/station/{sta}/crew/hire/operator")["id"]
            self.get(f"/station/{sta}/crew/assign/{op}/{sid}/{mod_id}")
            logger.log("[👨‍🔧] Hired an operator, assigned it on the mining module of our ship")
            

    def hire_first_pilot(self, sta, ship):
        # Hire a pilot, and assign it to our ship
        pilot = self.get(f"/station/{sta}/crew/hire/pilot")["id"]
        self.get(f"/station/{sta}/crew/assign/{pilot}/{ship}/pilot")

    def hire_first_trader(self, sta):
        # Hire a trader, assign it on our station
        trader = self.get(f"/station/{sta}/crew/hire/trader")["id"]
        self.get(f"/station/{sta}/crew/assign/{trader}/trading")

    def travel(self, sid, pos,logger):
        costs = self.get(f"/ship/{sid}/navigate/{pos[0]}/{pos[1]}/{pos[2]}")
        logger.log("[🚀] Traveling to {}, will take {}".format(pos, costs["duration"]))
        self.wait_idle(sid, ts=costs["duration"] if costs["duration"] < 1 else 0.1)

    def wait_idle(self, sid, ts=1/10):
        ship = self.get(f"/ship/{sid}")
        while ship["state"] != "Idle":
            time.sleep(ts)
            ship = self.get(f"/ship/{sid}")

    # Repair the ship:     Buy the plates, then ask for reparation
    def ship_repair(self, sid, logger):
        ship = self.get(f"/ship/{sid}")
        req = int(ship["hull_decay"])

        # No need for any reparation
        if req == 0:
            return

        # In case we don't have enough hull plates in stock
        station = self.get(f"/station/{self.sta}")["cargo"]
        if "HullPlate" not in station["resources"]:
            station["resources"]["HullPlate"] = 0
        if station["resources"]["HullPlate"] < req:
            need = req - station["resources"]["HullPlate"]
            bought = self.get(f"/market/{self.sta}/buy/hullplate/{need}")
            logger.log(f"[💰] Bought {need} of hull plates for", bought["removed_money"])
            station = self.get(f"/station/{self.sta}")["cargo"]

        if station["resources"]["HullPlate"] > 0:
            # Use the plates in stock to repair the ship
            repair = self.get(f"/station/{self.sta}/repair/{sid}")
            logger.log("[🔧] Repaired {} hull plates on the ship".format(repair["added-hull"]))

    # Refuel the ship:    Buy the fuel, then ask for a refill
    def ship_refuel(self, sid, logger):
        ship = self.get(f"/ship/{sid}")
        req = int(ship["fuel_tank_capacity"] - ship["fuel_tank"])

        # No need for any refuel
        if req == 0:
            return

        # In case we don't have enough fuel in stock
        station = self.get(f"/station/{self.sta}")["cargo"]
        if "Fuel" not in station["resources"]:
            station["resources"]["Fuel"] = 0
        if station["resources"]["Fuel"] < req:
            need = req - station["resources"]["Fuel"]
            bought = self.get(f"/market/{self.sta}/buy/Fuel/{need}")
            logger.log(f"[💰] Bought {need} of fuel for", bought["removed_money"])
            station = self.get(f"/station/{self.sta}")["cargo"]

        if station["resources"]["Fuel"] > 0:
            # Use the fuel in stock to refill the ship
            refuel = self.get(f"/station/{self.sta}/refuel/{sid}")
            logger.log("[⛽] Refilled {} fuel on the ship".format(
                refuel["added-fuel"],
            ))

    # Initializes the game:
    #     - Ensure our player exists
    #     - Ensure our station has a Trader hired
    #     - Ensure we own a ship
    #     - Setup the ship
    #         - Hire a pilot & assign it to our ship
    #         - Buy a mining module to be able to farm
    #         - Hire an operator & assign it on the mining module of our ship
    def init_game(self):
        # Ensure we own a ship, buy one if we don't
        status = self.get(f"/player/{self.pid}")
        self.sta = list(status["stations"].keys())[0]
        station = self.get(f"/station/{self.sta}")

        if not check_has(station["crew"], "member_type", "Trader"):
            self.hire_first_trader(self.sta)
            print("[👨‍✈️] Hired a trader, assigned it on station", self.sta)

        if len(status["ships"]) == 0:
            self.buy_first_ship(self.sta)
            status = self.get(f"/player/{self.pid}") # Update our status
            
        ships = status["ships"]
        self.sids = [s["id"] for s in ships]
        
        planets = self.get(f"/station/{self.sta}/scan")["planets"]
        # Count number of solid and gaseous planets
        num_solid = sum(1 for p in planets if p["solid"])
        num_gas = sum(1 for p in planets if not p["solid"])
        if num_solid > 0 and num_gas > 0:
            print("[🪐] This is a diverse type sector (contains both solid and gaseous planets)")
        elif num_solid > 0:
            print("[🪐] This is a monotype sector (only solid planets)")
        elif num_gas > 0:
            print("[🪐] This is a monotype sector (only gaseous planets)")
        else:
            print("[🪐] No planets detected in this sector")
        
        print("[✅] Game initialisation finished successfully")

    # - Find the nearest planet we can mine
    # - Go there
    # - Fill our cargo with resources
    # - Once the cargo is full, we stop mining, and this function returns
    def go_mine(self, sid, logger):
        logger.log("[💎] Starting mining operation for ship", sid)
        player = self.get(f"/player/{self.pid}")
        station = self.get(f"/station/{self.sta}")
        planets = self.get(f"/station/{self.sta}/scan")["planets"]
        num_solid = sum(1 for p in planets if p["solid"])
        num_gas = sum(1 for p in planets if not p["solid"])
        ship = self.get(f"/ship/{sid}")

        # Cas spécial : les deux premiers vaisseaux ou les systèmes monotype ignorent le marché
        if len(player["ships"]) < 3 or not (num_solid > 0 and num_gas > 0):
            nearest = sorted(planets, key=lambda p: get_dist(station["position"], p["position"]))[0]
            modtype = "Miner" if nearest["solid"] else "GasSucker"

            if not check_has(ship["modules"], "modtype", modtype):
                logger.log(f"[🛠️] Buying module {modtype} for ship {sid}")
                self.buy_mining_module(modtype, self.sta, sid, logger)
                self.optimize_upgrades(sid, logger)

            logger.log(f"[🪐] Targeting nearest planet at {nearest['position']}")
            self.wait_idle(sid)

            if ship["position"] != nearest["position"]:
                self.travel(sid, nearest["position"], logger)

            info = self.get(f"/ship/{sid}/extraction/start")
            logger.log("[⛏️] Extraction started:")
            for res, amnt in info.items():
                logger.log(f"  - {res}: {amnt}/sec")

            self.wait_idle(sid)
            logger.log("[📦] Cargo full, mining complete")
            return  

        # Cas standard : stratégie pilotée par le marché à partir du 3e vaisseau
        has_miner = check_has(ship["modules"], "modtype", "Miner")
        has_sucker = check_has(ship["modules"], "modtype", "GasSucker")

        if has_miner:
            modtype = "Miner"
        elif has_sucker:
            modtype = "GasSucker"
        else:
            logger.log("[📈] No module found, choosing best based on market")
            market = self.get("/market/prices")["prices"]

            try:
                rel_helium = (market["Helium"] / 8) * 100
                rel_stone = (market["Stone"] / 8) * 100
                logger.log(f"[🧪] Helium: {rel_helium:.1f}% vs Stone: {rel_stone:.1f}%")

                modtype = "GasSucker" if rel_helium > rel_stone else "Miner"
            except KeyError as e:
                logger.log(f"[⚠️] Market missing {e}, defaulting to Miner")
                modtype = "Miner"

            logger.log(f"[🛠️] Buying module {modtype} for ship {sid}")
            self.buy_mining_module(modtype, self.sta, sid, logger)
            self.optimize_upgrades(sid, logger)

        is_solid = (modtype == "Miner")
        matching_planets = sorted(
            [p for p in planets if p["solid"] == is_solid],
            key=lambda p: get_dist(station["position"], p["position"])
        )

        if not matching_planets:
            logger.log(f"[⚠️] No planets available for {modtype} mining")
            return

        target = matching_planets[0]
        logger.log(f"[🪐] Targeting planet at {target['position']}")

        self.wait_idle(sid)

        if ship["position"] != target["position"]:
            self.travel(sid, target["position"], logger)

        info = self.get(f"/ship/{sid}/extraction/start")
        logger.log("[⛏️] Extraction started:")
        for res, amnt in info.items():
            logger.log(f"  - {res}: {amnt}/sec")

        self.wait_idle(sid)
        logger.log("[📦] Cargo full, mining complete")
            

    # - Go back to the station
    # - Unload all the cargo
    # - Sell it on the market
    # - Refuel & repair the ship
    def go_sell(self,sid,logger):
        self.wait_idle(sid) # If we are currently occupied, wait
        ship = self.get(f"/ship/{sid}")
        station = self.get(f"/station/{self.sta}")

        # If we aren't at the station, got there
        if ship["position"] != station["position"]:
            self.travel(ship["id"], station["position"], logger)
        logger.log("[📡] Arrived at station, unloading cargo")
        
        # Sell resources from station cargo if it's full before unloading ship
        station_cargo = station["cargo"]
        if station_cargo["usage"] >= station_cargo["capacity"]:
            for res, amt in station_cargo["resources"].items():
                if amt > 0:
                    sold = self.get(f"/market/{self.sta}/sell/{res}/{amt}")
                    logger.log(f"[💲] Sold {amt:.1f} of {res} from station cargo, gain: {sold['added_money']:.1f} credits")
        
        # Unload the cargo and sell it directly on the market
        for res, amnt in ship["cargo"]["resources"].items():
            total_unloaded = 0.0
            total_earned = 0.0
            amt_left = amnt
            logisticLoop = 0

            while amt_left > 0.0:
                unloaded = self.get(f"/ship/{sid}/unload/{res}/{amt_left}")
                unloaded_amt = unloaded["unloaded"]
                if unloaded_amt == 0.0:
                    break

                sold = self.get(f"/market/{self.sta}/sell/{res}/{unloaded_amt}")
                total_unloaded += unloaded_amt
                total_earned += sold["added_money"]
                amt_left -= unloaded_amt
                logisticLoop += 1

            if total_unloaded > 0:
                logger.log(f"[💲] Unloaded and sold {total_unloaded:.1f} of {res}, total gain: {total_earned:.1f} credits")
                if logisticLoop > 2 and total_earned > 200000:
                    logger.log(f"[🔄] Too much Logistic loop completed, time to make the station great again")
                    unitcargoprice=self.get(f"/station/{self.sta}/upgrades")["cargo-expansion"]
                    new_cargo_price=unitcargoprice*199000
                    if new_cargo_price == 199000:           
                        logger.log(f"[⚙️] Upgrading cargo capacity for {new_cargo_price:.1f} credits")
                        self.get(f"/station/{self.sta}/shop/cargo/buy/{int(199000)}")
                    # if new_cargo_price > max_spend:  
                    #     # Acheter seulement ce qu'on peut se permettre (max_spend)
                    #     affordable_units = max_spend // unitcargoprice
                    #     if affordable_units > 0:
                    #         logger.log(f"[⚠️] Cargo upgrade cost {new_cargo_price:.1f} exceeds 90% of earned ({max_spend:.1f}), buying only {affordable_units:.0f} units")
                    #         self.get(f"/station/{self.sta}/shop/cargo/buy/{int(affordable_units)}")
                    #     else:
                    #         logger.log(f"[⚠️] Cargo upgrade cost {new_cargo_price:.1f} exceeds 90% of earned ({max_spend:.1f}), skipping upgrade")
                    # else:
                    #     logger.log(f"[⚙️] Upgrading cargo capacity for {new_cargo_price:.1f} credits")
                    #     self.get(f"/station/{self.sta}/shop/cargo/buy/{int(59000)}")

        logger.log("[📡] Cargo unloaded, now refueling and repairing the ship")
        self.ship_repair(sid,logger)
        self.ship_refuel(sid,logger)
                
    def optimize_upgrades(self,sid,logger):
        player = self.get(f"/player/{self.pid}")
        money = player["money"]
        ship = self.get(f"/ship/{sid}")
        station= self.get(f"/station/{self.sta}")
        has_miner = check_has(ship["modules"], "modtype", "Miner")
        has_sucker = check_has(ship["modules"], "modtype", "GasSucker")

        if has_miner:
            modtype = "Miner"
        elif has_sucker:
            modtype = "GasSucker"

        upgrades = []

        # Prévisualisation
        mod_preview = self.get(f"/station/{self.sta}/shop/modules/{sid}/upgrade")
        modules = self.get(f"/station/{self.sta}/shop/modules")
        crew_preview = self.get(f"/station/{self.sta}/crew/upgrade/ship/{sid}")
        ship_upgrades = self.get(f"/station/{self.sta}/shipyard/upgrade")
        station_upgrades = self.get(f"/station/{self.sta}/upgrades")
        available = self.get(f"/station/{self.sta}/shipyard/list")["ships"]

        # Modules
        for mod_id in ship["modules"]:
            mod_id_str = str(mod_id)
            if mod_id_str in mod_preview:
                price = mod_preview[mod_id_str]["price"]
                gain = estimate_gain("module", mod_id, ship)
                upgrades.append(("module", mod_id, price, gain))
        new_module_price = modules[modtype] + 4000
        upgrades.append(("newmodule", modtype, new_module_price, estimate_gain("newmodule", modtype, ship)))

        # Crew
        for crew_id in ship["crew"]:
            crew_id_str = str(crew_id)
            if crew_id_str in crew_preview:
                price = crew_preview[crew_id_str]["price"]
                gain = estimate_gain("crew", crew_id, ship)
                upgrades.append(("crew", crew_id, price, gain))

        # Ship upgrades
        for upg, data in ship_upgrades.items():
            price = data["price"]
            gain = estimate_gain("shipupgrade", upg, ship)
            upgrades.append(("shipupgrade", upg, price, gain))
            
        # Trader upgrade
        price = station_upgrades["trader-upgrade"]
        gain = estimate_gain("trader", str(station["trader"]), station)
        upgrades.append(("trader", str(station["trader"]), price, gain))
        
        # New ship
        for ship_data in available:
            ship_id = ship_data["id"]
            price = ship_data["price"]+15000
            gain = estimate_gain("ship", ship_id, player)
            upgrades.append(("ship", ship_id, price, gain))
        
        # Trier par rentabilité
        upgrades.sort(key=lambda u: u[3] / u[2], reverse=True)
        
        # Seuil de ratio
        top_ratio = upgrades[0][3] / upgrades[0][2]
        min_ratio = top_ratio * (1.0 - 0.10)
        shipmoney = money / len(player["ships"])  # Money per ship
        moneyMinCap = shipmoney*0.1+500
        shipUpgradeCap = 100
        while upgrades:
            kind, id_, price, gain = upgrades[0]
            ratio = gain / price

            if ratio < min_ratio:
                logger.log(f"[❌] Skipping {kind} {id_}: ratio too low ({ratio:.4f}) price={price:.1f}, gain={gain:.1f})")
                upgrades.pop(0)  # Enlever de la liste
                continue

            if shipmoney <= price + moneyMinCap:
                logger.log(f"[💸] Not enough money for {kind} {id_}: need {price:.1f}, have {shipmoney:.1f}, gain={gain:.1f}%")
                upgrades.pop(0)
                continue

            try:
                if kind == "module":
                    res = self.get(f"/station/{self.sta}/shop/modules/{sid}/upgrade/{id_}")
                    logger.log(f"[⏫] Module {id_} upgraded for {price:.1f} & gain {gain:.1f}%")
                elif kind == "newmodule":
                    res = self.get(f"/station/{self.sta}/shop/modules/{sid}/buy/{id_}")
                    logger.log(f"[🛠️] New module {id_} bought for {price:.1f} & gain {gain:.1f}%")
                    op = self.get(f"/station/{self.sta}/crew/hire/operator")["id"]
                    self.get(f"/station/{self.sta}/crew/assign/{op}/{sid}/{res['id']}")
                    logger.log("[👨‍🔧] Hired an operator, assigned it on the mining module of our ship")
                elif kind == "crew":
                    res = self.get(f"/station/{self.sta}/crew/upgrade/ship/{sid}/{id_}")
                    logger.log(f"[⏫] Crew {id_} upgraded for {price:.1f} & gain {gain:.1f}%")
                elif kind == "shipupgrade":
                    res = self.get(f"/station/{self.sta}/shipyard/upgrade/{sid}/{id_}")
                    logger.log(f"[⏫] Ship upgrade {id_} for {price:.1f} & gain {gain:.1f}%")  
                    shipUpgradeCap -= 1
                    if shipUpgradeCap <= 0:
                        logger.log("[❗] Ship upgrades cap reached")
                        upgrades.pop(0)
                        continue
                elif kind == "trader":
                    res = self.get(f"/station/{self.sta}/crew/upgrade/trader")
                    logger.log(f"[⏫] Trader upgraded for {price:.1f} & gain {gain:.1f}%")
                elif kind == "ship":
                    res = self.get(f"/station/{self.sta}/shipyard/buy/{id_}")
                    threading.Thread(target=ship_loop, args=(self,id_), daemon=True).start()
                    logger.log(f"[🚀] Bought new ship {id_} for {price:.1f} & gain {gain:.1f}%")
                shipmoney -= price
            except SimeisError as e:
                logger.log(f"[!] Upgrade {kind} {id_} failed:", e)
                upgrades.pop(0)
                continue
            
            ship = self.get(f"/ship/{sid}")
            station = self.get(f"/station/{self.sta}")

            if kind == "module":
                mod_preview = self.get(f"/station/{self.sta}/shop/modules/{sid}/upgrade")
                price = mod_preview[str(id_)]["price"]
                gain = estimate_gain("module", id_, ship)
            elif kind == "newmodule":
                modules = self.get(f"/station/{self.sta}/shop/modules")
                price = modules[modtype] + 4000
                gain = estimate_gain("newmodule", modtype, ship)
            elif kind == "crew":
                crew_preview = self.get(f"/station/{self.sta}/crew/upgrade/ship/{sid}")
                price = crew_preview[str(id_)]["price"]
                gain = estimate_gain("crew", id_, ship)
            elif kind == "shipupgrade":
                gain = estimate_gain("shipupgrade", id_, ship)
            elif kind == "trader":
                station_upgrades = self.get(f"/station/{self.sta}/upgrades")
                price = station_upgrades["trader-upgrade"]
                gain = estimate_gain("trader", id_, station)

            upgrades[0] = (kind, id_, price, gain)
            upgrades.sort(key=lambda u: u[3] / u[2], reverse=True)

            top_ratio = upgrades[0][3] / upgrades[0][2]
            min_ratio = top_ratio * (1.0 - 0.10)
        logger.log(f"[💰] Ship money left after upgrades: {shipmoney:.2f} credits")
                
def launch_galaxy_map(game):
    print(app.use_app()) 

    canvas = scene.SceneCanvas(keys='interactive', show=True, bgcolor='black')
    view = canvas.central_widget.add_view()
    view.camera = scene.cameras.TurntableCamera(fov=45)

    planet_markers = scene.visuals.Markers()
    station_markers = scene.visuals.Markers()
    ship_markers = scene.visuals.Markers()

    view.add(ship_markers)
    view.add(planet_markers)
    view.add(station_markers)

    scan = game.get(f"/station/{game.sta}/scan")
    planets = scan["planets"]
    stations = scan["stations"]

    def get_coords(obj_list):
        return np.array([obj["position"] for obj in obj_list], dtype=np.float32)

    planet_pos = get_coords(planets)
    station_pos = get_coords(stations)

    planet_markers.set_data(planet_pos, face_color='orange', size=20)
    station_markers.set_data(station_pos, face_color='blue', size=20)

    all_static = np.concatenate([planet_pos, station_pos]) if len(station_pos) > 0 else planet_pos
    if len(all_static) > 0:
        center = all_static.mean(axis=0)
        max_dist = np.linalg.norm(all_static - center, axis=1).max()
        view.camera.center = tuple(center)
        view.camera.distance = max(300, max_dist * 2)

    def update(event):
        try:
            ships = game.get(f"/player/{game.pid}")["ships"]
            ship_pos = get_coords(ships)
            ship_markers.set_data(ship_pos, face_color='red', size=10)
            canvas.update()  
        except Exception as e:
            print(f"[!] Update failed: {e}")

    timer = app.Timer(interval=0.1, connect=update, start=True)
    canvas.show()
    app.run()

def render_status(game):
    status = game.get("/player/" + str(game.pid))
    # market = game.get("/market/prices")["prices"]
    gameinfo = game.get("/gamestats")
    # Sort gameinfo by score descending
    gameinfo = dict(sorted(gameinfo.items(), key=lambda item: item[1].get('score', 0), reverse=True))
    # print(gameinfo)
    
    myinfo = None
    for player_id, info in gameinfo.items():
        if info.get("name", "").lower() == game.username:
            myinfo = info
            break

    money = round(status["money"], 2)
    costs = round(status["costs"], 2)
    time_left = int(money / costs)
    time_left_min = time_left // 60
    time_left_sec = time_left % 60
    time_left_str = f"{time_left_min}m {time_left_sec}s"
    # Convert age (seconds) to min:sec format
    age_sec = myinfo['age']
    age_min = age_sec // 60
    age_rem_sec = age_sec % 60
    age_str = f"{age_min}m {age_rem_sec}s"

    # Handle missing or incomplete myinfo gracefully
    if myinfo is not None:
        score = myinfo.get('score', 0.0)
        rank = list(gameinfo.keys()).index(player_id) + 1
        leaderboard = f"{rank}/{len(gameinfo)}"
    else:
        score = 0.0
        leaderboard = f"1/{len(gameinfo)}"

    header = Panel(
        f"[bold cyan]Credits:[/bold cyan] [bright_white]{money} 💲[/bright_white] | "
        f"[bold yellow]Costs:[/bold yellow] [bright_white]{costs} 💰/s[/bright_white] | "
        f"[bold red]Time Left:[/bold red] [bright_white]{time_left_str} ⌛[/bright_white] | "
        f"[bold green]Age:[/bold green] [bright_white]{age_str}[/bright_white] | "
        f"[bold magenta]Score:[/bold magenta] [bright_white]{score:.2f}[/bright_white] | "
        f"[bold blue]Leaderboard:[/bold blue] [bright_white]{leaderboard}[/bright_white] | "
        f"[bold white]Earning Rate:[/bold white] [bright_white]{score / age_sec if age_sec > 0 else 0:.2f} 💵/s[/bright_white]",
        title=f"[bold blue]Current Status : {game.username}[/bold blue]",
        expand=False,
        border_style="yellow"
    )

    station_lines = []
    for sta in status["stations"]:
        station = game.get(f"/station/{sta}")
        trader_info = station['crew'][str(station['trader'])]
        station_lines.append(f"[bold]📡 Station {station['id']}[/bold]")
        station_lines.append(f"  • Trader    : Rank {trader_info['rank']}")
        station_lines.append(f"  • Cargo     : {station['cargo']['usage']:.0f} / {station['cargo']['capacity']:.0f}")
        station_lines.append(f"  • Resources : {station['cargo']['resources']}")
    stations_panel = Panel("\n".join(station_lines), title="Stations", border_style="blue", expand=True)

    ships_table = Table.grid(expand=True)
    ships_table.add_column(no_wrap=True)
    ships_table.add_column()
    ships_table.add_column()
    ships_table.add_column()
    ships_table.add_column()
    ships_table.add_column()
    ships_table.add_column()

    for ship in status["ships"]:
        crew_stats = defaultdict(list)
        for crew in ship['crew'].values():
            crew_stats[crew['member_type']].append(crew['rank'])
        crew_summary = ", ".join([
            f"{member_type}({len(ranks)}|{sum(ranks)/len(ranks):.1f})"
            for member_type, ranks in crew_stats.items()
        ]) or "None"

        mod_stats = defaultdict(list)
        for mod in ship['modules'].values():
            mod_stats[mod['modtype']].append(mod['rank'])
        mod_summary = ", ".join([
            f"{modtype}({len(ranks)}|{sum(ranks)/len(ranks):.1f})"
            for modtype, ranks in mod_stats.items()
        ]) or "None"
        
        raw_state = ship["state"]
        if isinstance(raw_state, dict):
            key = next(iter(raw_state))
            data = raw_state[key]
            if key == "Extracting":
                state_str = f"[white]Extracting:[/white] {len(data)} resources"
            elif key == "InFlight":
                percent = (data['dist_done'] / data['dist_tot']) * 100
                state_str = f"[white]InFlight:[/white] {percent:.1f}%"
            else:
                state_str = f"[white]{key}[/white]"
        else:
            state_str = f"[white]{raw_state}[/white]"

        ship_cargo_info = f"[yellow]Cargo[/yellow] {ship['cargo']['usage']:.0f}/{ship['cargo']['capacity']:.0f}"
        ship_reactor_info = f"[magenta]Reactor[/magenta] {ship['reactor_power']}"
        ship_shield_info = f"[blue]Shield[/blue] {ship['shield_power']}"
        crew_summary = f"[green]Crew[/green] {crew_summary}"
        mod_summary = f"[bright_magenta]Modules[/bright_magenta] {mod_summary}"
        state_str = f"[cyan]State[/cyan] {state_str}"

        if any(mod.get("modtype") == "Miner" for mod in ship["modules"].values()):
            ship_label = f"[bold red]🚀 Ship {ship['id']}[/bold red]"
        else:
            ship_label = f"[bold cyan]🚀 Ship {ship['id']}[/bold cyan]"
        ships_table.add_row(ship_label, ship_cargo_info, ship_reactor_info, ship_shield_info, crew_summary, mod_summary, state_str)

    ships_panel = Panel(ships_table, title=f"{len(status['ships'])} Ships", border_style="magenta")

    content = Group(header, stations_panel, ships_panel)
    return content

def launch_terminal_hud(game):
    console = Console()
    with Live(render_status(game), console=console, refresh_per_second=10) as live:
        while True:
            try:
                live.update(render_status(game))
                time.sleep(0.1)
            except Exception as e:
                if e=="This player lost the game and cannot play anymore":
                    console.print("[❗] Player lost the game, exiting terminal HUD")
                    break
                print(f"[!] Error in terminal HUD: {e}")
                time.sleep(1)
            
def ship_loop(game, sid):
    logger = get_ship_logger(sid)
    ship = game.get(f"/ship/{sid}")
    if not check_has(ship["crew"], "member_type", "Pilot"):
        game.hire_first_pilot(game.sta, ship["id"])
        logger.log("[👨‍✈️] Hired a pilot, assigned it on ship", ship["id"])
    while True:
        try:
            logger.log("")
            ship= game.get(f"/ship/{sid}")
            if ship["cargo"]["usage"]>100:
                game.go_sell(sid, logger)
                game.optimize_upgrades(sid, logger)
            game.go_mine(sid, logger)
            game.go_sell(sid, logger)
            game.optimize_upgrades(sid, logger)
        except Exception as e:
            if e=="This player lost the game and cannot play anymore":
                logger.log("[❗] Player lost the game, exiting ship loop")
                break
            logger.log(f"[!] Error during ship loop: {e}")
            time.sleep(0.1)
if __name__ == "__main__":
    name = sys.argv[1]
    game = Game(name)
    game.init_game()
    #threading.Thread(target=launch_galaxy_map, args=(game,), daemon=True).start()
    threading.Thread(target=launch_terminal_hud, args=(game,), daemon=True).start()
    
    try:
        for sid in game.sids:
            threading.Thread(target=ship_loop, args=(game, sid), daemon=True).start()
        while True:
            time.sleep(1)
    except Exception as e:
        print(f"[!] Error starting game threads: {e}")
        sys.exit(1)




