import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
import time
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import sys
from datetime import date, datetime,timezone as tz
import os.path
from pytz import timezone
import os
from pathlib import Path
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pathlib import Path
import json
import os
import pandas as pd
import redis
import json
import time
import argparse

"""
    find path to parent dir
"""
parent_dir = Path(__file__).parent

print("parent_dir",parent_dir)

# ---------------------------------------------------------------------------------------*
# ------------------------------Set chrome and selenium config---------------------------*
# ---------------------------------------------------------------------------------------*
# path_to_chrome_driver = os.path.join(parent_dir, '../chromedriver')
path_to_chrome_driver = "/usr/bin/chromedriver"


chrome_options = Options()
chrome_options.add_argument('--headless')
# chrome_options.add_argument("window-size=1920x1080")
# chrome_options.add_argument("--disable-gpu")
# chrome_options.add_argument("--no-sandbox")
# chrome_options.add_argument("start-maximized")
# chrome_options.add_argument("enable-automation")
# chrome_options.add_argument("--disable-infobars")
# chrome_options.add_argument("--disable-dev-shm-usage")


# Add this argument to remove the "controlled by automated software" message
chrome_options.add_argument("--disable-infobars")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")

# Set the window size (adjust this to your preference)
chrome_options.add_argument("window-size=1920,1080")

# Disable GPU hardware acceleration (optional, helps in some environments)
chrome_options.add_argument("--disable-gpu")

# Prevent Chrome from running in a sandbox (useful in some environments, like CI)
chrome_options.add_argument("--no-sandbox")

# Start Chrome in maximized mode (makes sure Chrome opens in a large window)
chrome_options.add_argument("--start-maximized")

# Enable automation optimizations
chrome_options.add_argument("enable-automation")

# Disable "Chrome is being controlled by automated software" message
chrome_options.add_argument("--disable-infobars")

# Disable dev-shm-usage (useful when running Chrome in Docker or low-memory environments)
chrome_options.add_argument("--disable-dev-shm-usage")

# Disable browser-side navigation (helps with slow page loads in some cases)
chrome_options.add_argument("--disable-browser-side-navigation")

# Disable the Blink features to reduce detection by websites
chrome_options.add_argument("--disable-blink-features=AutomationControlled")

# Open Chrome in incognito mode (optional, can be useful to avoid cache or cookies)
chrome_options.add_argument("--incognito")

# Set a custom user-agent (optional, helpful to make the browser appear as a regular user)
chrome_options.add_argument(
    "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"
)


service = Service(
    executable_path=path_to_chrome_driver)

driver = webdriver.Chrome(service=service, options=chrome_options)


# ---------------------------------------------------------------------------------------*
# --------------------------------------Variable Declared--------------------------------*
# ---------------------------------------------------------------------------------------*

sleep_time = 23

# ---------------------------------------------------------------------------------------*
# -----------------------------------Check Dir-------------------------------------------*
# ---------------------------------------------------------------------------------------*
def check_dir():
    MYDIR = ("CSV")
    CHECK_FOLDER = os.path.isdir(MYDIR)

    if not CHECK_FOLDER:
        os.makedirs(MYDIR)
        print("created folder : ", MYDIR)

    else:
        print(MYDIR, "folder already exists.")


