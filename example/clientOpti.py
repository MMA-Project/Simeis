PORT=8080
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


def estimate_gain(kind, id, data):
    if kind == "module":
        current_rank = data["modules"][id]["rank"]
        new_rank = current_rank + 1
        gain_ratio = (new_rank*100  / current_rank) if current_rank > 0 else 200.0
        return gain_ratio-100

    elif kind == "crew":
        current_rank = data["crew"][id]["rank"]
        new_rank = current_rank + 1
        gain_ratio = (new_rank*100  / current_rank) if current_rank > 0 else 200.0
        return gain_ratio-100
    
    elif kind == "trader":
        rank = data["crew"][id]["rank"]
        current_fee = 0.26 / (rank ** 1.15)
        new_fee = 0.26 / ((rank + 1) ** 1.15)
        if new_fee <= 0.0001:
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
            if new > 20: return 0
        elif id == "CargoExpansion":
            current = data["cargo"]["capacity"]
            new = current + 100
        elif id == "HullUpgrade":
            current = data["hull_decay_capacity"]
            new = current + 1
        elif id == "Shield":
            current = data["shield_power"]
            new = current + 0.01
            if new > 20: return 0
        else:
            return 0.0
        #print(f"[🔧] Estimating gain for {data}: current={current}, new={new}")
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
        self.sid = None    # ID of our ship
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

    # def disp_status(self):
    #     status = game.get("/player/" + str(game.pid))
    #     print("[*] Current status: {} credits, costs: {}, time left before lost: {} secs".format(
    #         round(status["money"], 2), round(status["costs"], 2), int(status["money"] / status["costs"]),
    #     ))  
    #     print("[*] === STATIONS ===")
    #     for sta in status["stations"]:
    #         station= self.get(f"/station/{sta}")
    #         print(f"-> Station {station['id']}")
    #         print(f"   - Pos       : {station['position']}")
    #         print(f"   - Trader    : {station['crew'][str(station['trader'])]['member_type']} (Rank {station['crew'][str(station['trader'])]['rank']})")
    #         print(f"   - Cargo     : {round(station['cargo']['usage'], 2)} / {station['cargo']['capacity']}")
    #         print(f"   - Resources : {station['cargo']['resources']}")
    #     print("[*] === SHIPS ===")
    #     for ship in status["ships"]:
    #         sid = ship["id"]
    #         print(f"-> Ship {sid}")
    #         print(f"   - Pos       : {ship['position']}")
    #         print(f"   - Cargo     : {round(ship['cargo']['usage'], 2)} / {ship['cargo']['capacity']}")
    #         print(f"   - Fuel      : {round(ship['fuel_tank'], 2)} / {ship['fuel_tank_capacity']}")
    #         print(f"   - Hull      : {round(ship['hull_decay'], 2)} / {ship['hull_decay_capacity']}")
    #         print(f"   - Reactor   : Rank {ship['reactor_power']}")
    #         print(f"   - Shield    : Rank {ship['shield_power']}")

    #         print("   - Crew:")
    #         for crewid, crew in ship['crew'].items():
    #             print(f"      > {crewid}: {crew['member_type']} (Rank {crew['rank']})")

    #         print("   - Modules:")
    #         for modid, mod in ship['modules'].items():
    #             print(f"      > {modid}: {mod['modtype']} (Rank {mod['rank']})")

    #         print("")

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

    def buy_first_mining_module(self, modtype, sta, sid):
        # Buy the mining module
        all = self.get(f"/station/{sta}/shop/modules")
        mod_id = self.get(f"/station/{sta}/shop/modules/{sid}/buy/{modtype}")["id"]
        print("[💰] Bought a {} module for our ship {} (ID: {})".format(modtype, sid, mod_id))

        # Check if we have the crew assigned on this module
        # If not, hire an operator, and assign it to the mining module of our ship
        ship = self.get(f"/ship/{sid}")
        if not check_has(ship["crew"], "member_type", "Operator"):
            op = self.get(f"/station/{sta}/crew/hire/operator")["id"]
            self.get(f"/station/{sta}/crew/assign/{op}/{sid}/{mod_id}")
            self.get(f"/station/{sta}/crew/upgrade/ship/{sid}/{op}")
            print("[👨‍🔧] Hired an operator, assigned it on the mining module of our ship")
            

    def hire_first_pilot(self, sta, ship):
        # Hire a pilot, and assign it to our ship
        pilot = self.get(f"/station/{sta}/crew/hire/pilot")["id"]
        self.get(f"/station/{sta}/crew/assign/{pilot}/{ship}/pilot")

    def hire_first_trader(self, sta):
        # Hire a trader, assign it on our station
        trader = self.get(f"/station/{sta}/crew/hire/trader")["id"]
        self.get(f"/station/{sta}/crew/assign/{trader}/trading")

    def travel(self, sid, pos):
        costs = self.get(f"/ship/{sid}/navigate/{pos[0]}/{pos[1]}/{pos[2]}")
        print("[🚀] Traveling to {}, will take {}".format(pos, costs["duration"]))
        self.wait_idle(sid, ts=costs["duration"])

    def wait_idle(self, sid, ts=2/10):
        ship = self.get(f"/ship/{sid}")
        while ship["state"] != "Idle":
            time.sleep(ts)
            ship = self.get(f"/ship/{sid}")

    # Repair the ship:     Buy the plates, then ask for reparation
    def ship_repair(self, sid):
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
            print(f"[💰] Bought {need} of hull plates for", bought["removed_money"])
            station = self.get(f"/station/{self.sta}")["cargo"]

        if station["resources"]["HullPlate"] > 0:
            # Use the plates in stock to repair the ship
            repair = self.get(f"/station/{self.sta}/repair/{self.sid}")
            print("[🔧] Repaired {} hull plates on the ship".format(repair["added-hull"]))

    # Refuel the ship:    Buy the fuel, then ask for a refill
    def ship_refuel(self, sid):
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
            print(f"[💰] Bought {need} of fuel for", bought["removed_money"])
            station = self.get(f"/station/{self.sta}")["cargo"]

        if station["resources"]["Fuel"] > 0:
            # Use the fuel in stock to refill the ship
            refuel = self.get(f"/station/{self.sta}/refuel/{self.sid}")
            print("[⛽] Refilled {} fuel on the ship".format(
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
        ship = status["ships"][0]
        self.sid = ship["id"]

        # Ensure our ship has a crew, hire one if we don't
        if not check_has(ship["crew"], "member_type", "Pilot"):
            self.hire_first_pilot(self.sta, self.sid)
            print("[👨‍✈️] Hired a pilot, assigned it on ship", self.sid)

        print("[*] Game initialisation finished successfully")

    # - Find the nearest planet we can mine
    # - Go there
    # - Fill our cargo with resources
    # - Once the cargo is full, we stop mining, and this function returns
    def go_mine(self):
        print("[⛏] Starting the Mining operation")

        # Scan the galaxy sector, detect which planet is the nearest
        station = self.get(f"/station/{self.sta}")
        planets = self.get(f"/station/{self.sta}/scan")["planets"]
        print("planets: ", planets)
        nearest = sorted(planets,
            key=lambda pla: get_dist(station["position"], pla["position"])
        )[0]

        # If the planet is solid, we need a Miner to mine it
        # If it's gaseous, we need a GasSucker to mine it
        if nearest["solid"]:
            modtype = "Miner"
        else:
            modtype = "GasSucker"

        # Ensure the ship has a corresponding module, buy one if we don't
        ship = self.get(f"/ship/{self.sid}")
        if not check_has(ship["modules"], "modtype", modtype):
            self.buy_first_mining_module(modtype, self.sta, self.sid)
        print("[🪐] Targeting planet at", nearest["position"])

        self.wait_idle(self.sid) # If we are currently occupied, wait

        # If we are not current at the position of the target planet, travel there
        if ship["position"] != nearest["position"]:
            self.travel(ship["id"], nearest["position"])

        # Now that we are there, let's start mining
        info = self.get(f"/ship/{self.sid}/extraction/start")
        print("[*] Starting extraction:")
        for res, amnt in info.items():
            print(f"\t- Extraction of {res}: {amnt}/sec")

        # Wait until the cargo is full
        self.wait_idle(self.sid) # The ship will have the state "Idle" once the cargo is full
        print("[*] The cargo is full, stopping mining process")

    # - Go back to the station
    # - Unload all the cargo
    # - Sell it on the market
    # - Refuel & repair the ship
    def go_sell(self):
        self.wait_idle(self.sid) # If we are currently occupied, wait
        ship = self.get(f"/ship/{self.sid}")
        station = self.get(f"/station/{self.sta}")

        # If we aren't at the station, got there
        if ship["position"] != station["position"]:
            self.travel(ship["id"], station["position"])

        # Unload the cargo and sell it directly on the market
        for res, amnt in ship["cargo"]["resources"].items():
            total_unloaded = 0.0
            total_earned = 0.0
            amt_left = amnt

            while amt_left > 0.0:
                unloaded = self.get(f"/ship/{self.sid}/unload/{res}/{amt_left}")
                unloaded_amt = unloaded["unloaded"]
                if unloaded_amt == 0.0:
                    break

                sold = self.get(f"/market/{self.sta}/sell/{res}/{unloaded_amt}")
                total_unloaded += unloaded_amt
                total_earned += sold["added_money"]
                amt_left -= unloaded_amt

            if total_unloaded > 0:
                print(f"[💲] Unloaded and sold {total_unloaded:.1f} of {res}, total gain: {total_earned:.1f} credits")

        self.ship_repair(self.sid)
        self.ship_refuel(self.sid)
                
    def optimize_upgrades(self):
        player = self.get(f"/player/{self.pid}")
        money = player["money"]
        ship = self.get(f"/ship/{self.sid}")
        station= self.get(f"/station/{self.sta}")

        upgrades = []

        # Prévisualisation
        mod_preview = self.get(f"/station/{self.sta}/shop/modules/{self.sid}/upgrade")
        crew_preview = self.get(f"/station/{self.sta}/crew/upgrade/ship/{self.sid}")
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
            price = ship_data["price"]
            gain = estimate_gain("ship", ship_id, player)
            #upgrades.append(("ship", ship_id, price, gain))
        
        # Trier par rentabilité
        upgrades.sort(key=lambda u: u[3] / u[2], reverse=True)
        
        # Seuil de ratio
        top_ratio = upgrades[0][3] / upgrades[0][2]
        min_ratio = top_ratio * (1.0 - 0.10)
        moneyMinCap = money*0.1

        while upgrades:
            kind, id_, price, gain = upgrades[0]
            ratio = gain / price

            if ratio < min_ratio:
                print(f"[❌] Skipping {kind} {id_}: ratio too low ({ratio:.4f}) price={price:.1f}, gain={gain:.1f})")
                upgrades.pop(0)  # Enlever de la liste
                continue

            if money <= price + moneyMinCap:
                print(f"[💸] Not enough money for {kind} {id_}: need {price:.1f}, have {money:.1f}, gain={gain:.1f}%")
                upgrades.pop(0)
                continue

            try:
                if kind == "module":
                    res = self.get(f"/station/{self.sta}/shop/modules/{self.sid}/upgrade/{id_}")
                    print(f"[⏫] Module {id_} upgraded for {price:.1f} & gain {gain:.1f}%")
                elif kind == "crew":
                    res = self.get(f"/station/{self.sta}/crew/upgrade/ship/{self.sid}/{id_}")
                    print(f"[⏫] Crew {id_} upgraded for {price:.1f} & gain {gain:.1f}%")
                elif kind == "shipupgrade":
                    res = self.get(f"/station/{self.sta}/shipyard/upgrade/{self.sid}/{id_}")
                    print(f"[⏫] Ship upgrade {id_} for {price:.1f} & gain {gain:.1f}%")
                elif kind == "trader":
                    res = self.get(f"/station/{self.sta}/crew/upgrade/trader")
                    print(f"[⏫] Trader upgraded for {price:.1f} & gain {gain:.1f}%")
                money -= price
            except SimeisError as e:
                print(f"[!] Upgrade {kind} {id_} failed:", e)
                upgrades.pop(0)
                continue

            if kind == "module":
                mod_preview = self.get(f"/station/{self.sta}/shop/modules/{self.sid}/upgrade")
                price = mod_preview[str(id_)]["price"]
                gain = estimate_gain("module", id_, ship)
            elif kind == "crew":
                crew_preview = self.get(f"/station/{self.sta}/crew/upgrade/ship/{self.sid}")
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
        print(f"[💰] Money left after upgrades: {money:.2f} credits")
                
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
        planets = scan["planets"]
        stations = scan["stations"]
        ships = game.get(f"/player/{game.pid}")["ships"]

        fig = go.Figure()

        # Cache planets and stations positions to avoid re-adding them every interval
        if not hasattr(update_map, "static_traces"):
            static_traces = []
            for p in planets:
                x, y, z = p["position"]
                static_traces.append(go.Scatter3d(
                    x=[x], y=[y], z=[z], mode="markers+text",
                    marker=dict(size=5, color="blue"), text=["🪐"], name="Planets"
                ))
            for s in stations:
                x, y, z = s["position"]
                static_traces.append(go.Scatter3d(
                    x=[x], y=[y], z=[z], mode="markers+text",
                    marker=dict(size=6, color="green"), text=["📡"], name="Stations"
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
        # lines.append(f"   - Cargo     : {round(station['cargo']['usage'], 2)} / {station['cargo']['capacity']}")
        # lines.append(f"   - Resources : {station['cargo']['resources']}")
    lines.append("=== SHIPS ===")
    for ship in status["ships"]:
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
    return "\n".join(lines)

def launch_terminal_hud(game):
    console = Console()
    with Live(render_status(game), console=console, refresh_per_second=100) as live:
        while True:
            live.update(render_status(game))
            time.sleep(0.5)

if __name__ == "__main__":
    name = sys.argv[1]
    game = Game(name)
    game.init_game()
    # Lancer la carte dans un thread
    # threading.Thread(target=launch_galaxy_map, args=(game,), daemon=True).start()
    # Lancer l'HUD dans un thread
    threading.Thread(target=launch_terminal_hud, args=(game,), daemon=True).start()

    while True:
        print("")
        game.go_mine()
        game.go_sell()
        game.optimize_upgrades()



