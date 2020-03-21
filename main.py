# define usage
import sys
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("input",
    help="input file path for file; deckbox.org account name for wishlist",
    type=str)
parser.add_argument("-v", "--verbose",
    action="store_true",
    help="increase output verbosity")
parser.add_argument("--source",
    default='wishlist',
    choices=['wishlist', 'file'],
    help="the type of source for your cards",
    nargs='?',
    type=str)
parser.add_argument("--rate",
    default=None,
    help="the exchange rate of USD -> AUD",
    nargs='?',
    type=float)
parser.add_argument('outstream',
    default=sys.stdout,
    help="file location to store results in",
    nargs='?',
    type=argparse.FileType('w'))
args = parser.parse_args()

import re
import time
import urllib
import requests
from bs4 import BeautifulSoup
from bs4 import NavigableString

# define some API endpoints
SCRYFALL_API    = "https://api.scryfall.com/cards/"
CURRENCY_API    = "https://api.exchangeratesapi.io/latest"
GOODGAMES_API   = "https://tcg.goodgames.com.au/catalogsearch/advanced/result/"
DECKBOX_API     = "https://deckbox-api.herokuapp.com/api/users/%s/wishlist" % args.input

# define the conversion rate of USD -> AUD (use from commandline if provided)
CONVERSION_RATE = args.rate or requests.get(CURRENCY_API, params={"base" : "USD"}).json()["rates"]["AUD"]

if args.verbose:
    print("Input:\t\t" + args.input)
    print("Input Type:\t" + args.source)
    print("Output:\t\t"+ str(args.outstream))
    print("\nCurrent conversion rate (USD -> AUD): %s\n" % CONVERSION_RATE)

# retrieve cards..
CARDS = []
if args.source == "file": # ..from source input file
    for line in open(args.input, "r"):
        CARDS.append({"name" : line.strip()})
elif args.source == "wishlist": # ..from deckbox.org wishlist
    for i in range(requests.get(DECKBOX_API).json()["total_pages"]):
        wishlist_page = requests.get(DECKBOX_API, params={"page": i+1}).json()
        for card in wishlist_page["items"]:
            CARDS.append({"name": card["name"]})

# fetch pricing data from scryfall and good games
for card in CARDS:

    print("Fetching: %s" % card["name"])

    # fetch scryfall data
    card["oracle_id"] = requests.get(SCRYFALL_API + "named", params={"exact" : card["name"]}).json()["oracle_id"]
    scryfall_cards = requests.get(SCRYFALL_API + "search", params={"q" : "oracleid:" + card["oracle_id"], "order" : "usd", "unique" : "prints"}).json()["data"]

    # extract each printings multiverse ids
    card["multiverse_ids"] = [id for sublist in [card["multiverse_ids"] for card in scryfall_cards] for id in sublist]

    # process non-foil and foil prices into single flat list
    scryfall_prices = [round(float(scryfall_card["prices"]["usd"]) * CONVERSION_RATE, 2) for scryfall_card in scryfall_cards if scryfall_card["prices"]["usd"] is not None]
    scryfall_prices.extend([round(float(scryfall_card["prices"]["usd_foil"]) * CONVERSION_RATE, 2) for scryfall_card in scryfall_cards if scryfall_card["prices"]["usd_foil"] is not None])
    scryfall_prices.sort()
    scryfall_prices.reverse()

    if args.verbose:
        print("\tFound:\t\t%s" % card["oracle_id"])
        print("\tPrintings:\t%s" % card["multiverse_ids"])
        print("\tSF Prices:\t%s" % scryfall_prices)

    # fetch good games data
    goodgames_prices = []
    for multiverse_id in card["multiverse_ids"]:
        # retrieve HTML from store page search for multiverse id.. GG don't have a plublic API :(
        soup = BeautifulSoup(urllib.request.urlopen(GOODGAMES_API + "?%s" % urllib.parse.urlencode({"mtg_multiverseid" : multiverse_id})).read().decode("utf-8"), features="html.parser")

        name = None
        price = None
        in_stock = True

        # skip printings that GG doesn't have
        if soup.ol is None:
            continue

        for li in soup.ol.children:
            if isinstance(li, NavigableString): # ignore empty strings
                continue
            for desc in li.descendants:
                if not isinstance(desc, NavigableString):
                    if desc.has_attr('class') and 'product-item-link' in desc['class']:
                        name = str(desc.text).strip()
                    if desc.has_attr('data-price-amount'):
                        price = float(desc["data-price-amount"])
                    if desc.has_attr('class') and 'stock' in desc['class']:
                        in_stock = False
        if name.startswith(card['name']):
            # TODO add logic for cards not in stock
            goodgames_prices.append(price)

    goodgames_prices.sort()
    goodgames_prices.reverse()

    if args.verbose:
        print("\tGG Prices:\t%s" % goodgames_prices)

    # add the pricing data
    card["prices"] = {
        "scryfall" : {
            "aud" : scryfall_prices[-1]
        },
        "goodgames" : {
            "aud" : goodgames_prices[-1]
        }
    }

    # scryfall is a public api and will blacklist IPs if they're requesting too frequently.
    time.sleep(1/10)

# define a monsterous commpare function for sorting
def compare(card):
    return float(card["prices"]["goodgames"]["aud"]) - float(card["prices"]["scryfall"]["aud"])

# sort the cards by the difference between scryfall and goodgames
CARDS.sort(key=compare)
# then print 'em out
for card in CARDS:
    args.outstream.write(card["name"] + ":\n")
    for vendor in card["prices"]:
        args.outstream.write("\t%s:\t%s AUD\n" % (vendor, card["prices"][vendor]["aud"]))
    args.outstream.write("\n")
