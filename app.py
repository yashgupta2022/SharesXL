from flask import Flask, request,  Response
import pandas as pd
import io

app = Flask(__name__)
class Item :
    def __init__(self, name, date, trade, qty ,amt ) :
        self.name = name
        self.date = date
        self.trade = trade
        self.qty = qty
        self.amt = amt
    def print(self):
        print(self.name, self.date, self.trade, self.qty, self.amt)

class FinalItem:
    def __init__(self, name, qty, buy_date, buy_price, sell_date, sell_price):
        self.name = name
        self.qty = qty
        self.buy_date = buy_date
        self.buy_price = buy_price
        self.sell_date = sell_date
        self.sell_price = sell_price

def read_new_shares(file_name):
    df = pd.read_csv(file_name)
    df.drop([ 'isin',  'exchange', 'segment', 'series',  'auction',  'trade_id', 'order_id', 'order_execution_time'] , axis=1, inplace=True)
    df.rename(columns={'symbol': "NAME", 'trade_date': "DATE",  'trade_type': "TRADE", 'quantity': "QTY", 'price': "AMT"} , inplace=True)
    df['QTY'] = df['QTY'].astype(int)
    df['DATE'] = pd.to_datetime(df['DATE'], format='%d-%m-%Y')
    return df

def add_custom_entries(): #FOR IPO, BONUS, SPLIT, BUYBACK
    entries =  []
    return entries

def merge_new_entries(df):
    data = []
    for i in range(len(df)):
        if i==0:
            data.append(Item(df.iloc[i]['NAME'], df.iloc[i]['DATE'], df.iloc[i]['TRADE'], df.iloc[i]['QTY'], df.iloc[i]['AMT']))
        else:
            if df.iloc[i]['NAME'] == data[-1].name and df.iloc[i]['DATE'] == data[-1].date and df.iloc[i]['TRADE'] == data[-1].trade:
                data[-1].amt = ((((df.iloc[i]['AMT']*df.iloc[i]['QTY'] )  + (data[-1].amt * data[-1].qty)) / (df.iloc[i]['QTY'] + data[-1].qty) ).round(2))
                data[-1].qty += df.iloc[i]['QTY']
            else:
                data.append(Item(df.iloc[i]['NAME'], df.iloc[i]['DATE'], df.iloc[i]['TRADE'], df.iloc[i]['QTY'], df.iloc[i]['AMT']))
        #custom_entries = add_custom_entries();
        #for entry in custom_entries:
        #    data.append(Item(entry['Name'], entry['Date'], entry['Trade'], entry['Quantity'], entry['Amount']))
    
    return data

def process_old_shares(file_name ):
    df_old = pd.read_excel(file_name,sheet_name='Shares',  usecols="A:L")
    # drop rows if s.no is nan
    df_old = df_old.dropna(subset =['QTY'])
    for col in ['BUY DATE', 'SELL DATE']:
        df_old[col] = pd.to_datetime(df_old[col] , format = '%d-%m-%Y')
    df_old['QTY'] = df_old['QTY'].astype(int)
    df_complete = df_old[ df_old['SELL AMT'].isnull()==False]
    df_complete.reset_index(drop=True, inplace=True)
    df_unsold = df_old[df_old['SELL AMT'].isnull()]
    # ignore index
    df_unsold.reset_index(drop=True, inplace=True)
    df_unsold = df_unsold.drop(['BUY AMT', 'SELL DATE', 'SELL PRICE', 'SELL AMT', 'TYPE' ,	'GROSS P/L',	 'CHARGES' ,	 'NET P&L' ], axis=1)
    df_unsold['Trade'] = "buy"
    df_unsold.rename(columns={'NAME': "Name", 'BUY PRICE': "Amount",  'QTY': "Quantity", 'BUY DATE': "Date"} , inplace=True)
    # rearrange columns     
    df_unsold = df_unsold[['Name', 'Date', 'Trade', 'Quantity', 'Amount']]
    return df_complete, df_unsold

def merge_unsold_with_new_entries(df_unsold, data):
    datacsv = {
    'Name': [item.name for item in data],
    'Date': [item.date for item in data],
    'Trade': [item.trade for item in data],
    'Quantity': [item.qty for item in data],
    'Amount': [item.amt for item in data], 
    }
    dfcsv = pd.DataFrame(datacsv)
    shares = pd.concat([df_unsold ,dfcsv] , ignore_index=True)
    shares['Date'] = pd.to_datetime(shares['Date'], format='%d-%m-%Y')
    shares= shares.sort_values(by=['Date', 'Trade','Amount'] ,ascending=True, ignore_index=True )
    return shares

