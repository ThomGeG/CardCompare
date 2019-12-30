# define usage
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("account_name", help="your deckbox.org account name", type=str)
parser.add_argument("-v", "--verbose", help="increase output verbosity", action="store_true")
args = parser.parse_args()

import time
import urllib
import requests
from GoodGamesParser import GoodGamesParser

# define some API endpoints
SCRYFALL_API    = "https://api.scryfall.com/cards/"
CURRENCY_API    = "https://api.exchangeratesapi.io/latest"
GOODGAMES_API   = "https://tcg.goodgames.com.au/catalogsearch/advanced/result/"
DECKBOX_API     = "https://deckbox-api.herokuapp.com/api/users/%s/wishlist" % args.account_name

# define the conversion rate of USD -> AUD
CONVERSION_RATE = requests.get(CURRENCY_API, params={"base" : "USD"}).json()["rates"]["AUD"]
if args.verbose:
    print("\nCurrent conversion rate (USD -> AUD): %s\n" % CONVERSION_RATE)

# retrieve cards from wishlist on deckbox.org
WISHLIST_CARDS = []
for i in range(requests.get(DECKBOX_API).json()["total_pages"]):
    wishlist_page = requests.get(DECKBOX_API, params={"page": i+1}).json()
    for card in wishlist_page["items"]:
        WISHLIST_CARDS.append({"name": card["name"]})

# fetch pricing data from scryfall and good games
for card in WISHLIST_CARDS:

    print("Fetching: %s" % card["name"])

    # fetch scryfall data
    oracle_id = requests.get(SCRYFALL_API + "named", params={"exact" : card["name"]}).json()["oracle_id"]
    scryfall_cards = requests.get(SCRYFALL_API + "search", params={"q" : "oracleid:" + oracle_id, "order" : "usd", "unique" : "prints"}).json()["data"]

    # do some post-processing
    multiverse_ids = [id for sublist in [card["multiverse_ids"] for card in scryfall_cards] for id in sublist]
    scryfall_prices = [round(float(scryfall_card["prices"]["usd"]) * CONVERSION_RATE, 2) for scryfall_card in scryfall_cards if scryfall_card["prices"]["usd"] is not None]

    if args.verbose:
        print("\tFound:\t\t%s" % oracle_id)
        print("\tPrintings:\t%s" % multiverse_ids)
        print("\tPrices:\t\t%s" % scryfall_prices)

    # fetch good games data
    parser = GoodGamesParser()
    for multiverse_id in multiverse_ids:
        params = urllib.parse.urlencode({"mtg_multiverseid" : multiverse_id})
        parser.feed(urllib.request.urlopen(GOODGAMES_API + "?%s" % params).read().decode("utf-8"))

    # add the pricing data
    card["prices"] = {
        "scryfall" : {
            "aud" : scryfall_prices[-1],
            "instock" : True # scryfall doesn't track stock, so always assume it's in stock.
        },
        "goodgames" : {
            "aud" : parser.price,
            "instock" : parser.is_instock
        }
    }

    # scryfall is a public api and will blacklist IPs if they're requesting too frequently.
    time.sleep(1/10)

# define a monsterous commpare function for sorting
def compare(card):
    return float(card["prices"]["goodgames"]["aud"]) - float(card["prices"]["scryfall"]["aud"])

WISHLIST_CARDS.sort(key=compare)
for card in WISHLIST_CARDS:
    # printing card information
    print(card["name"] + ":")
    for vendor in card["prices"]:
        print(vendor, end= ': ')
        if card["prices"][vendor] is None:
            print("No price avail.")
        else:
            print(card["prices"][vendor], end=" AUD ")
            print()
    print()
