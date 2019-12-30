from html.parser import HTMLParser

# create a subclass and override the handler methods
class GoodGamesParser(HTMLParser):

    # is the current tag a pricing tag, ie <span class="price">
    is_price_flag = False
    # card was in stock
    is_instock = False

    price = None
    interim_price = None # working price for comparison

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "class" in attrs:
            if attrs["class"] == "price":
                self.is_price_flag = True
            elif "availability" in attrs["class"]:
                # only use out-of-stock prices if we're yet to find a print in stock.
                if self.price is None or ("out-of-stock" in attrs["class"] and not self.is_instock and float(self.interim_price) < float(self.price)):
                    self.price = self.interim_price
                if "in-stock" in attrs["class"]:
                    if not self.is_instock or float(self.interim_price) < float(self.price):
                        self.price = self.interim_price
                    self.is_instock = True

    def handle_data(self, data):
        if self.is_price_flag: # only consume pricing data
            self.is_price_flag=False
            self.interim_price=str.strip(data)[1:]