def process_merged_entries(shares , dfcomplete ):
    data= []
    for i in range(len(shares)):
        data.append(Item(shares.iloc[i]['Name'], shares.iloc[i]['Date'], shares.iloc[i]['Trade'], shares.iloc[i]['Quantity'], shares.iloc[i]['Amount']))
    final = []
    for i in range(len(data)):
        if data[i].trade == "sell":
            while data[i].qty > 0:
                intraday=[]
                delivery=[]
                for j in range(i):
                    if data[j].trade == "buy" and data[j].name == data[i].name and data[j].qty > 0:
                        if data[j].date == data[i].date:
                            intraday.append(data[j])
                        else:
                            delivery.append(data[j])
                intraday.sort(key=lambda x: x.amt)
                delivery.sort(key=lambda x: x.amt)

                buy=None
                if (not buy) and len(intraday)>0 :
                    k=0
                    while  (k<len(intraday) and intraday[k].amt < data[i].amt) : #Check for buy price just less than sell price for intraday
                        buy = intraday[k]
                        k+=1
                if (not buy) and len(delivery)> 0 and  (delivery[0].amt < data[i].amt) : #Min buy price for delivery to make max profit
                            buy = delivery[0] 
                #if all buy prices are more than sell price then buy at first buy price
                if (not buy) and len(intraday)>0 : 
                    buy = intraday[0]  
                if (not buy) and len(delivery)>0 : 
                    buy = delivery[0]

                if  buy:     
                    if buy.qty <= data[i].qty:
                        data[i].qty -= buy.qty
                        final.append(FinalItem(data[i].name, buy.qty, buy.date, buy.amt, data[i].date, data[i].amt))
                        buy.qty = 0
                    else:                     
                        buy.qty -= data[i].qty
                        final.append(FinalItem(data[i].name, data[i].qty, buy.date, buy.amt, data[i].date, data[i].amt))
                        data[i].qty = 0
                else:
                    print("No buy found for sell", data[i].name, data[i].date, data[i].amt, data[i].qty)
                    break
                
    unsold = [i for i in range(len(data)) if data[i].qty > 0]
    unsold_datacsv = {
        'Name': [data[i].name for i in unsold],
        'Date': [data[i].date for i in unsold],
        'Trade': [data[i].trade for i in unsold],
        'Quantity': [data[i].qty for i in unsold],
        'Amount': [data[i].amt for i in unsold],
        'Total' : [data[i].amt * data[i].qty for i in unsold]
    }
    unsold_dfcsv = pd.DataFrame(unsold_datacsv)
    unsold_dfcsv.sort_values(by=['Name', 'Amount','Quantity'], inplace=True)
    unsold_dfcsv.loc[len(unsold_dfcsv)] = ['','','Total Qty', unsold_dfcsv['Quantity'].astype(float).sum(), 'Total Amt', unsold_dfcsv['Total'].astype(float).sum()]
    

    unsold_datacsv2 = {
        'BUY DATE' : [data[i].date for i in unsold],
        'NAME': [data[i].name for i in unsold],
        'QTY':[data[i].qty for i in unsold],
        'BUY PRICE': [data[i].amt for i in unsold],
        'BUY AMT' : [(data[i].amt * data[i].qty) for i in unsold],    
        'SELL DATE': [None for item in unsold],
        'SELL PRICE': [None for item in unsold],
        'SELL AMT'  : [None for item in unsold],
        'TYPE' : [None for item in unsold],
        'GROSS P/L' : [None for item in unsold],
        'CHARGES' : [getCharges(data[i],'unsold') for i in unsold],
        'NET P&L' : [getCharges(data[i] , 'unsold') for i in unsold]

    }
    unsold_dfcsv2 = pd.DataFrame(unsold_datacsv2)
    # Create DataFrame for final shares
    final_datacsv = {
        'BUY DATE' : [item.buy_date for item in final],
        'NAME': [item.name for item in final],
        'QTY': [item.qty for item in final],
        'BUY PRICE': [item.buy_price for item in final],
        'BUY AMT' : [item.buy_price * item.qty for item in final],
        'SELL DATE': [item.sell_date for item in final],
        'SELL PRICE': [item.sell_price for item in final],
        'SELL AMT': [item.sell_price * item.qty for item in final],
        'TYPE' : [getTradeType(item) for item in final],
        'GROSS P/L' : [((item.sell_price * item.qty)-(item.buy_price * item.qty)) for item in final],
        'CHARGES' : [getCharges(item , 'sold') for item in final],
        'NET P&L' : [(((item.sell_price * item.qty)-(item.buy_price * item.qty)) +getCharges(item ,'sold')) for item in final]
    }
    final_dfcsv = pd.DataFrame(final_datacsv)
    print(len(final_dfcsv), len(dfcomplete),len(unsold_dfcsv2) )
    finalshares =pd.concat([final_dfcsv,unsold_dfcsv2], ignore_index=True)
    for col in ['BUY DATE', 'SELL DATE']:
        finalshares[col] = pd.to_datetime(finalshares[col] , format='%d-%m-%Y')
    finalshares.sort_values(by=['BUY DATE','NAME'], inplace=True)
    finalshares =pd.concat([dfcomplete, finalshares], ignore_index=True)
    return unsold_dfcsv, finalshares

