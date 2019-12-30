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
SCRYFALL_API = "https://api.scryfall.com/cards/named"
CURRENCY_API = "https://api.exchangeratesapi.io/latest"
GOODGAMES_API = "https://tcg.goodgames.com.au/catalogsearch/advanced/result/"
DECKBOX_API = "https://deckbox-api.herokuapp.com/api/users/%s/wishlist" % args.account_name

# define the conversion rate of USD -> AUD
CONVERSION_RATE = requests.get(CURRENCY_API, params={"base" : "USD"}).json()["rates"]["AUD"]
if args.verbose:
    print("\nCurrent conversion rate (USD -> AUD): %s\n" % CONVERSION_RATE)

# retrieve cards from wishlist on deckbox.org
WISHLIST_CARDS = []
for i in range(requests.get(DECKBOX_API).json()["total_pages"]):
    wishlist_page = requests.get(DECKBOX_API, params={"page": i+1}).json()
    for card in wishlist_page["items"]:
        WISHLIST_CARDS.append(card)

# fetch pricing data from scryfall and good games
for card in WISHLIST_CARDS:
    # fetch scryfall data
    scryfall_card = requests.get(SCRYFALL_API, params={"exact" : card["name"]}).json()

    # convert usd into aud
    if scryfall_card["prices"]["usd"] is not None:
        scryfall_card["prices"]["aud"] = str(round(float(scryfall_card["prices"]["usd"]) * CONVERSION_RATE, 2))
    else:
        scryfall_card["prices"]["aud"] = None

    # add pricing data to WISHLIST_CARDS
    card["prices"] = {"tcgplayer" : scryfall_card["prices"]}
    card["multiverse_ids"] = scryfall_card["multiverse_ids"]

    # fetch good games data
    parser = GoodGamesParser()
    params = urllib.parse.urlencode({"mtg_multiverseid" : card["multiverse_ids"][0]})
    parser.feed(urllib.request.urlopen(GOODGAMES_API + "?%s" % params).read().decode("utf-8"))
    card["prices"]["goodgames"] = {
        "aud": parser.price,
        "usd": round(float(parser.price) / CONVERSION_RATE, 2) if parser.price is not None else None,
        "instock": parser.is_instock
    }

    if args.verbose:
        print("Fetched: " + card["name"])
    # scryfall is a public api and will blacklist IPs if they're requesting too frequently.
    time.sleep(1/10)

# define a monsterous commpare function for sorting
def compare(card):
    if card["prices"]["goodgames"]["aud"] is None:
        return float(card["prices"]["goodgames"]["usd"]) if card["prices"]["goodgames"]["usd"] is not None else 0
    elif card["prices"]["tcgplayer"]["usd"] is None:
        return float(card["prices"]["goodgames"]["aud"]) if card["prices"]["goodgames"]["aud"] is not None else 0
    else:
        return float(card["prices"]["goodgames"]["aud"]) - float(card["prices"]["tcgplayer"]["aud"])

WISHLIST_CARDS.sort(key=compare)
for card in WISHLIST_CARDS:
    # printing card information
    print(card["name"] + ":")
    for vendor in card["prices"]:
        print(vendor, end= ': ')
        if card["prices"][vendor]["aud"] is None or card["prices"][vendor]["usd"] is None:
            print("No price avail.")
        else:
            print(card["prices"][vendor]["usd"], end=" USD ")
            print(card["prices"][vendor]["aud"], end=" AUD ")
            print()
    print()
