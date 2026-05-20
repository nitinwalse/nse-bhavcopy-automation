import os
import json
import requests
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import io
import time

def get_bhavcopy():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }
    for i in range(5):
        d = datetime.now() - timedelta(days=i)
        if d.weekday() > 4: # शनिवार आणि रविवार वगळा
            continue
        date_str = d.strftime('%d%m%Y')
        url = f"https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{date_str}.csv"
        try:
            s = requests.Session()
            s.get("https://www.nseindia.com", headers=headers, timeout=10)
            time.sleep(2)
            response = s.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                print(f"Data downloaded for {date_str}")
                return pd.read_csv(io.StringIO(response.text))
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(2)
    return None

def main():
    df = get_bhavcopy()
    if df is None or df.empty:
        print("Failed to download data.")
        return

    df.columns = df.columns.str.strip()
    
    # १. फक्त 'EQ' सिरीज ठेवणे
    df_eq = df[df['SERIES'].astype(str).str.strip() == 'EQ'].copy()
    
    # २. सर्व नको असलेले शब्द (कडक फिल्टर)
    filter_keywords = 'BEES|ETF|GOLD|LIQUID|CASE|SILVER|GILT|METAL|ALPL'
    df_eq = df_eq[~df_eq['SYMBOL'].astype(str).str.contains(filter_keywords, case=False, na=False, regex=True)]
    
    # ३. SYMBOL च्या आधी "NSE:" लावणे
    df_eq['SYMBOL'] = 'NSE:' + df_eq['SYMBOL'].astype(str).str.strip()
    
    top_turnover = df_eq.sort_values(by='TURNOVER_LACS', ascending=False).head(250)
    top_volume = df_eq.sort_values(by='TTL_TRD_QNTY', ascending=False).head(250)
    unique_df = pd.concat([top_turnover, top_volume]).drop_duplicates(subset=['SYMBOL'])

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_json = json.loads(os.environ.get('GCP_CREDENTIALS'))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    client = gspread.authorize(creds)
    
    sheet_id = os.environ.get('SHEET_ID')
    spreadsheet = client.open_by_key(sheet_id)
    
    def update_sheet(worksheet_name, data_df):
        try:
            worksheet = spreadsheet.worksheet(worksheet_name)
            worksheet.clear()
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows="1000", cols="20")
        data_df = data_df.fillna('')
        worksheet.update([data_df.columns.values.tolist()] + data_df.values.tolist())
        print(f"Updated: {worksheet_name}")
        
    update_sheet("Top 250 Turnover", top_turnover)
    update_sheet("Top 250 Volume", top_volume)
    update_sheet("Final Unique List", unique_df)
    print("Done!")

if __name__ == "__main__":
    main()
