PORT=8080
#URL=f"http://103.45.247.164:{PORT}"
URL=f"http://127.0.0.1:{PORT}"

RESOURCE_VALUE = {
    "Ozone": 100,
    "Iron": 75,
    "Helium": 50,
    "Stone": 25
}

import os
import sys
import math
import time
import json
import string
import urllib.request
import threading
import plotly.graph_objs as go
from rich.live import Live
from rich.console import Console
import dash
from dash import dcc, html
from dash.dependencies import Input, Output

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
        if new_rank > 45:
            return 0.0
        gain_ratio = (new_rank*100  / current_rank) if current_rank > 0 else 200.0
        if data["cargo"]["capacity"] > 10000:
            return (gain_ratio-100)*2
        return gain_ratio-100

    elif kind == "crew":
        current_rank = data["crew"][id]["rank"]
        new_rank = current_rank + 1
        if "Pilot" == data["crew"][id]["member_type"] and new_rank > 20:
            return 0.0
        if "Operator" == data["crew"][id]["member_type"] and new_rank > 200:
            return 0.0
        gain_ratio = (new_rank*100  / current_rank) if current_rank > 0 else 200.0
        if "Operator" == data["crew"][id]["member_type"] and data["cargo"]["capacity"] > 10000:
            return (gain_ratio+-100)*2
        return gain_ratio-100
    
    elif kind == "trader":
        rank = data["crew"][id]["rank"]
        current_fee = 0.26 / (rank ** 1.15)
        new_fee = 0.26 / ((rank + 1) ** 1.15)
        if new_fee <= 0.01:
            return 0
        gain_ratio = (current_fee * 100 / new_fee) if current_fee > 0 else 200.0
        return gain_ratio-100
    elif kind == "ship":
        current_ships = len(data["ships"]) 
        new_ships = current_ships + 1
        gain_ratio = (new_ships * 100 / current_ships) if current_ships > 0 else 200.0
        return gain_ratio - 100
    elif kind == "shipupgrade":
        # Accès à la stat modifiée selon le type
        if id == "ReactorUpgrade":
            current = data["reactor_power"]
            new = current + 1
            if new > 50: return 0
        elif id == "CargoExpansion":
            current = data["cargo"]["capacity"]
            new = current + 100
            if new > 100000: return 0
        elif id == "HullUpgrade":
            current = data["hull_decay_capacity"]
            new = current 
        elif id == "Shield":
            current = data["shield_power"]
            new = current + 0.01
            if new > 20: return 0
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
            self.get(f"/station/{sta}/crew/upgrade/ship/{sid}/{op}")
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

    def wait_idle(self, sid, ts=2/10):
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
        if len(player["ships"]) < 2 or not (num_solid > 0 and num_gas > 0):
            nearest = sorted(planets, key=lambda p: get_dist(station["position"], p["position"]))[0]
            modtype = "Miner" if nearest["solid"] else "GasSucker"

            if not check_has(ship["modules"], "modtype", modtype):
                logger.log(f"[🛠️] Buying module {modtype} for ship {sid}")
                self.buy_mining_module(modtype, self.sta, sid, logger)

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
                if logisticLoop > 2 and total_earned > 100000:
                    logger.log(f"[🔄] Too much Logistic loop completed, time to make the station great again")
                    unitcargoprice=self.get(f"/station/{self.sta}/upgrades")["cargo-expansion"]
                    new_cargo_price=unitcargoprice*59000
                    if new_cargo_price == 59000:           
                        logger.log(f"[⚙️] Upgrading cargo capacity for {new_cargo_price:.1f} credits")
                        self.get(f"/station/{self.sta}/shop/cargo/buy/{int(59000)}")
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

        upgrades = []

        # Prévisualisation
        mod_preview = self.get(f"/station/{self.sta}/shop/modules/{sid}/upgrade")
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
            price = ship_data["price"]+30000
            gain = estimate_gain("ship", ship_id, player)
            upgrades.append(("ship", ship_id, price, gain))
        
        # Trier par rentabilité
        upgrades.sort(key=lambda u: u[3] / u[2], reverse=True)
        
        # Seuil de ratio
        top_ratio = upgrades[0][3] / upgrades[0][2]
        min_ratio = top_ratio * (1.0 - 0.10)
        shipmoney = money / len(self.sids)
        moneyMinCap = shipmoney*0.1
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

            if kind == "module":
                mod_preview = self.get(f"/station/{self.sta}/shop/modules/{sid}/upgrade")
                price = mod_preview[str(id_)]["price"]
                gain = estimate_gain("module", id_, ship)
            elif kind == "crew":
                crew_preview = self.get(f"/station/{self.sta}/crew/upgrade/ship/{sid}")
                price = crew_preview[str(id_)]["price"]
                gain = estimate_gain("crew", id_, ship)
            elif kind == "shipupgrade":
                ship = self.get(f"/ship/{sid}")
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
    app = dash.Dash(__name__)
    app.layout = html.Div([
        html.H3("Carte de la galaxie 🚀", style={"color": "#fff"}),
        dcc.Interval(id='interval', interval=1000, n_intervals=0),
        dcc.Graph(id='galaxy-map')
    ])

    @app.callback(Output('galaxy-map', 'figure'), Input('interval', 'n_intervals'))
    def update_map(n):
        scan = game.get(f"/station/{game.sta}/scan")
        gamestats= game.get(f"/gamestats")
        planets = scan["planets"]
        stations = scan["stations"]
        # stations = []
        # for player, data in gamestats.items():
        #     for sta_id, pos in data["stations"].items():
        #         stations.append({'id': int(sta_id), 'position': pos})
        ships = game.get(f"/player/{game.pid}")["ships"]

        fig = go.Figure()

        # Cache planets and stations positions to avoid re-adding them every interval
        if not hasattr(update_map, "static_traces"):
            static_traces = []
            for p in planets:
                x, y, z = p["position"]
                color = "brown" if p.get("solid", False) else "orange"
                emoji = "🪐" if p.get("solid", False) else "☁️"
                static_traces.append(go.Scatter3d(
                    x=[x], y=[y], z=[z], mode="markers+text",
                    marker=dict(size=5, color=color), text=[emoji], name="Planets"
                ))
            for s in stations:
                x, y, z = s["position"]
                static_traces.append(go.Scatter3d(
                    x=[x], y=[y], z=[z], mode="markers+text",
                    marker=dict(size=6, color="blue"), text=["📡"], name="Stations"
                ))
            update_map.static_traces = static_traces

        # Add static traces (planets & stations)
        for trace in update_map.static_traces:
            fig.add_trace(trace)

        # Ships are dynamic, update every interval
        for s in ships:
            x, y, z = s["position"]
            fig.add_trace(go.Scatter3d(
            x=[x], y=[y], z=[z], mode="markers+text",
            marker=dict(size=7, color="red"), text=[f"🚀{s['id']}"], name="Ships"
            ))

        fig.update_layout(template="plotly_dark", scene=dict(bgcolor="black"), margin=dict(l=0, r=0, t=40, b=0))
        return fig

    app.run(debug=False, port=8050)

