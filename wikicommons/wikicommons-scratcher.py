"""
This file is dedicated to obtain a .csv record report for WikiCommons
Data.
"""

# Standard library
import datetime as dt
import os
import random
import sys
import time
import traceback

# Third-party
import requests

CWD = os.path.dirname(os.path.abspath(__file__))
CALLBACK_INDEX = 2
CALLBACK_EXPO = 0
MAX_WAIT = 64
DATA_WRITE_FILE = CWD
LICENSE_CACHE = {}


def expo_backoff():
    """Performs exponential backoff upon call.
    The function will force a wait of CALLBACK_INDEX ** CALLBACK_EXPO + r
    seconds, where r is a decimal number between 0.001 and 0.999, inclusive.
    If that value is higher than MAX_WAIT, then it will just wait MAX_WAIT
    seconds instead.
    """
    global CALLBACK_EXPO
    backoff = random.randint(1, 1000) / 1000 + CALLBACK_INDEX**CALLBACK_EXPO
    time.sleep(min(backoff, MAX_WAIT))
    if backoff < MAX_WAIT:
        CALLBACK_EXPO += 1


def expo_backoff_reset():
    """Resets the CALLBACK_EXPO to 0."""
    global CALLBACK_EXPO
    CALLBACK_EXPO = 0


def get_content_request_url(license):
    """Provides the API Endpoint URL for specified parameters' WikiCommons
    contents.

    Args:
        license:
            A string representing the type of license, and should be a segment
            of its URL towards the license description. Alternatively, the
            default None value stands for having no assumption about license
            type.

    Returns:
        string: A string representing the API Endpoint URL for the query
        specified by this function's parameters.
    """
    base_url = (
        r"https://commons.wikimedia.org/w/api.php?"
        r"action=query&prop=categoryinfo&titles="
        f"Category:{license}&format=json"
    )
    return base_url


def get_subcat_request_url(license):
    """Provides the API Endpoint URL for specified parameters' WikiCommons
    subcategories for recursive searching.

    Args:
        license:
            A string representing the type of license, and should be a segment
            of its URL towards the license description. Alternatively, the
            default None value stands for having no assumption about license
            type.

    Returns:
        string: A string representing the API Endpoint URL for the query
        specified by this function's parameters.
    """
    base_url = (
        r"https://commons.wikimedia.org/w/api.php?"
        r"action=query&cmtitle="
        f"Category:{license}"
        r"&cmtype=subcat&list=categorymembers&format=json"
    )
    return base_url


def get_subcategories(license, eb=False):
    """Obtain the subcategories of LICENSE in WikiCommons Database for
    recursive searching.

    Args:
        license:
            A string representing the type of license, and should be a segment
            of its URL towards the license description. Alternatively, the
            default None value stands for having no assumption about license
            type.
        eb:
            A boolean indicating whether there should be exponential callback.
            Is by default False.

    Returns:
        list: A list representing the subcategories of current license type
        in WikiCommons dataset from a provided API Endpoint URL for the query
        specified by this function's parameters.
    """
    try:
        request_url = get_subcat_request_url(license)
        search_data = requests.get(request_url).json()
        cat_list = []
        for members in search_data["query"]["categorymembers"]:
            cat_list.append(
                members["title"].replace("Category:", "").replace("&", "%26")
            )
        return cat_list
    except Exception as e:
        if eb:
            expo_backoff()
            get_subcategories(license)
        elif "query" not in search_data:
            print(search_data)
            print("This query will not be processed due to empty subcats.")
        else:
            print("ERROR (1) Unhandled exception:", file=sys.stderr)
            print(traceback.print_exc(), file=sys.stderr)
            sys.exit(1)


def get_license_contents(license, eb=False):
    """Provides the metadata for query of specified parameters.

    Args:
        license:
            A string representing the type of license, and should be a segment
            of its URL towards the license description. Alternatively, the
            default None value stands for having no assumption about license
            type.
        eb:
            A boolean indicating whether there should be exponential callback.
            Is by default False.

    Returns:
        dict: A dictionary mapping metadata to its value provided from the API
        query of specified parameters.
    """
    try:
        url = get_content_request_url(license)
        search_data = requests.get(url).json()
        file_cnt = 0
        page_cnt = 0
        for id in search_data["query"]["pages"]:
            lic_content = search_data["query"]["pages"][id]
            file_cnt += lic_content["categoryinfo"]["files"]
            page_cnt += lic_content["categoryinfo"]["pages"]
        search_data_dict = {
            "total_file_cnt": file_cnt,
            "total_page_cnt": page_cnt,
        }
        return search_data_dict
    except Exception as e:
        if eb:
            expo_backoff()
            get_license_contents(license)
        elif "queries" not in search_data:
            print(search_data)
            print("This query will not be processed due to empty result.")
        else:
            print("ERROR (1) Unhandled exception:", file=sys.stderr)
            print(traceback.print_exc(), file=sys.stderr)
            sys.exit(1)


def set_up_data_file():
    """Writes the header row to file to contain WikiCommons Query data."""
    header_title = "LICENSE TYPE,File Count, Page Count"
    with open(DATA_WRITE_FILE, "a") as f:
        f.write(header_title + "\n")


def record_license_data(license_type, license_alias):
    """Writes the row for LICENSE_TYPE to file to contain WikiCommon Query.

    Args:
        license_type:
            A string representing the type of license, and should be a segment
            of its URL towards the license description. Alternatively, the
            default None value stands for having no assumption about license
            type.
        license_alias:
            A forward slash separated string that stands for the route by which
            this license is found from other parent categories. Used for
            eventual efforts of aggregating data.
    """
    search_result = get_license_contents(license_type)
    data_log = (
        f"{license_alias},"
        f"{search_result['total_file_cnt']},{search_result['total_page_cnt']}"
    )
    with open(DATA_WRITE_FILE, "a") as f:
        f.write(f"{data_log}\n")


def recur_record_all_licenses(alias="Free_Creative_Commons_licenses"):
    """Recursively records the data of all license types findable in the
    license list and its individual subcategories, then records these data into
    the DATA_wRITE_FILE as specified in that constant.

    Args:
        license_alias:
            A forward slash separated string that stands for the route by which
            this license is found from other parent categories. Used for
            eventual efforts of aggregating data. Defaults to
            "Free_Creative_Commons_licenses".
    """
    cur_cat = alias.split("/")[-1]
    subcategories = get_subcategories(cur_cat)
    if cur_cat not in LICENSE_CACHE:
        record_license_data(cur_cat, alias)
        LICENSE_CACHE[cur_cat] = True
        print("DEBUG", f"Logged {cur_cat} from {alias}")
        for cats in subcategories:
            recur_record_all_licenses(alias=f"{alias}/{cats}")


def main():
    global DATA_WRITE_FILE
    today = dt.datetime.today()
    DATA_WRITE_FILE += (
        f"/data_wikicommons_{today.year}_{today.month}_{today.day}.txt"
    )
    set_up_data_file()
    recur_record_all_licenses()
    DATA_WRITE_FILE = CWD


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        sys.exit(e.code)
    except KeyboardInterrupt:
        print("INFO (130) Halted via KeyboardInterrupt.", file=sys.stderr)
        sys.exit(130)
    except Exception:
        print("ERROR (1) Unhandled exception:", file=sys.stderr)
        print(traceback.print_exc(), file=sys.stderr)
        sys.exit(1)
