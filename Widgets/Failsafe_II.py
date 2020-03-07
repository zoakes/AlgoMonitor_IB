

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Mar  5 08:27:58 2020

@author: zoakes
"""
"""
IBHalt: Command-Line & Spyder Program
Program Version 2.0.1
By: Zach Oakes


Revision Notes:
1.0.0 (03/05/2020) - Initial
1.0.1 (03/05/2020) - Refactored, Added Recursive Cls Var, bm @ 4us
2.0.1 (03/05/2020) - Begin Chg to MONITORING program

"""

from ib_insync import *
import numpy as np
import pytz
import calendar
import datetime
import logging
import sys
import time

USING_NOTEBOOK = True

#GLOBAL INPUTS 

SL = 50
PT = 10



# Set timezone for your TWS setup
TWS_TIMEZONE = pytz.timezone('US/Central')  

class Failsafe:
    Recursive = False
    
    def __init__(self,ip='127.0.0.1',port=7497,tid=99):
        self.ip = ip
        self.port = port
        self.id = tid
        
        # logging levels: CRITICAL, ERROR, WARNING, INFO, DEBUG, NOTSET
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.handler = logging.FileHandler('IBFailsafe.log')
        self.handler.setLevel(logging.INFO)
        self.formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.handler.setFormatter(self.formatter)
        self.logger.addHandler(self.handler)
        self.logger.info('Starting log at {}'.format(datetime.datetime.now()))
        #HALT = self.close_open_orders()
        self.instruments = []
        
        #METRIC dicts!
        self.agg_PNL = 0
        self.open_PNL = 0
        self.open_ids = []
        self.open_PNLs = []
        self.max_OPNL = 0
        self.max_RPL = 0
        self.RPLs = []
        self.largest_loss = 0
        self.max_DD = 0
        self.realized_equity = []
        self.low_pnl = {}
        self.trade_list = [] #1 for win, 0 for loss 
        
        
        # Create IB connection
        self.ib = self.connect()
 
###############################################################################
    
    def run(self):
        #Get trading hours -- exchange (Just filled in for now)
        EOD = datetime.time(hour=15) 
        BOD = datetime.time(hour=8,minute=30)
        
        now = datetime.datetime.now().time()
        while True:
            #if BOD <= now <= EOD: mkt hours
            if now < BOD:
                self.log('Waiting for market hours')
                break
        
        while True:
            try:
                #self.log('Halt program running -- Ready to halt')
                now = datetime.datetime.now().time()
                
                if now >= EOD:
                    self.log('Closing Failsafe for day')
                    break
                
                open_insts = [pos.contract for pos in self.ib.positions()]
                #Check PNL                                                      (SHOULD be looping through POSITIONS)
                for instrument in open_insts:
                    opl = self.get_open_pnl(instrument)
                    if opl < self.low_pnl[instrument]:
                        self.low_pnl[instrument] = opl
                        
                        if self.low_pnl[instrument] < self.largest_loss:
                            self.largest_loss = self.low_pnl[instrument]
                            self.log(f'Largest Loss -- {self.largest_loss} : {instrument.symbol}')
                            
                        #Check if at/below stop -- (losing trade)              ? Unsure how to do, need to confirm its no longer in positions()...
                        if self.low_pnl[instrument] <= -1*(abs(SL)) and instrument not in open_insts:
                            #Need to append ONCE -- not each time it's at SL or PT  *****
                            self.trade_list.append(0)
                            self.log('Loss Added -- {instrument.symbol}')
                         
                    #This needs to add DIFFERENCE **** THIS IS WRONG (maybe use list, and subtract difference from elements?)
                    #self.agg_PNL += opl
                    #self.log(f'Agg PNL -- {self.agg_PNL}')
                
                #Unrealized PNL -- open_PNL
                #Check for new open orders -- request singlepnl  for them if so
                account = set([pos.account for pos in self.ib.positions()])
                
                temp_ids = set([pos.contract.conId for pos in self.ib.positions()])
                past_ids = self.open_ids
                self.open_ids = temp_ids
                
                new_ids = np.setdiff1d(temp_ids,past_ids) #IN array1 (open) NOT in array2 
                self.open_PNL = 0 #Reset
                for nid in new_ids:
                    single_pnl = self.ib.reqPnlSingle(account, conId=nid)
                    self.open_PNL += single_pnl
                self.log(f'Open PNL -- {self.max_PNL}')

                #Drawdown? -- NEEDS PNLS AS A LIST -- check largest difference -- rolling max - min of x elements
                if self.open_PNL > self.max_OPNL:
                    self.max_OPNL = self.open_PNL
                    self.log(f'MAX OPEN PNL -- {self.max_OPNL}')

                #Aggregate PNL (Realized)
                agg_pnl = self.ib.reqPnL(account, modelCode='') #This is a STREAM -- just call ONCE!!
                if agg_pnl != self.agg_PNL:
                    self.agg_PNL = agg_pnl
                    #self.RPLs.insert(0,self.agg_PNL) #deque faster -- pushfront?
                    self.RPLs.append(self.agg_PNL)
                    self.log(f'Realized PNL -- {self.RPLs[-1]}')
                    
                #MAX DD
                ordered_pnl = self.RPLs[::-1]
                old_max = self.max_RPL
                self.max_RPL = max(ordered_pnl)
                if self.max_RPL != old_max:
                    self.log(f'Max Realized PNL -- {self.max_RPL}')
                    
                win = len(ordered_pnl)
                rolling_max = ordered_pnl.rolling(window=win).max()
                rolling_min = ordered_pnl.rolling(window=win).min()
                max_dd = (rolling_max - rolling_min)/rolling_max
                if max_dd < self.max_DD:
                    self.max_DD = max_dd
                    self.log(f'Max Drawdown -- {self.max_dd}')
                
                    
                    #Request full pnl --
                
                #Check Win Rate (Better internal?)
                wins = sum(self.trade_list)
                trades = len(self.trade_list)
                self.log(f'Win Rate -- {wins/trades}')
                
                

                    
                
                #Check avg W / Avg L OR Avg Trade?
                
            
            except (KeyboardInterrupt, SystemExit):
                self.log("Caught expected exception, CTRL-C, aborting")
                raise
                
            except:
                # Log exception info
                self.log("Caught unexpected exception in trading loop.")
                self.log(sys.exc_info()[0])
                
                # Try to disconnect
                if self.ib is not None:
                    self.ib.disconnect()
                    self.ib = None
                    
                # Create new IB connection
                self.ib = self.connect()
                
        self.log('Failsafe no longer running')
  
###############################################################################
    '''straihgt out of modular '''
    '''
    def run(self):
        """Run logic for live trading"""
        # Get today's trading hours
        self.get_trading_hours()

        # Wait until the markets open
        open_hr = int(self.exchange_open[:2])
        open_min = int(self.exchange_open[-2:])
        self.log('Waiting until the market opens ({}:{} ET)...'.format(
            open_hr, open_min))
        while True:
            now = datetime.datetime.now(tz=pytz.timezone('US/Eastern'))
            if ((now.minute >= open_min) and (now.hour >= open_hr)) or \
               (now.hour >= open_hr+1):
                break

            # Sleep 5 seconds
            self.ib.sleep(5)

        # Exchange is now open
        self.log()
        self.log('The market is now open {}'.format(now))
        self.start_time = time.time()

        # Set time reference 9:30AM ET for today / 13:30 UTC time
        # Used for determining when new bars are available
        self.time_ref = calendar.timegm(time.strptime(
                now.strftime('%Y-%m-%d') + ' 13:30:00', '%Y-%m-%d %H:%M:%S'))

        # Run loop during exhange hours
        while True:
            # Get the time delta from the time reference
            time_since_open = time.time() - self.time_ref

            # Check for new intraday bars
            if len(self.bars_minutes)>0:
                for minutes in self.bars_minutes:
                    if 60*minutes-(time_since_open%(60*minutes)) <= 5:
                        # Time to update 'minutes' bar for all instruments
                        if minutes == 1:
                            bar = '1 min'
                        elif minutes < 60:
                            bar = str(minutes) + ' mins'
                        elif minutes == 60:
                            bar = '1 hour'
                        else:
                            hours =  minutes/60
                            bar = str(hours) + ' hours'
                        # Loop through all instruments and update bar dfs
                        for instrument in self.instruments:
                            # Get current df for instrument/bar
                            df = self.dfs[instrument][bar]
                            # Update instrument/bar df
                            df = self.update_bar(df, instrument, bar)
                            self.dfs[instrument][bar] = df
                            self.log("Updated {}'s {} df".format(
                                    instrument.symbol, bar))
                        # Process signals (new bar)
                        self.on_data()

            # Perform other checks once per minute (60s)
            if True:                                                            #5-(time_since_open%5) <= 5: #CONFIRM THIS IS CORRECT
                # Loop through instruments                                      #if 60-(time_since_open%60) <= 5: (check every minute, 5s margin of error)
                for instrument in self.instruments:                             #Replaced with Constant check.
                    # Get current qty
                    qty = self.get_quantity(instrument)
                    # Check for trailing exit signal
                    if qty != 0:
                        if self.trailing_exit_signal(instrument, qty):
                            # Go flat
                            self.go_flat(instrument)

            # Get current ET time
            now = datetime.datetime.now(tz=pytz.timezone('US/Eastern'))

            # Get number of minutes until the market close
            close_str = now.strftime('%Y-%m-%d') + "T" \
                        + self.exchange_close[:2] \
                        + ":" + self.exchange_close[-2:] + ":00-04:00"
            close_time = datetime.datetime.strptime(
                ''.join(close_str.rsplit(':', 1)), '%Y-%m-%dT%H:%M:%S%z')
            min_to_close = int((close_time-now).seconds/60)

            #Exit for EOD!                                                      #ADDED EOD EXIT
            if min_to_close <= 30:
                if qty != 0:
                    self.go_flat(instrument)


            # Check for exchange closing time
            if min_to_close <= 0:
                log('The market is now closed: {}'.format(now))
                break

            # Sleep
            self.ib.sleep(5)

        self.log('Algo no longer running for the day.')      
        '''
        
###############################################################################
        
    def get_quantity(self,instrument):
        '''Get current quantity for instrument'''
        if str(type(instrument))[-7:-2] == 'Stock':
            instrument_type = 'Stock'
        else:
            raise ValueError(f'Invalid Instrument type {type(instrument)} for get_qty')
        
        for position in self.ib.positions():
            #Verify position for instrument
            contract = position.contract
            if instrument_type == 'Stock':
                try:
                    if contract.secType == 'STK' and \
                        contract.localSymbol == instrument.symbol:
                        return int(position.position)
                except:
                    continue
        #Else return flat
        return 0
    
###############################################################################

    def get_cost_basis(self,instrument):
        '''Returns avg fill price for instruments position'''
        for position in self.ib.positions():
            contract = position.contract
            try:
                if contract.secType == 'STK' and \
                    contract.localSymbol == instrument.symbols:
                    return float(position.avgCost)
            except:
                continue
        return 0
    
###############################################################################

#May need add_instrument ? (should be able to simply loop through positions?)
        
    def add_instruments(self,ticker_list):
        for ticker in ticker_list:
            try:
                instrument = Stock(ticker,'SMART','USD',primary_exchange='NASDAQ')
                
            except:
                self.log(f'Error adding instrument {instrument} for ticker -- {ticker}')
            
            finally:
                #Qualify + Append to instrument list, (and create dict for dfs)
                self.ib.qualifyContracts(instrument)
                self.instruments.append(instrument)
                
                self.dfs[instrument] = {}
                
    
    def check_instruments(self):
        '''
        Check to make sure no missing symbols active
        May need to qualify? not sure.
        '''
        added = 0
        for order_symbol in self.ib.orders():
            if order_symbol.contract not in self.instruments:
                self.instruments.append(order_symbol.contract)
                self.log(f'Added {order_symbol.contract} to instruments')
                added += 1
        
        for pos_symbol in self.ib.positions():
            if pos_symbol.contract not in self.instruments:
                self.instruments.append(pos_symbol.contract)
                self.log(f'Added {pos_symbol.contract} to instruments')
                added += 1
        return added
        
                
                
            
###############################################################################
        
    
    def get_price(self,instrument):
        
        ticker = self.ib.reqMktData(instrument,'',False,False)
        self.ib.sleep(.5)
        for i in range(10):
            self.ib.sleep(.2)
            if ticker.bid is not None and ticker.ask is not None:
                bid = float(ticker.bid)
                ask = float(ticker.ask)
                break
        #Check for valid bid/ask
        try:
            mid = round((bid+ask)/2,2)
        except:
            self.log(f'Error getting current mid price for {instrument.symbol}')
            return None,None,None
        
        return bid,ask,mid
            
###############################################################################
        
    def get_open_pnl(self,instrument):
        _, _, mid = self.get_price(instrument)
        basis = self.get_cost_basis(instrument)
        qty = self.get_quantity(instrument)
        if mid is None:
            return -1
        
        if qty != 0:
            profit = (mid-cost_basis)*qty
            return profit
        else:
            return -2
        

###############################################################################
        
    
    def connect(self):
        """Connect to Interactive Brokers TWS"""
        self.log('Connecting to Interactive Brokers TWS...')
        try:
            if USING_NOTEBOOK:
                util.startLoop()
            ib = IB()
            ib.connect(self.ip, self.port, clientId=self.id)
            self.log('Connected')
            self.log()
            return ib
        except:
            self.log('Error in connecting to TWS!! Exiting...')
            self.log(sys.exc_info()[0])
            #exit(-1)
            
            
###############################################################################
    def close_open_orders(self):
        """
        Cancels pending orders + Closes open positions
        Returns True or False.
        
        IF RECURSIVE is TRUE:
            runs recursively until 'dead' is True
        """
        # Verify open orders match open trades
        for i in range(1):
            open_trades = list(self.ib.openTrades())
            #trade_ids = set([t.order.orderId for t in open_trades])
            open_orders = list(self.ib.reqOpenOrders())
            #order_ids = set([o.orderId for o in open_orders])
            missing = order_ids.difference(trade_ids)
            if len(missing) == 0 and len(open_trades) > 0:
                #break
                self.log('Open orders present')
        
        #Cancel any open / pending orders-- 
        if len(open_orders) > 0: 
            self.log(f'Cancelling orders -- Global -- {open_orders}')
        self.ib.reqGlobalCancel() 
        #Cancel regardless ** (See bug in ib_insync--groups.io) **
            
            
        open_positions = self.ib.positions() #May need to be cast into list?
        for op in open_positions:
            contract = Stock(op.contract.symbol,"SMART","USD")
            qty = op.position
            self.log(f'Closing Trade -- {op.contract.symbol} : {qty}')
            
            if qty < 0:
                order = MarketOrder('BUY',abs(qty))
                
            if qty > 0:
                order = MarketOrder('SELL',abs(qty))
                
            self.ib.placeOrder(contract,order)
            self.log(f'Market Flat Order Sent -- {op.contract.symbol}')
                
                
        dead = len(open_trades) == 0 and len(open_orders) == 0 and len(open_positions) == 0 #check ALL just in case.
        if dead:
            self.log('Failsafe Success')
            return True
        
        if Recursive:
            self.log(f'Error -- Recursing')
            self.close_open_orders()
            
        return False

        
 ###############################################################################
    def log(self, msg=""):
        """Add log to output file"""
        self.logger.info(msg)
        print(msg)       





if __name__ == "__main__":
    #ibf = Failsafe() #To connect
    #ibf.Recursive = False
    
    #HALT = ibf.close_open_orders #To halt -- enter HALT()
    #HALT()
    
    print(0)
    ibf = Failsafe()
    #ibf.add_instruments('AAPL')
    ibf.check_instruments()
    

    
    
        