import requests
from bs4 import BeautifulSoup

import sys
import json

from typing import *

def get_html(s: requests.Session, state_id: str, action_str: str, btn_id: str) -> BeautifulSoup:
    print(f"Making req: {action_str}: {btn_id}")
    url = "https://splus.cumulus.vub.ac.be/SWS/v3/evenjr/NL/STUDENTSET/studentset.aspx"
    data = {
        "__VIEWSTATE": state_id,
        "__EVENTTARGET": action_str, # Clicked event
        "__EVENTARGUMENT": btn_id, # clicked btn
    }
    req = s.post(url, data=data)
    html = BeautifulSoup(req.text, features="html5lib")
    
    return html, html.find(id='__VIEWSTATE').get("value")

def get_sub_ids(section_html: BeautifulSoup) -> List[str]:
    td = section_html.find_all("td", class_="tCell")
    td.extend(section_html.find_all("td", class_="tCellSelected"))
    return list(map(lambda elem: elem['id'], td))

def get_sets(html: BeautifulSoup) -> List[BeautifulSoup]:
    return html.find_all("td", class_="td-set")

def get_ical(s: requests.Session, initial_html: BeautifulSoup):
    tree = {}
    
    # get all classes
    dlObject = initial_html.find(id="dlObject")
    dlObject_options = dlObject.find_all("option")
    opt_vals = list(map(lambda i: {"id": i.get("value"), "value": i.contents[0]}, dlObject_options))
    print(f"({len(opt_vals)})", end="")
    
    # Select class
    for opt in opt_vals:
        ical_html = ""
        
        try:
            url = "https://splus.cumulus.vub.ac.be/SWS/v3/evenjr/NL/STUDENTSET/Default.aspx"
            evt_validation = initial_html.find(id="__EVENTVALIDATION").get("value")
            evt_view_state = initial_html.find(id="__VIEWSTATE").get("value")
            evt_radio = initial_html.find(id="RadioType_2").get("value")

            data = {
                "__EVENTVALIDATION": evt_validation,
                "__EVENTTARGET": "",
                "__EVENTARGUMENT": "",
                "__LASTFOCUS": "",
                "__VIEWSTATE": evt_view_state,
                "tLinkType": "setbytag",
                "tWildcard": "",
                "dlObject": opt["id"], # Gekozen vak
                "lbWeeks": [
                    "1;2;3;4;5;6;7;8;9;10;11;12;13;14",
                    "22;23;24;25;26;27;28;29;32;33;34;35;36"
                ],
                "lbDays": "1;2;3;4;5;6",
                "dlPeriod": "2;3;4;5;6;7;8;9;10;11;12;13;14;15;16;17;18;19;20;21;22;23;24;25;26;27;28;29;30;31;32;33",
                "RadioType": evt_radio,
                "bGetTimetable": "Bekijk+het+lesrooster",
            }

            opt_id = opt["id"]
            #print(f"Making request to Default with {opt_id}")
            print(".", end="")
            select_req = s.post(url, data=data) # Send request
            #select_html = BeautifulSoup(select_req.text)

            # ical
            url = "https://splus.cumulus.vub.ac.be/SWS/v3/evenjr/NL/STUDENTSET/showtimetable.aspx"
            ical_req = s.get(url) # Go to ical screen
            ical_html = BeautifulSoup(ical_req.text, features="html5lib")
            url_input = ical_html.find(id="ical_url")
            ical_url = url_input.get("value")

            tree[opt["id"]] = {
                "url": ical_url,
                **opt
            }
        except AttributeError as err:
            opt_id = opt["id"]
            print(f"ICal could not be found for {opt}, error: {err}", file=sys.stderr)
            print(ical_html, file=sys.stderr)
        
    print() # esthetics
    # Next calendar
    print("Going back")
    url = "https://splus.cumulus.vub.ac.be/SWS/v3/evenjr/NL/STUDENTSET/studentset.aspx?"
    back_req = s.get(url)
    back_html = BeautifulSoup(back_req.text, features="html5lib")
    view_state = back_html.find(id="__VIEWSTATE").get("value")
    
    return tree, view_state

def get_opleid(s: requests.Session, state_id: str, initial_html: BeautifulSoup):
    tree = {}
    sets = get_sets(initial_html)
    opleidingen = get_sub_ids(sets[2])
    for opleiding in opleidingen:
        tree[opleiding] = {}
        html, state_id = get_html(s, state_id, "tTagClicked", opleiding)
        ical, state_id = get_ical(s, html)
        tree[opleiding] = ical
    return tree, state_id

def get_fac(s: requests.Session, state_id: str, inital_html: BeautifulSoup):
    tree = {}
    sets = get_sets(inital_html)
    fac = get_sub_ids(sets[1])
    for f in fac:
        html, state_id = get_html(s, state_id, "tDepartmentClicked", f)
        opl, state_id = get_opleid(s, state_id, html)
        tree[f] = opl
    return tree, state_id

def get_type(s: requests.Session, state_id: str, initial_html: BeautifulSoup):
    tree = {}
    sets = get_sets(initial_html)
    types = get_sub_ids(sets[0])
    for t in types:
        html, state_id = get_html(s, state_id, "tTypeClicked", t)
        fac, state_id = get_fac(s, state_id, html)
        tree[t] = fac
    return tree, state_id

# Buildng tree
with requests.Session() as s:
    s.headers["User-Agent"] = "Mozilla/5.0 (X11; Linux x86_64; rv:92.0) Gecko/20100101 Firefox/92.0"
    s.headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    
    url = "https://splus.cumulus.vub.ac.be/SWS/v3/evenjr/NL/STUDENTSET/studentset.aspx"
    req = s.get(url) # Inital req
    html = BeautifulSoup(req.text, features="html5lib")
    view_state = html.find(id='__VIEWSTATE').get("value")

    print("[*] Set Content Type to form validation")
    s.headers["Content-Type"] = "application/x-www-form-urlencoded"
    
    tree = get_type(s, view_state, html)
    
data_tree = json.dumps(tree[0])
with open("data_tree_dummy.json", "w") as f:
    f.write(data_tree)
