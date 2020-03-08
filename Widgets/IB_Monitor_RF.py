

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
        self.largest_loss_r = 0
        self.max_DD = 0
        self.realized_equity = []
        self.low_pnl = {}
        self.trade_list = [] #1 for win, 0 for loss 
        self.consec_loss = 0
        self.consec_wins = 0
        
        self.single_PNLs = {}
        self.ids_set = set([])
        self.win_rate = 0
        
        self.avg_w = 0
        self.avg_l = 0
        self.avg_t = 0
        
        self.win_loss = 0
        
        
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
                        '''Alternate Method of Largest Loss -- incl instrument '''
                        if self.low_pnl[instrument] < self.largest_loss:
                            self.largest_loss = self.low_pnl[instrument]
                            #self.log(f'Largest Single Loss -- {self.largest_loss} : {instrument.symbol}')
                
                #Unrealized PNL -- open_PNL
                #Check for new open orders -- request singlepnl  for them if so
                account = set([pos.account for pos in self.ib.positions()])
                
                temp_ids = set([pos.contract.conId for pos in self.ib.positions()])
                past_ids = self.open_ids
                add_ids = [self.ids_set.add(i) for i in temp_ids]               #Save ALL ids for later ?
                self.open_ids = temp_ids
                
                new_ids = np.setdiff1d(temp_ids,past_ids)                       #IN array1 (open) NOT in array2 (past open)
                
                #Check Open PNL + Largest Loss  (& add to global dict)
                self.get_open_PNL(account,new_ids)

                
                #Track Wins & Losses in self.trade_list (0 = loss, 1 = win)
                closed_ids = np.setdiff1d(past_ids,self.open_ids)               #IN past ids, NOT in Open (Recently Closed)
                
                self.track_wins_losses(account,closed_ids)

                #Track Aggregate Open Max Profit & Loss
                self.get_agg_unrealized()


                #Aggregate PNL (Realized)
                self.get_agg_realized()
                
                ordered_pnl = self.RPLs[::-1]
                
                
                #MAX Realized Equity
                self.get_max_equity()
                

                    
                #Max DD
                #window = len(self.RPLs) Used as default.
                self.get_max_dd()

                    
                #Largest REALIZED loss  
                largest_loss = min(np.diff(ordered_pnl,prepend=0))
                #Report + Update if greater than previous
                if abs(largest_loss) > abs(self.largest_loss_r):
                    self.largest_loss_r = largest_loss
                    self.log(f'Largest Realized Loss -- {self.largest_loss_r}')
                
                    
                #Get Win Rate (Better internal?)
                wins, trades = sum(self.trade_list), len(self.trade_list)
                win_rate = round(wins/trades,4)
                #Update + Log if Changed
                if win_rate != self.win_rate:
                    self.win_rate = win_rate
                    self.log(f'Win Rate -- {wins/trades}')
                
                #Consecutive Wins
                self.consec_wins = self.consecutive_trades(loss_or_win='w')
                self.log(f'Consecutive Wins -- {self.consec_wins}')
                    
                #Consecutive Losses
                self.consec_loss = self.consecutive_trades(loss_or_win='l')
                self.log(f'Consecutive Losses -- {self.consec_loss}')
                
                #Average Win / Loss + Average Trade
                #self.get_average_trades()

                pnls = np.diff(self.RPLs) #Need to go backwards, for correct sign
                
                self.avg_t = round(np.mean(pnls),2)
                self.avg_w = np.mean([t for t in pnls if t >= 0]) #avoid divide by zero -- track as W
                self.avg_l = np.mean([t for t in pnls if t < 0])
                
                self.log(f'Average Trade -- {self.avg_t}')
                
                self.win_loss = round(self.avg_w / self.avg_l,2)
                
                self.log(f'Average Win / Loss -- {self.win_loss}')
                
                
                #SLOW this thing down -- Calm down on compute
                self.ib.sleep(10)
            
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
        
    def get_open_PNL(self,account,new_ids):
        '''
        Gets OPEN PNL -- (input of NEW ids)
        Stores ALL in global dict (w/ id keys)
        
        AND check largest loss !  (Could also loop through single_PNLs dict)
        '''
        self.open_PNL = 0 #Reset each time
        for nid in new_ids:
            single_pnl = self.ib.reqPnlSingle(account, conId=nid)
            self.single_PNLs[nid] = single_pnl                                 #TRACK THEM GLOBALLY
            if single_pnl < self.largest_loss:
                self.largest_loss = single_pnl
                self.log(f'Largest Loss -- {self.largest_loss}')
            self.open_PNL += single_pnl
        self.log(f'Open PNL -- {self.open_PNL}')
        
        return self.open_PNL
        