def getTradeType(item):
    if item.buy_date == item.sell_date:
        return "INTRADAY"
    else:
        return "DELIVERY"

def getCharges(item, type):
    return (
        type=='sold'
        and (
            -round(
                (
                    item.buy_date == item.sell_date
                    and (
                        round(
                            (
                                item.buy_date == item.sell_date
                                and (
                                    (
                                        0.0003 * ((item.buy_price * item.qty) + (item.sell_price * item.qty)) > 40
                                        and (40,)
                                        or (0.0003 * ((item.buy_price * item.qty) + (item.sell_price * item.qty)),)
                                    )[0],
                                )
                                or (0,)
                            )[0],
                            2,
                        )
                        + round(
                            (
                                item.buy_date == item.sell_date
                                and (0.00025 * (item.sell_price * item.qty),)
                                or (0.001 * ((item.buy_price * item.qty) + (item.sell_price * item.qty)),)
                            )[0],
                            0,
                        )
                        + round(0.0000345 * ((item.buy_price * item.qty) + (item.sell_price * item.qty)), 2)
                        + round(10 / 10000000 * ((item.buy_price * item.qty) + (item.sell_price * item.qty)) * 1.18, 2)
                        + round(
                            0.18
                            * (
                                round(
                                    (
                                        item.buy_date == item.sell_date
                                        and (
                                            (
                                                0.0003 * ((item.buy_price * item.qty) + (item.sell_price * item.qty)) > 40
                                                and (40,)
                                                or (0.0003 * ((item.buy_price * item.qty) + (item.sell_price * item.qty)),)
                                            )[0],
                                        )
                                        or (0,)
                                    )[0],
                                    2,
                                )
                                + round(0.0000345 * ((item.buy_price * item.qty) + (item.sell_price * item.qty)), 2)
                            ),
                            2,
                        )
                        + round(
                            (item.buy_date == item.sell_date and (0.00003 * (item.buy_price * item.qty),) or (0.00015 * (item.buy_price * item.qty),))[0], 0
                        ),
                    )
                    or (
                        15.93
                        + round(
                            (
                                item.buy_date == item.sell_date
                                and (
                                    (
                                        0.0003 * ((item.buy_price * item.qty) + (item.sell_price * item.qty)) > 40
                                        and (40,)
                                        or (0.0003 * ((item.buy_price * item.qty) + (item.sell_price * item.qty)),)
                                    )[0],
                                )
                                or (0,)
                            )[0],
                            2,
                        )
                        + round(
                            (
                                item.buy_date == item.sell_date
                                and (0.00025 * (item.sell_price * item.qty),)
                                or (0.001 * ((item.buy_price * item.qty) + (item.sell_price * item.qty)),)
                            )[0],
                            0,
                        )
                        + round(0.0000345 * ((item.buy_price * item.qty) + (item.sell_price * item.qty)), 2)
                        + round(10 / 10000000 * ((item.buy_price * item.qty) + (item.sell_price * item.qty)) * 1.18, 2)
                        + round(
                            0.18
                            * (
                                round(
                                    (
                                        item.buy_date == item.sell_date
                                        and (
                                            (
                                                0.0003 * ((item.buy_price * item.qty) + (item.sell_price * item.qty)) > 40
                                                and (40,)
                                                or (0.0003 * ((item.buy_price * item.qty) + (item.sell_price * item.qty)),)
                                            )[0],
                                        )
                                        or (0,)
                                    )[0],
                                    2,
                                )
                                + round(0.0000345 * ((item.buy_price * item.qty) + (item.sell_price * item.qty)), 2)
                            ),
                            2,
                        )
                        + round(
                            (item.buy_date == item.sell_date and (0.00003 * (item.buy_price * item.qty),) or (0.00015 * (item.buy_price * item.qty),))[0], 0
                        ),
                    )
                )[0],
                2,
            ),
        )
        or (
          (
            type=='unsold' and   (

                    -round(
                        round((0.001 * ((item.amt * item.qty))), 0)
                        + round(0.0000345 * ((item.amt * item.qty)) * 1.18, 2)
                        + round(10 / 10000000 * ((item.amt * item.qty)) * 1.18, 2)
                        + round((0.00015 * (item.amt * item.qty)), 2),
                        2,
                    ),
                )
                or ("",)
            )[0],
        )
    )[0]


