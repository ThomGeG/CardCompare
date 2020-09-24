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

import os
import re
import csv
import json
import time
import urllib
import requests
from functools import reduce

os.system("") # magic to get ANSI codes working

# define some API endpoints
SCRYFALL_API    = "https://api.scryfall.com/cards/"
CURRENCY_API    = "https://api.exchangeratesapi.io/latest"
SETS_API        = "https://deckbox-api.herokuapp.com/api/users/%s/sets" % args.input
DECKBOX_API     = "https://deckbox.org/sets/export/%s?format=csv&columns=Type" % list(filter(lambda x: x["name"] == 'wishlist', requests.get(SETS_API).json()["items"]))[0]["id"]

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
    for card in [dict(x) for x in csv.DictReader(requests.get(DECKBOX_API).text.split('\n'))]:
        CARDS.append({"name": card["Name"]})

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

    if args.verbose:
        print("\tFound:\t\t%s" % card["oracle_id"])
        print("\tPrintings:\t%s" % card["multiverse_ids"])
        print("\tSF Prices:\t%s" % scryfall_prices)

    # fetch good games data
    goodgames_prices = []

    # hit the API directly
    response = requests.post(
        "https://wf19vv0nsf-dsn.algolia.net/1/indexes/*/queries",
        data=json.dumps({"requests" : [{
            "indexName": "magento2_tcg_productiondefault_products",
            "params": "query=%s" % card["name"]
        }]}),
        params={
            "x-algolia-application-id" : "WF19VV0NSF",
            "x-algolia-api-key" : "MDdmNjA0Mjc1YzRkZjI4MWMwZmQyMDI4MDc5NDY4ZjlkYzJmOTVmMWY5Yjc3MGFkNDRiODA4YjU0MDVlM2Q1YnRhZ0ZpbHRlcnM9"
        },
        headers={
            "Referer" : "https://tcg.goodgames.com.au/"
        }
    ).json()["results"][0]

    if len(response["hits"]) >= 0:
        for hit in response["hits"]:
            if ("mtg_multiverseid" in hit and hit["mtg_multiverseid"] in card["multiverse_ids"]) or re.compile("^%s (- Foil )?\(.+\)$" % re.escape(card["name"])).match(hit["name"]):
                goodgames_prices.append((hit["price"]["AUD"]["default"], hit["stock_qty"]))

    goodgames_prices.sort(key=lambda x: x[0])
    if args.verbose:
        print("\tGG Prices:\t[%s]" % reduce(lambda s, pair: s + "%s%s\033[0m, " % ('\033[92m' if pair[1] > 0 else '\033[91m', pair[0]), goodgames_prices, "")[:-2])

    # add the pricing data
    card["prices"] = {
        "scryfall" : {
            "aud" : scryfall_prices
        },
        "goodgames" : {
            "aud" : goodgames_prices
        }
    }

    # scryfall is a public api and will blacklist IPs if they're requesting too frequently.
    time.sleep(1/10)
