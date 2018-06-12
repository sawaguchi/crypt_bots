#!/usr/bin/python3
import configparser
import time
import ccxt
import sys
import json
import ast
import datetime

##### notes #####
# mexのAPI制限は、5分あたり300req
#################

inifile = configparser.ConfigParser()
inifile.read('./config.ini', 'UTF-8') # setting keys : mex_apiKey / mex_secret

bitmex = ccxt.bitmex({
    'apiKey': inifile.get('settings', 'mex_apiKey'),
    'secret': inifile.get('settings', 'mex_secret'),
})
#bitmex.urls['api'] = bitmex.urls['test']
bitmex.options['fetchTickerQuotes'] = False

def limit_order(side, price, size, is_reduceonly=False):
    params_dict = {
        'execInst': 'ParticipateDoNotInitiate',
    }
    if is_reduceonly :
        params_dict['execInst'] = 'ParticipateDoNotInitiate,ReduceOnly'
    return bitmex.create_order('BTC/USD', type='limit', side=side, price=price, amount=size, params=params_dict)

def market_order(side, size):
    return bitmex.create_order('BTC/USD', type='market', side=side, amount=size)

# 無条件でオーダーをキャンセル
def cancel_order(orders):
    for order in orders:
        order_ts = datetime.datetime.fromtimestamp(int(str(order['timestamp'])[:10]))
        res = bitmex.cancel_order(order['id'])
        res_info = res['info']
        print('cancel_order: ' + res_info['ordType'] + ' ' + res_info['side'] + ': ' + \
            str(res_info['orderQty']) + ' @ ' + str(res_info['price']) + ' / ' + res_info['orderID'])
    return 0 # 残order本数

# 一定時間以上経過したオーダーはキャンセル
def cancel_order_timeout(orders, timeout_sec):
    order_cnt = 0
    for order in orders:
        order_ts = datetime.datetime.fromtimestamp(int(str(order['timestamp'])[:10]))
        # order_ts = order_ts + datetime.timedelta(minutes=timeout_min)
        order_ts = order_ts + datetime.timedelta(seconds=timeout_sec)
        if order_ts < datetime.datetime.now() :
            res = bitmex.cancel_order(order['id'])
            res_info = res['info']
            print('cancel_order: ' + res_info['ordType'] + ' ' + res_info['side'] + ': ' + \
                str(res_info['orderQty']) + ' @ ' + str(res_info['price']) + ' / ' + res_info['orderID'])
        else :
            # 時間切れではないのでオーダーキャンセルしない
            order_cnt +=1
    return order_cnt # 残order本数


LOT = 500
CLOSE_RANGE = 20
STOP_RANGE = 20

### main routin
# last = bitmex.fetch_ticker('BTC/USD')['last']
# print('LTP: ' + str(last))

json_str = bitmex.fetchMarkets()
json_str = json.dumps(json_str)
json_dict = json.loads(str(json_str))

while True:
    # 1分以上経過しているオーダーはキャンセル
    orders = json.loads(json.dumps(bitmex.fetch_open_orders()))
    order_cnt = cancel_order_timeout(orders, 30) #sec
    # order_cnt = cancel_order(orders) #sec
    ### ここでオーダー数が減った場合用に、Function戻り値をordersにしたいかな。
    print ("check-01")
    positon = None
    while True:
        positon = bitmex.private_get_position()
        if len(positon) != 0  :
            break
        else :
            time.sleep(5)
            print ("RETRY:::bitmex.private_get_position()")

    last = bitmex.fetch_ticker('BTC/USD')['last']
    print ("check-04")
    # exec_qty = bitmex.private_get_position()[0]['currentQty'] # 保持position数量
    exec_qty = positon[0]['currentQty'] # 保持position数量
    if exec_qty < 0 :
        # ポジあり、ならポジ決済オーダー(利確or損切り)
        limit_order('buy', last - 0.5, LOT*2, True)
        limit_order('buy', last, LOT*2, True)
        print ("ポジ決済オーダー: limit_order('buy', last, LOT)" + str(last))
        print ("time.sleep(20)")
        time.sleep(20)
    elif exec_qty > 0 :
        # ポジあり、ならポジ決済オーダー(利確or損切り)
        limit_order('sell', last + 0.5, LOT*2, True)
        limit_order('sell', last, LOT*2, True)
        print ("ポジ決済オーダー: limit_order('sell', last, LOT)" + str(last))
        print ("time.sleep(20)")
        time.sleep(20)
    else :
        if order_cnt == 0 :
            # ポジなし & オーダー0、なら新規オーダー
            ts = bitmex.fetch_ticker('BTC/USD')['timestamp']
            ts = ts - 12*300000 # 足取得本数*(300秒+000) ... 5分足を12本分
            before_price = bitmex.fetch_ohlcv('BTC/USD', timeframe='5m', since=ts)[0][4] # 足配列のうち最も古い足
            now_price = last
            if before_price < now_price :
                # limit_order('buy', last - 0.5, LOT)
                limit_order('buy', last, LOT)
                print ("新規オーダー: limit_order('buy', last, LOT)" + str(last - 0.5))
            else :
                # limit_order('sell', last + 0.5, LOT)
                limit_order('sell', last, LOT)
                print ("新規オーダー: limit_order('sell', last, LOT)" + str(last + 0.5))
        else :
            # ポジあり & オーダー0、ならスルー
            pass


    print ("time.sleep(10)")
    time.sleep(10)

