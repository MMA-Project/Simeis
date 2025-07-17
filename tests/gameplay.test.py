PORT=9345
URL=f"http://127.0.0.1:{PORT}"

RESOURCE_VALUE = {
    "Ozone": 100,
    "Iron": 75,
    "Helium": 50,
    "Stone": 25
}

import sys
import math
import json
import string
import urllib.request
import datetime

class SimeisError(Exception):
    pass

# Théorème de Pythagore pour récupérer la distance entre 2 points dans l'espace 3D
def get_dist(a, b):
    return math.sqrt(((a[0] - b[0]) ** 2) + ((a[1] - b[1]) ** 2) + ((a[2] - b[2]) ** 2))

# Check if types are present in the list
def check_has(alld, key, *req):
    alltypes = [c[key] for c in alld.values()]
    return all([k in alltypes for k in req])


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
    
    def setup_player(self, username, force_register=False):
        # Sanitize the username, remove any symbols
        username = "".join([c for c in username if c in string.ascii_letters + string.digits]).lower()

        # If we don't have any existing account
        player = self.get(f"/player/new/{username}")
        self.player = player

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
            

# OHMONDIEU CETTE IMMONDICE
# Utilisez des fonctions, factorisez le code, espacez, commentez
# Je dois vraiment lire ça ?
# J'ai envie de crever.
if __name__ == "__main__":
    name = "test_gameplay"
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    name = f"{name}_{timestamp}"
    game = Game(name)
    print (f"[*] Starting test {name}_buyship_buyminer")
    try:
        # Get the player and station information
        player = game.get(f"/player/{game.pid}")
        game.sta = list(player["stations"].keys())[0]
        station = game.get(f"/station/{game.sta}")
        money = player["money"]
        assert money > 0, "Player should have some money to start with"
        # Buy a ship from the shipyard
        available = game.get(f"/station/{game.sta}/shipyard/list")["ships"]
        cheapest = sorted(available, key = lambda ship: ship["price"])[0]
        game.get(f"/station/{game.sta}/shipyard/buy/" + str(cheapest["id"]))
        sid=cheapest["id"]
        player = game.get(f"/player/{game.pid}")
        assert(len(player["ships"]) == 1)
        assert player["money"] < money, "Player should have spent some money on the ship purchase"  
        money = player["money"]
        # Buy a mining module for the ship for the nearest planet
        planets = game.get(f"/station/{game.sta}/scan")["planets"]
        nearest = sorted(planets, key=lambda p: get_dist(station["position"], p["position"]))[0]
        modtype = "Miner" if nearest["solid"] else "GasSucker"
        game.get(f"/station/{game.sta}/shop/modules/{sid}/buy/{modtype}")
        player = game.get(f"/player/{game.pid}")
        ship = game.get(f"/ship/{sid}")
        assert len(ship["modules"]) == 1, "Ship should have one module"
        assert player["money"] < money, "Player should have spent some money on the module purchase"
    except Exception as e:
        print(f"[❌] Test {name}_buyship_buyminer failed: {e}")
        sys.exit(1)
    print(f"[✅] Test {name}_buyship_buyminer passed")
    print (f"[*] Starting test {name}_assignOperator_upgradeOperator")
    try:
        # Get the player and station information
        player = game.get(f"/player/{game.pid}")
        game.sta = list(player["stations"].keys())[0]
        station = game.get(f"/station/{game.sta}")
        sid = list(player["ships"])[0]["id"]
        ship = game.get(f"/ship/{sid}")
        assert len(ship["modules"]) == 1, "Ship should have one module"
        assert len(ship["crew"]) == 0, "Ship should have no crew"
        # Hire an operator and assign them to the ship
        op = game.get(f"/station/{game.sta}/crew/hire/operator")["id"]
        mod_id = list(ship["modules"].keys())[0]
        game.get(f"/station/{game.sta}/crew/assign/{op}/{sid}/{mod_id}")
        ship = game.get(f"/ship/{sid}")
        assert len(ship["crew"]) == 1, "Ship should have one operator"
        # Upgrade the operator to level 2
        game.get(f"/station/{game.sta}/crew/upgrade/ship/{sid}/{op}")
        ship = game.get(f"/ship/{sid}")
        assert list(ship["crew"].values())[0]["rank"] == 2, "Operator should be upgraded to level 2"
    except Exception as e:
        print(f"[❌] Test {name}_assignOperator_upgradeOperator failed: {e}")
        sys.exit(1)
    print(f"[✅] Test {name}_assignOperator_upgradeOperator passed")
    print (f"[*] Starting test {name}_travel_mine_travel_survive")
    try:
        # Get the player and station information
        player = game.get(f"/player/{game.pid}")
        game.sta = list(player["stations"].keys())[0]
        station = game.get(f"/station/{game.sta}")
        sid = list(player["ships"])[0]["id"]
        ship = game.get(f"/ship/{sid}")
        # Ensure the ship has an operator and a trader
        trader = game.get(f"/station/{game.sta}/crew/hire/trader")["id"]
        game.get(f"/station/{game.sta}/crew/assign/{trader}/trading")
        pilot = game.get(f"/station/{game.sta}/crew/hire/pilot")["id"]
        game.get(f"/station/{game.sta}/crew/assign/{pilot}/{sid}/pilot")
        ship = game.get(f"/ship/{sid}")
        station = game.get(f"/station/{game.sta}")
        assert len(ship["crew"]) == 2, "Ship should have two crew members"
        assert len(station["crew"]) == 1, "Station should have a trader"
        # Travel to the nearest planet
        planets = game.get(f"/station/{game.sta}/scan")["planets"]
        nearest = sorted(planets, key=lambda p: get_dist(station["position"], p["position"]))[0]
        planetpos = nearest["position"]
        game.get(f"/ship/{sid}/navigate/{planetpos[0]}/{planetpos[1]}/{planetpos[2]}")
        game.get("/tick/600")
        ship = game.get(f"/ship/{sid}")
        assert ship["position"] != station["position"], "Ship should have left station"
        assert ship["position"] == planetpos, "Ship should have arrived at the nearest planet"
        # Start mining the nearest planet and stop mining when full
        print(ship["modules"])
        print(nearest)
        extractinfo=game.get(f"/ship/{sid}/extraction/start")
        print(f"[*] Extracting resources with ship {sid}: {extractinfo}")
        game.get("/tick/300")
        ship = game.get(f"/ship/{sid}")
        assert ship["state"] == "Idle", "Ship should have finished mining"
        print(f"[*] Ship {sid} has mined {ship['cargo']['usage']} units of resources")
        assert ship["cargo"]["usage"] > 0, "Ship should have mined some resources"
        assert ship["cargo"]["usage"]== ship["cargo"]["capacity"], "Ship should have full cargo"
        # Travel back to the station
        game.get(f"/ship/{sid}/navigate/{station['position'][0]}/{station['position'][1]}/{station['position'][2]}")
        game.get("/tick/600")
        ship = game.get(f"/ship/{sid}")
        assert ship["position"] == station["position"], "Ship should have returned to station"
        player = game.get(f"/player/{game.pid}")
        assert player["money"] > 0, "Player should survive with some money left"
    except Exception as e:
        print(f"[❌] Test {name}_travel_mine_travel_survive failed: {e}")
        sys.exit(1)
    print(f"[✅] Test {name}_travel_mine_travel_survive passed")
    print (f"[*] Starting test {name}_sell_refill")
    try:
        # Get the player and station information
        player = game.get(f"/player/{game.pid}")
        berforeMoney=player["money"]
        game.sta = list(player["stations"].keys())[0]
        station = game.get(f"/station/{game.sta}")
        sid = list(player["ships"])[0]["id"]
        ship = game.get(f"/ship/{sid}")
        # Unload the cargo at the station
        for res, amnt in ship["cargo"]["resources"].items():
            unloaded = game.get(f"/ship/{sid}/unload/{res}/{amnt}")
            ship = game.get(f"/ship/{sid}")
            assert ship["cargo"]["usage"] == 0, "Ship should have unloaded all resources"
        # Sell the resources at the station
            sold = game.get(f"/market/{game.sta}/sell/{res}/{amnt}")
        player = game.get(f"/player/{game.pid}")
        assert player["money"] > berforeMoney, "Player should have made some money from selling resources"
        # Refill the ship's fuel
        req = int(ship["fuel_tank_capacity"] - ship["fuel_tank"])
        game.get(f"/market/{game.sta}/buy/Fuel/{req}")
        game.get(f"/station/{game.sta}/refuel/{sid}")
        # Repair the ship's hull
        req = int(ship["hull_decay"])
        game.get(f"/market/{game.sta}/buy/hullplate/{req}")
        game.get(f"/station/{game.sta}/repair/{sid}")
        player = game.get(f"/player/{game.pid}")
        assert player["money"] > 1000, "Player should have enough money left to keep playing"
        
    except Exception as e:
        print(f"[❌] Test {name}_sell_refill failed: {e}")
        sys.exit(1)
    print(f"[✅] Test {name}_sell_refill passed")
        
        
