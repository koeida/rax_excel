import json
import math
import requests
from operator import itemgetter
from conn_info import conn_info

class ShopifyConnector:

    def __init__(self, start_date):
        self.SEASON_START_DATE = start_date
        self.SHOP_NAME = conn_info["SHOP_NAME"]
        self.API_KEY = conn_info["API_KEY"]
        self.PASSWORD = conn_info["PASSWORD"]
        self.API_URL = "https://{}.myshopify.com/admin/".format(self.SHOP_NAME)

    def do_request(self, rest_string):
        return requests.get(self.API_URL + rest_string, auth=(self.API_KEY,self.PASSWORD))

    def get_carrier_services(self):
        return requests.get(self.API_URL + "carrier_services.json", auth=(self.API_KEY,self.PASSWORD))

    def get_shipping_cost(orig, dest, items, carrier, self): 
        pass

    def do_post(self,rest_string,data):
        headers = {"Content-Type": "application/json",
                   "Accept": "*/*"}
        return requests.post(
                self.API_URL + rest_string,
                auth=(self.API_KEY,self.PASSWORD),
                data=data,
                headers=headers)

    def get_all_customers(self):
        resp = []
        x = 0
        while(True):
            x += 1
            response = self.do_request("customers.json?limit=250&page=" + str(x))
            if response.ok:
                res = json.loads(response.text)
                if(len(res["customers"]) == 0):
                    break
                for c in json.loads(response.text)["customers"]:
                    resp.append(c)
            else:
                raise("Unable to get list of customers")
        return resp

    def get_products(self,products):
        products = map(str,products)
        products = ",".join(products)
        req_str = "products.json?ids=" + products
        response = self.do_request(req_str)
        return response

    def get_all_products2(self, limit):
        req_str = "products.json?limit=" + str(limit)
        response = self.do_request(req_str)
        return response

    def put_order(self,order_json):
        return self.do_post("orders.json",order_json)

    def get_orders_list(self):
        # get all open (and ready-to-ship?) orders
        response = self.do_request("orders.json?limit=250&fields=id,customer,order_number")
        results = {}
        if response.ok:
            orders = json.loads(response.text)["orders"]
            for i in orders:
                key = "{} - {}".format(i["order_number"], i["customer"]["default_address"]["company"])
                results[key] = i["id"]
        return results

    def process_products_list(self, products, new_cards):
        variants = []
        for product in products:
            for variant in product["variants"]:
                v = {
                        "barcode": variant["barcode"],
                        "id": product["id"],
                        "variant_id": variant["id"],
                        "grams": variant["grams"],
                        "price": variant["price"]}
                variants.append(v)
                
        return variants

    def process_products_list_old(self, products, new_cards):
        # cards are: list of (item["title"], item["product_id"], item["variant_id"])
        # products are: list of {id, variant}
        # create products dict for easier lookup
        barcode_lookup = {}
        for product in products:
            barcode_lookup.setdefault(product["id"], {})
            for variant in product["variants"]:
                barcode_lookup[product["id"]].setdefault(variant["id"], variant["barcode"])
        results = []
        cards = sorted(new_cards, key=itemgetter(0))
        for card in cards:
            try:
                catnum, name = card[0].split(" - ", maxsplit=1)
                results.append((name, catnum, barcode_lookup[card[1]][card[2]], card[3]))
            except ValueError:
                title = card[0]
                results.append((title, title, barcode_lookup[card[1]][card[2]]))
            except KeyError:
                continue
        return results

    def get_all_products(self):
        results = None

        resp_count = self.do_request('products/count.json')
        if resp_count.ok:
            pages = math.ceil(json.loads(resp_count.text)["count"] / 250)
            cards = set()
            products = []
            curr_page = 1
            while curr_page <= pages:
                resp_get_prods = self.do_request("products.json?limit=250&page={}&fields=id,title,variants".format(curr_page))
                if resp_get_prods.ok:
                    curr_prods = json.loads(resp_get_prods.text)["products"]
                    for prod in curr_prods:
                        if prod["variants"] is not None and len(prod["variants"]) > 0:
                            cards.add((prod["title"],
                                       prod["id"],
                                       prod["variants"][0]["id"],
                                       prod["variants"][0]["price"],
                                       prod["variants"][0]["grams"]))
                            products.append({
                                "id": prod["id"],
                                "variants": prod["variants"],
                                "price": prod["variants"][0]["price"]})
                    curr_page += 1
                else:
                    break
            results = self.process_products_list(products, cards)

        return results

    def get_cards_needed_list(self, order_id):
        results = None
        new_cards = None
        current_products = set()
        past_products = set()

        resp_curr_order = self.do_request("orders/{}.json?limit=250&fields=id,customer,order_number,line_items,created_at".format(order_id))
        if resp_curr_order.ok:
            # get order
            current_order = json.loads(resp_curr_order.text)["order"]
            for item in current_order["line_items"]:
                current_products.add((item["title"], item["product_id"], item["variant_id"]))
            # get customer from order
            customer_id = current_order["customer"]["id"]
            # use customer_id to get all customer's orders since season start until current order
            since = "created_at_min={}T00:00:00-00:00".format(self.SEASON_START_DATE)
            until = "created_at_max={}".format(current_order["created_at"])
            req_str = "orders.json?customer_id={}&{}&{}&limit=250&fields=id,customer,order_number,line_items,created_at".format(customer_id, since, until)
            resp_all_orders = self.do_request(req_str)
            if resp_all_orders.ok:
                # build list of current order prods and past order prods
                past_orders = json.loads(resp_all_orders.text)["orders"]
                for order in past_orders:
                    if order["order_number"] == current_order["order_number"]:
                        continue
                    for item in order["line_items"]:
                        past_products.add((item["title"], item["product_id"], item["variant_id"]))
                # get list of what is in current order and not in past orders
                get_id = lambda e: e[0].split(" ")[0]
                new_cards = current_products - past_products
        if new_cards:
            ids = [str(x[1]) for x in new_cards]
            resp_barcodes = self.do_request("products.json?ids={}&limit=250&fields=id,variants".format(",".join(ids)))
            if resp_barcodes.ok:
                products = json.loads(resp_barcodes.text)["products"]
                results = self.process_products_list(products, new_cards)
            else:
                print(resp_barcodes.status_code)
        return results
