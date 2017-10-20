#! /usr/bin/python3
from connection import ShopifyConnector
from copy import deepcopy
from openpyxl import Workbook, load_workbook
from tkinter import *
from tkinter.ttk import *
from tkinter.filedialog import askopenfilename
import tkinter.messagebox

import datetime
import itertools
import json
import pickle
import sys

from keeg_functional import *

# returns true if s is convertable to an int
def intable(s):
    try:
        int(s)
        return True
    except:
        return False

def is_valid_line(l):
    if ((l[0].value == None or intable(l[0].value)) and
        (intable(l[1].value)) and
        (l[2].value != None) and
        (l[3].value != None) and
        (intable(l[4].value))):
        return True
    else:
        return False

def get_shopify_conn():
    year = datetime.date.today().year
    if datetime.date.today().month < 11:
        year -= 1

    return ShopifyConnector(str(year)+ "-11-01")

#Convert order row to a json-compatible format
def row_to_json(r):
    return {
        "barcode": int(r[4].value[:-1]),
        "quantity": int(r[0].value),
        "requires_shipping": "true",
        "title": r[2].value
    }

def get_product(products,barcode):
    item = first(lambda i: str(i["barcode"]) == str(barcode),products)
    if item == None:
        raise Exception("Item barcode " + str(barcode) + " not found.")
    return item

#Replace item barcode with id
#Add product id
#Add product weight
def convert_id(variants,r):
    result = deepcopy(r) 
    item = get_product(variants, r["barcode"])
    result["variant_id"] = item["variant_id"]
    result["product_id"] = item["id"]
    result["grams"] = item["grams"]
    return result

def makeform(root, fields):
   entries = []
   for field in fields:
      row = Frame(root)
      lab = Label(row, width=15, text=field, anchor='w')
      ent = Entry(row)
      row.pack(side=TOP, fill=X, padx=5, pady=5)
      lab.pack(side=LEFT)
      ent.pack(side=RIGHT, expand=YES, fill=X)
      entries.append((field, ent))
   return entries

#Assign a price to each item
def add_price(variants,r):
    result = deepcopy(r)
    item = get_product(variants, r["barcode"])
    result["price"] = item["price"]
    return result

def get_carrier_names(conn):
    cs_resp = conn.get_carrier_services().json()
    carriers = map(lambda s: s["name"], cs_resp["carrier_services"])
    return list(carriers)

def gen_order(conn, cid, email):
    form = load_workbook(filename="seas.xlsx", read_only=True)['Order Form'] 

    variants = conn.get_all_products()

    rows = pipe(list(form.rows),[
        p(filter,is_valid_line), # Remove header/footer rows
        p(filter,lambda r: r[0].value != None), # Remove lines without a quantity specified
        p(map,row_to_json),
        p(map,p(convert_id,variants)),
        p(map,p(add_price,variants)),
        list])

    order = json.dumps(
            {
                "order": 
                {
                 "financial_status": "pending",
                 "email": email,
                 "customer": {"id": int(cid) },
                 "line_items": rows
                }
            }, sort_keys=True, indent=4)
    return order
    
def make_order(customer,customers,xls_path):
    if customer.strip() == "":
        tkinter.messagebox.showerror("Error","You need to select a customer.")
        return
    if xls_path == "":
        tkinter.messagebox.showerror("Error","You need to select an excel document containing the order.")
        return
    
    cid = customers[customer]["cid"]
    email = customers[customer]["email"]
    order = gen_order(conn, cid, email)
    #print(order)
    resp = conn.put_order(order)
    if resp.ok:
        tkinter.messagebox.showinfo("Success","Order successfully created.") 
    else:
        tkinter.messagebox.showerror("Error", "Error creating order: " + resp.text)

def select_file(label):
    fname = askopenfilename()
    label["text"] = fname

def init():
    conn = get_shopify_conn()

    # Test/console mode
    if len(sys.argv) > 1 and sys.argv[1] == "-t":
        carriers = get_carrier_names(conn)
        print(carriers)
        customers = conn.get_all_customers()
        print(customers[-1])
        exit()

    customers = None
    if "-c" in sys.argv: 
        customers = pickle.load(open("all_customers.p","rb"))
    else:
        customers = conn.get_all_customers()

    customer_ids = {}
    # Remove customers who have no address
    for c in customers:
        if len(c["addresses"]) > 0:
            cid = str(c["addresses"][0]["id"])
            if c["addresses"][0]["company"] != None: 
                c["id"] = c["default_address"]["company"] + \
                        " (" + c["default_address"]["name"] + ")" + \
                        " [" + cid + "]"
            else:
                c["id"] = c["default_address"]["name"] + " [" + cid + "]"
            customer_ids[c["id"]] = {}
            customer_ids[c["id"]]["cid"] = cid
            customer_ids[c["id"]]["email"] = c["email"]
        else:
            c["id"] = "NULL"
    customer_list = pipe(customers,[
        p(filter, lambda c: c["id"] != "NULL"),
        p(map, lambda c: c["id"]),
        list])
    customer_list.sort(key = lambda c: c.upper())
    return (conn, customer_ids, customer_list)

root = Tk()
root.title("Seed Racks Excel Order Reader")
root.geometry("600x80")

try:
    w = Label(root,text="LOADING...")
    w.pack()
    w.wait_visibility()
    conn, customer_ids, customer_list = init()
    w.destroy()
except: 
    tkinter.messagebox.showerror("Error retrieving customer info",
                                 "Error retrieving customer info: Either the internet ain't working or your shopify connection info is wrong in conn_info.py")
    exit()


# Allow user to select pre-existing customer
Label(root, text="Select Customer:").pack()
customer_selection = StringVar(root)
customer_selection.set(customer_list[0])
customer_menu = Combobox(root)
customer_menu['values'] = customer_list
customer_menu['width'] = 100
customer_menu.pack()

browse_row = Frame(root)
lab = Label(browse_row, width=15, text="", anchor='w', background="white", relief="sunken")
browse_button = Button(browse_row, text="Select Excel File", command=lambda: select_file(lab))
browse_row.pack(side=TOP, fill=X, padx=5, pady=5)
browse_button.pack(side=LEFT)
lab.pack(side=RIGHT, padx=5, expand=YES, fill=X)

Button(root, text="Create Order", command=lambda: make_order(
    customer_menu.get(),
    customer_ids,
    lab["text"])).pack()

# Remaining work: 
# Whatever that missing piece of info Elspeth mentioned in the last email
# Version control

browse_button.pack()

root.mainloop()
