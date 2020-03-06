

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Mar  5 08:27:58 2020

@author: zoakes
"""

"""
IBHalt: Command-Line & Spyder Program
Program Version 1.0.1
By: Zach Oakes


Revision Notes:
1.0.0 (03/05/2020) - Initial
1.0.1 (03/05/2020) - Refactored, Added Recursive Cls Var, bm @ 4us


"""

from ib_insync import *
import pytz
import calendar
import datetime
import logging
import sys
import time

USING_NOTEBOOK = True



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
        
        #HALT = self.close_open_orders
        # Create IB connection
        
        self.ib = self.connect()
        

        

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
        # Verify open orders match open trades, find Open Orders
        for i in range(1):
            open_trades = list(self.ib.openTrades())
            trade_ids = set([t.order.orderId for t in open_trades])
            open_orders = list(self.ib.reqOpenOrders())
            order_ids = set([o.orderId for o in open_orders])
            missing = order_ids.difference(trade_ids)
            if len(missing) == 0 and len(open_trades) > 0:
                #break
                self.log('Open orders present')
        
        #Cancel any open / pending orders-- 
        if len(open_orders) > 0: 
            self.log(f'Cancelling orders -- Global -- {open_orders}')
        self.ib.reqGlobalCancel() 
        #Cancel regardless ** (See bug in ib_insync--groups.io) **
            
            
        open_positions = self.ib.positions()
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
                
        #check ALL just in case.      
        dead = len(open_trades) == 0 and len(open_orders) == 0 and len(open_positions) == 0 
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
    
    ibf = Failsafe(ip='127.0.0.1',port=7497,tid=99) #use DIFFERENT TID than strategy/data!
    #ibf.Recursive = True #To switch Recursive flag

    HALT = ibf.close_open_orders #To halt -- enter HALT() in spyder 'In []' input ->
    
    #HALT() #Uncomment to run from command line 
    # (or exit all immediately)
    
    '''
    -- To run via command prompt -- 
    - Uncomment HALT()
    - set USING_NOTEBOOK = False
    Anaconda Prompt -> change dir to program location -> python <filename.py> 
    '''
    

    
    
        