def render_status(game):    
    status = game.get("/player/" + str(game.pid))
    lines = []
    lines.append("Current status: {} credits, costs: {}, time left before lost: {} secs".format(
        round(status["money"], 2), round(status["costs"], 2), int(status["money"] / status["costs"]),
    ))
    lines.append("=== STATIONS ===")
    for sta in status["stations"]:
        station = game.get(f"/station/{sta}")
        lines.append(f"-> Station {station['id']}")
        lines.append(f"   - Pos       : {station['position']}")
        lines.append(f"   - Trader    : {station['crew'][str(station['trader'])]['member_type']} (Rank {station['crew'][str(station['trader'])]['rank']})")
        lines.append(f"   - Cargo     : {round(station['cargo']['usage'], 2)} / {station['cargo']['capacity']}")
        lines.append(f"   - Resources : {station['cargo']['resources']}")
    lines.append(f"=== {len(status['ships'])} SHIPS ===")
    for ship in status["ships"][:1]:
        sid = ship["id"]
        lines.append(f"-> Ship {sid}")
        lines.append(f"   - Pos       : {ship['position']}")
        lines.append(f"   - Cargo     : {round(ship['cargo']['usage'], 2)} / {ship['cargo']['capacity']}")
        lines.append(f"   - Fuel      : {round(ship['fuel_tank'], 2)} / {ship['fuel_tank_capacity']}")
        lines.append(f"   - Hull      : {round(ship['hull_decay'], 2)} / {ship['hull_decay_capacity']}")
        lines.append(f"   - State     : {ship['state']}")
        lines.append(f"   - Reactor   : Rank {ship['reactor_power']}")
        lines.append(f"   - Shield    : Rank {ship['shield_power']}")
        lines.append("   - Crew:")
        for crewid, crew in ship['crew'].items():
            lines.append(f"      > {crewid}: {crew['member_type']} (Rank {crew['rank']})")
        lines.append("   - Modules:")
        for modid, mod in ship['modules'].items():
            lines.append(f"      > {modid}: {mod['modtype']} (Rank {mod['rank']})")
        lines.append("")
    for ship in status["ships"][1:]:
        sid = ship["id"]
        lines.append(f"-> Ship {sid} | Pos: {ship['position']} | Cargo: {round(ship['cargo']['usage'], 2)}/{ship['cargo']['capacity']}| Reactor: {ship['reactor_power']} | Shield: {ship['shield_power']}")
        lines.append(f"   - State: {ship['state']}")
        
    return "\n".join(lines)

def launch_terminal_hud(game):
    console = Console()
    with Live(render_status(game), console=console, refresh_per_second=100) as live:
        while True:
            try:
                live.update(render_status(game))
                time.sleep(0.1)
            except Exception as e:
                print(f"[!] Error in terminal HUD: {e}")
                time.sleep(1)
            
def ship_loop(game, sid):
    logger = get_ship_logger(sid)
    # Ensure our ship has a crew, hire one if we don't
    ship = game.get(f"/ship/{sid}")
    if not check_has(ship["crew"], "member_type", "Pilot"):
        game.hire_first_pilot(game.sta, ship["id"])
        logger.log("[👨‍✈️] Hired a pilot, assigned it on ship", ship["id"])
    while True:
        try:
            logger.log("")
            game.go_mine(sid, logger)
            game.go_sell(sid, logger)
            game.optimize_upgrades(sid, logger)
        except Exception as e:
            logger.log(f"[!] Error during ship loop: {e}")
            time.sleep(1)
            
if __name__ == "__main__":
    name = sys.argv[1]
    game = Game(name)
    game.init_game()
    # Lancer la carte dans un thread
    # threading.Thread(target=launch_galaxy_map, args=(game,), daemon=True).start()
    # Lancer l'HUD dans un thread
    threading.Thread(target=launch_terminal_hud, args=(game,), daemon=True).start()
    
    try:
        # Lancer le jeu pour chaque vaisseau
        for sid in game.sids:
            threading.Thread(target=ship_loop, args=(game, sid), daemon=True).start()
        while True:
            time.sleep(1)
    except Exception as e:
        print(f"[!] Error starting game threads: {e}")
        sys.exit(1)