###############################################################################
        
    def track_wins_losses(self,account,closed_ids):
        '''
        Tracks Winning and Losing trades in self.trade_list
        0 = win
        1 = loss 
        appended to END
        '''
        for cid in closed_ids:
            last_pnl = self.ib.reqPnlSingle(account,conId=cid) #HOPE this works with PAST pnls?
            if last_pnl > 0:
                self.trade_list.append(1)
                self.log(f'Win Added -- {last_pnl}')
            elif last_pnl < -abs(SL):
                self.trade_list.append(0)
                self.log(f'Loss Added -- {last_pnl}')
                
        return self.trade_list

###############################################################################

    def get_agg_unrealized(self):
        '''
        (Cut this method ? Dont think I need)
        Track Aggregate Unrealized PNL --  Max Open Profit & Loss
        '''
        if self.open_PNL > self.max_OPNL:
            self.max_OPNL = self.open_PNL
            self.log(f'MAX Agg Open PNL -- {self.max_OPNL}')
                
        if self.open_PNL < self.largest_loss:
            self.largest_loss = self.open_PNL
            self.log(f'Max Agg Open Loss -- {self.largest_loss}')
            
        return self.max_OPNL
            
###############################################################################

    def get_agg_realized(self):
        '''
        Track Aggregate Realized PNL -- 
        self.RPLs has most recent at END of list!
        '''
        #This is a stream, just call ONCE --                                    **THIS MIGHT NEED TO BE TAKEN OUT OF FUNC
        if agg_pnl is None:
            agg_pnl = self.ib.reqPnL(account, modelCode='')                   
            
        #Log all Changes in PNL -- Track Globally for DD and Avgs
        if agg_pnl != self.agg_PNL:
            self.agg_PNL = agg_pnl
            #self.RPLs.insert(0,self.agg_PNL) #deque faster -- pushfront?
            self.RPLs.append(self.agg_PNL)
            self.log(f'Realized PNL -- {self.RPLs[-1]}')
            
        return self.RPLs
        
        
###############################################################################

    def get_max_equity(self):
        '''
        Order RPLs, pull max value 
        '''
        ordered_pnl = self.RPLs[::-1]
        old_max = self.max_RPL
        self.max_RPL = max(ordered_pnl)
        #If new value -- Log New value!
        if self.max_RPL != old_max:
            self.log(f'Max Realized Equity/PNL -- {self.max_RPL}')
            
        return self.max_RPL
        
###############################################################################

    def get_max_dd(self,window=None):
        '''
        Get Max Drawdown -- Window defaults to LIFE of strategy 
        (otherwise listed in # trades)
        '''
        #Default without self.RPLs as arg (was raising ValueError)
        if window is None:
            window = len(self.RPLs)
        #Sort Realized PNL's
        ordered_pnl = self.RPLs[::-1]
        
        #Get Rolling min and max 
        rolling_max = ordered_pnl.rolling(window).max()
        rolling_min = ordered_pnl.rolling(window).min()
        
        max_dd = (rolling_max - rolling_min)/rolling_max
        #If Lower than Global, Update global + Log Change!
        if max_dd < self.max_DD:
            self.max_DD = max_dd
            self.log(f'Max Drawdown -- {self.max_dd}')
            
        return self.max_dd

###############################################################################


    def consecutive_trades(self,loss_or_win):
        '''
        Get Max consecutive losses ('l') or wins ('w')
        '''
        #Consecutive Wins
        if loss_or_win == 'w':
            self.consec_wins = 0
            for t in self.trade_list[::-1]:
                if t != 0:
                    self.consec_wins += 1
                else:
                    break
                
            self.consec_wins -= 1                                               #consec means first doesn't count
            return self.consec_wins                                        
            
        if loss_or_win == 'l':
            self.consec_loss = 0
            for t in self.trade_list[::-1]:
                if t != 1:
                    self.consec_loss += 1
                else:
                    break
                
            self.consec_loss -= 1
            return self.consec_loss
    
###############################################################################

    def get_average_trades(self):
        '''
        Get Average Win, Loss & Trade
        '''
        pnls = np.diff(self.RPLs) #Need to go backwards, for correct sign
        
        self.avg_t = round(np.mean(pnls),2)
        self.avg_w = np.mean([t for t in pnls if t >= 0]) #avoid divide by zero -- track as W
        self.avg_l = np.mean([t for t in pnls if t < 0])
        
        self.log(f'Average Trade -- {self.avg_t}')
        
        self.win_loss = round(self.avg_w / self.avg_l,2)
        
        self.log(f'Average Win / Loss -- {self.win_loss}')
        
        return self.avg_w, self.avg_l, self.avg_t, self.win_loss
    

        
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
    

    
    
        