def update_google_sheet(values, _parent_dir, _spread_sheet_name, _sheet_name):

    # define the scope
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']

            #  /home/dfuse/hyperliquid-exporter/crypto-analysis-341008-b75fdac731c9.json

    # add credentials to the account
    google_auth_file = os.path.join(
        _parent_dir, 'crypto-analysis-341008-b75fdac731c9.json')

    print(google_auth_file)

    creds = ServiceAccountCredentials.from_json_keyfile_name(
        google_auth_file, scope)

    # authorize the clientsheet
    client = gspread.authorize(creds)

    # get the instance of the Spreadsheet
    spread_sheet_name = _spread_sheet_name
    spread_sheet = client.open(spread_sheet_name)

    sheet_name = _sheet_name

    # get the first sheet of the Spreadsheet
    sheet_instance = spread_sheet.worksheet(sheet_name)
    records_data = sheet_instance.get_all_records()
    try:
        records_data = sheet_instance.get_all_records()
        # sheet = service.spreadsheets()
        # resultc = sheet.values().get(spreadsheetId=SAMPLE_SPREADSHEET_ID,
        #  range = sheet_name+'!C:C').execute()
        # records_data=resultc.get('values', [])

        tmp1 = list()

        if not records_data:
            print('No data found.')
            tmp1 = values
            # return
        else:
            print("data found")
            tmp1 = values[1:]

        a = spread_sheet.values_append(sheet_name, {'valueInputOption': 'USER_ENTERED'},
                                       {'values': tmp1})

        print("\n\nssddsd")
        print(a)
    except Exception as err:
        print(err)



# ---------------------------------------------------------------------------------------*
# --------------------------------------Scrap xe protocol--------------------------------*
# ------------------------ https://www.xe.com/currencyconverter -------------------------*

def scrape_xe_for_bhat_price():
    

    while True:

        data_list = list()

    
        
        try:
            """
                Get time
            """
            now = datetime.now(timezone("Asia/Kolkata"))
            # now_1 = datetime.utcnow()
            now_utc = datetime.now(tz.utc)

            # Format it as a string, e.g., "YYYY-MM-DD HH:MM:SS"
            formatted_time = now_utc.strftime("%Y-%m-%d %H:%M:%S")
            print("Formatted UTC time:", formatted_time)

            # print(now)

            

            driver.get(
                "https://www.grassfoundation.io/stake/delegations")
            driver.implicitly_wait(10)

            time.sleep(10)
            print("\nStart 1: ", driver.title)

            print("\loading... ")
            time.sleep(10)
            print("loaded")

            print("Scrolling.. ")

            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(10)  # Wait for content to load (adjust the sleep time as needed)
            print("scrolled.. ")


            # ---------------------------------------------------------------------------------------*
            # --------------------------------------Total Deposit------------------------------------*
            # ---------------------------------------------------------------------------------------*
            table_tag = driver.find_element(
                By.XPATH, "/html/body/div[1]/div[2]/div[2]/main/div/div[3]/div/div[2]/table")


            print("\ntable tag", table_tag,
                  table_tag.text)
            
             # Extract table rows
            rows = table_tag.find_elements(By.TAG_NAME, "tr")

            print("total rows", len(rows))

            for ind,item in enumerate(rows):

                data_dict = dict()
                # if ind == 0: continue 
                print("\nitem ",item,item.text)

                data_dict['date_time_UTC'] = formatted_time

                divs = item.find_elements(By.TAG_NAME, "td")
                # for ind2,item_2 in enumerate(divs):
                #     # if ind2 == 1 or ind2 == 2 or ind2 > 4 : continue 
                #     if ind2 == 3 : continue 
                #     print("\nitem2 ind2",ind2,item_2,item_2.text)

                data_dict['validator'] = divs[0].text
                data_dict['delegated amount']=divs[1].text
                data_dict['Commission'] = divs[2].text

                data_list.append(data_dict)

            final_list = data_list[0::]
            print("final_list", len(final_list))

            tmp = [list(final_list[0].keys())]
            for i in final_list:
                tmp.append(list(i.values()))

            update_google_sheet(tmp,parent_dir,'Grass Router Node','Staking Data')
            # print("Sleep for {} secs.....".format(sleep_time))
            # time.sleep(sleep_time)
            # print("Awake...")
            # return all_list
        except Exception as ex:
            print("Got an error while running scraper: ", str(ex))
            print("Sleep for {} secs.....".format(sleep_time))
            time.sleep(sleep_time)
            print("Awake...")
            continue
        else:
            break


if __name__ == "__main__":

    # check_dir()

    googledata = scrape_xe_for_bhat_price()

    driver.quit()