def get_unique_names(finalshares):
    unique_values = finalshares['NAME'].unique()
    df_unique = pd.DataFrame(sorted(unique_values), columns=['NAME'])   
    return df_unique



def process_files(funds, file1, file2):
    df_new_shares = read_new_shares(file1)
    entries = merge_new_entries(df_new_shares)
    dfcomplete, df_unsold = process_old_shares(file2)
    merged_shares = merge_unsold_with_new_entries(df_unsold, entries)
    unsold_dfcsv, finalshares = process_merged_entries(merged_shares, dfcomplete)
    unique_names = get_unique_names(finalshares)
    buy_amt_sum = finalshares['BUY AMT'].astype(float).sum()
    sell_amt_sum = finalshares['SELL AMT'].astype(float).sum()
    gross_pl_sum = finalshares['GROSS P/L'].astype(float).sum()
    charges_sum = finalshares['CHARGES'].astype(float).sum()
    net_pl_sum = finalshares['NET P&L'].astype(float).sum()
    funds_rem = float(funds) + float(sell_amt_sum) - float(buy_amt_sum) + float(charges_sum)
    finalshares.loc[len(finalshares)] = ['','Funds Remaining', '', '','Total Buy' ,'','' , 'Total Sell', '' , 'Total Gross P/L', 'Total Charges', 'Total Net P/L']
    finalshares.loc[len(finalshares)] = ['',funds_rem, '', '', buy_amt_sum, '', '', sell_amt_sum, '',  gross_pl_sum, charges_sum, net_pl_sum]
    return finalshares, unsold_dfcsv, unique_names
    

app = Flask(__name__)

# Assuming all your processing functions are defined 

@app.route('/')
def upload_form():
    return '''
    <!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Upload Form</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f4f4f9;
            margin: 0;
            padding: 20px;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
        }

        .form-container {
            background-color: #ffffff;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
            width: 100%;
            max-width: 400px;
        }

        .form-container label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
        }

        .form-container input[type="number"],
        .form-container input[type="file"] {
            width: 95%;
            padding: 10px;
            margin-bottom: 15px;
            border: 1px solid #ccc;
            border-radius: 4px;
            cursor: pointer;
        }

        .form-container button {
            background-color: #007bff;
            color: white;
            padding: 10px 15px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            width: 100%;
            font-size: 16px;
        }

        .form-container button:hover {
            background-color: #0056b3;
            cursor: pointer;
        }

    </style>
</head>
<body>
    <div class="form-container">
        <form action="/upload" method="POST" enctype="multipart/form-data">
            <label for="funds">Enter Total Funds Added:</label>
            <input type="number" id="funds" name="funds" placeholder="Enter funds" required>

            <label for="file1">Upload New Shares (.csv):</label>
            <input type="file" id="file1" name="file1" accept=".csv" required>

            <label for="file2">Upload Existing Shares (.xlsx):</label>
            <input type="file" id="file2" name="file2" accept=".xlsx" required>

            <button type="submit">Merge</button>
        </form>
    </div>
</body>
</html>

    '''

@app.route('/upload', methods=['POST'])
def upload_files():
    funds = request.form['funds']
    file1 = request.files['file1']
    file2 = request.files['file2']
    
    final_buffer, unsold_buffer, unique_buffer = process_files(funds , file1, file2)
    
    excel_buffer = io.BytesIO()

    # Use pandas ExcelWriter to write multiple sheets
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        final_buffer.to_excel(writer, sheet_name='Shares', index=False)
        unsold_buffer.to_excel(writer, sheet_name='Unsold', index=False)
        unique_buffer.to_excel(writer, sheet_name='Unique', index=False)

    # Ensure the buffer's pointer is at the beginning after writing
    excel_buffer.seek(0)

    # Create a Response object to send the Excel file
    response = Response(excel_buffer.read())
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    response.headers['Content-Disposition'] = 'attachment; filename=download.xlsx'
    
    return response
   
if __name__ == '__main__':
    app.run(debug=True)