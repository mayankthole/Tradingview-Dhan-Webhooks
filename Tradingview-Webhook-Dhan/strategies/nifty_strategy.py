from Dhan_Tradehull import Tradehull
import time
import logging
import traceback
import pandas as pd
import os

# Import credentials
from credentials import client_code, token_id

# Set up logging
logger = logging.getLogger(__name__)


# Global cache for instrument data
_instrument_cache = None

def load_instrument_data():
    """
    Load instrument data from CSV and cache it
    """
    global _instrument_cache
    try:
        if _instrument_cache is None:
            csv_path = os.path.join(os.path.dirname(__file__), 'Dependencies', 'all_instrument 2025-05-15.csv')
            _instrument_cache = pd.read_csv(csv_path, low_memory=False)  # Added low_memory=False to handle mixed types
            logger.info(f"Loaded {len(_instrument_cache)} instruments from CSV")
            logger.info(f"CSV columns: {_instrument_cache.columns.tolist()}")
        return _instrument_cache
    except Exception as e:
        logger.error(f"Error loading instrument data: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def get_instrument_details(trading_symbol):
    """
    Get instrument details from the cached CSV data
    Returns: dict with instrument details or None if not found
    """
    try:
        # Load instrument data if not cached
        df = load_instrument_data()
        if df is None:
            return None
        
        # Log the available columns for debugging
        logger.info(f"Available columns in CSV: {df.columns.tolist()}")
        
        # Find the instrument using SEM_TRADING_SYMBOL
        instrument = df[df['SEM_TRADING_SYMBOL'] == trading_symbol]
        if instrument.empty:
            logger.error(f"Instrument {trading_symbol} not found in CSV")
            return None
            
        instrument = instrument.iloc[0]
        
        # Log the found instrument details
        logger.info(f"Found instrument details: {instrument.to_dict()}")
        
        return {
            'tradingsymbol': instrument['SEM_TRADING_SYMBOL'],
            'exchange': instrument['SEM_EXM_EXCH_ID'],
            'instrument_type': instrument['SEM_EXCH_INSTRUMENT_TYPE'],
            'expiry': instrument['SEM_EXPIRY_DATE'],
            'strike': instrument['SEM_STRIKE_PRICE'],
            'option_type': instrument['SEM_OPTION_TYPE']
        }
    except Exception as e:
        logger.error(f"Error getting instrument details: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def execute_ratio_backspread(option_type, ratio):
    """
    Execute ratio backspread strategy for both CALL and PUT options
    option_type: 'CALL' or 'PUT'
    ratio: tuple of (buy_ratio, sell_ratio) e.g., (12,6) for 12:6 ratio
    """
    try:
        buy_ratio, sell_ratio = ratio
        logger.info(f"Executing NIFTY ratio backspread strategy for {option_type} options ({buy_ratio}:{sell_ratio})")
        
        # Initialize Tradehull
        tsl = Tradehull(client_code, token_id)
        
        # Get ATM strike
        atm_strike = tsl.ATM_Strike_Selection(Underlying='NIFTY', Expiry=0)
        logger.info(f"Selected ATM strike: {atm_strike}")
        
        # Get ATM option price
        try:
            atm_option = tsl.get_option_price(
                Underlying='NIFTY',
                Strike=atm_strike,
                OptionType=option_type,
                Expiry=0
            )
            atm_price = float(atm_option['lastTradedPrice'])
            logger.info(f"ATM {option_type} price: {atm_price}")
        except Exception as e:
            logger.error(f"Error getting ATM option price: {str(e)}")
            atm_price = 100  # Default price if API fails
        
        # Get lot size
        try:
            CE_symbol_name, PE_symbol_name, strike_price = tsl.ATM_Strike_Selection(Underlying='NIFTY', Expiry=0)
            lot_size = tsl.get_lot_size(tradingsymbol=CE_symbol_name)
            logger.info(f"Lot size: {lot_size}")
        except Exception as e:
            logger.error(f"Error getting lot size: {str(e)}")
            lot_size = 75  # Default lot size if API fails
        
        # Find best ITM strike
        best_itm_strike = None
        best_itm_price = None
        min_strike_diff = float('inf')
        
        # Try different strikes to find the best ITM option
        for i in range(1, 5):  # Try up to 4 strikes away
            if option_type == 'CALL':
                itm_strike = atm_strike - (i * 50)  # For calls, ITM is below ATM
            else:
                itm_strike = atm_strike + (i * 50)  # For puts, ITM is above ATM
                
            try:
                itm_option = tsl.get_option_price(
                    Underlying='NIFTY',
                    Strike=itm_strike,
                    OptionType=option_type,
                    Expiry=0
                )
                itm_price = float(itm_option['lastTradedPrice'])
                
                # Calculate net position
                net_position = (buy_ratio * atm_price) - (sell_ratio * itm_price)
                
                # Log the attempt
                logger.info(f"Trying ITM strike {itm_strike}: Price={itm_price}, Net Position={net_position}")
                
                # Check if this strike gives us a good premium
                if net_position < 0:  # We want to receive premium
                    strike_diff = abs(itm_strike - atm_strike)
                    if strike_diff < min_strike_diff:
                        min_strike_diff = strike_diff
                        best_itm_strike = itm_strike
                        best_itm_price = itm_price
                        logger.info(f"Found better ITM strike: {itm_strike} with price {itm_price}")
            except Exception as e:
                logger.error(f"Error getting ITM option price for strike {itm_strike}: {str(e)}")
                continue
        
        # If no suitable ITM strike found, use a fallback
        if best_itm_strike is None:
            if option_type == 'CALL':
                best_itm_strike = atm_strike - 200  # 200 points below ATM for calls
            else:
                best_itm_strike = atm_strike + 200  # 200 points above ATM for puts
            try:
                itm_option = tsl.get_option_price(
                    Underlying='NIFTY',
                    Strike=best_itm_strike,
                    OptionType=option_type,
                    Expiry=0
                )
                best_itm_price = float(itm_option['lastTradedPrice'])
                logger.info(f"Using fallback ITM strike {best_itm_strike} with price {best_itm_price}")
            except Exception as e:
                logger.error(f"Error getting fallback ITM option price: {str(e)}")
                best_itm_price = atm_price * 1.5  # Fallback price if API fails
        
        # Place orders
        logger.info(f"Placing orders for {buy_ratio}:{sell_ratio} ratio backspread")
        
        # Place buy orders for ATM options
        buy_orders = []
        for _ in range(buy_ratio):
            try:
                order = tsl.place_slice_order(
                    symbol=f"NIFTY{atm_strike}{option_type[0]}",
                    quantity=lot_size,
                    order_type="MARKET",
                    side="BUY",
                    product_type="INTRADAY"
                )
                buy_orders.append(order)
                logger.info(f"Placed buy order for ATM {option_type} at strike {atm_strike}")
            except Exception as e:
                logger.error(f"Error placing buy order: {str(e)}")
        
        # Wait for buy orders to execute
        time.sleep(0.5)  # Changed from 1 to 0.5
        
        # Place sell orders for ITM options
        sell_orders = []
        for _ in range(sell_ratio):
            try:
                order = tsl.place_slice_order(
                    symbol=f"NIFTY{best_itm_strike}{option_type[0]}",
                    quantity=lot_size,
                    order_type="MARKET",
                    side="SELL",
                    product_type="INTRADAY"
                )
                sell_orders.append(order)
                logger.info(f"Placed sell order for ITM {option_type} at strike {best_itm_strike}")
            except Exception as e:
                logger.error(f"Error placing sell order: {str(e)}")
        
        # Wait for orders to execute
        time.sleep(1)  # Changed from 2 to 1
        
        # Verify order execution
        try:
            positions = tsl.get_positions()
            buy_positions = [p for p in positions if p['side'] == 'BUY' and p['symbol'].endswith(option_type[0])]
            sell_positions = [p for p in positions if p['side'] == 'SELL' and p['symbol'].endswith(option_type[0])]
            
            total_buy_qty = sum(int(p['quantity']) for p in buy_positions)
            total_sell_qty = sum(int(p['quantity']) for p in sell_positions)
            
            logger.info(f"Verifying positions - Buy: {total_buy_qty}, Sell: {total_sell_qty}")
            
            # Check if orders executed correctly
            if total_buy_qty != buy_ratio * lot_size or total_sell_qty != sell_ratio * lot_size:
                logger.error(f"Position mismatch detected! Expected {buy_ratio}:{sell_ratio}, Got {total_buy_qty/lot_size}:{total_sell_qty/lot_size}")
                logger.info("Closing all positions due to incomplete execution")
                close_nifty_all_positions()
                return {
                    "status": "error",
                    "message": "Strategy execution incomplete - positions closed",
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
            
            logger.info("All orders executed successfully!")
            
        except Exception as e:
            logger.error(f"Error verifying positions: {str(e)}")
            logger.info("Closing all positions due to verification error")
            close_nifty_all_positions()
            return {
                "status": "error",
                "message": "Position verification failed - positions closed",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        
        # Calculate risk profile
        max_risk = (buy_ratio * atm_price * lot_size) - (sell_ratio * best_itm_price * lot_size)
        if option_type == 'CALL':
            breakeven_above = atm_strike + (max_risk / (buy_ratio * lot_size))
            breakeven_below = best_itm_strike - (max_risk / (sell_ratio * lot_size))
        else:
            breakeven_above = best_itm_strike + (max_risk / (sell_ratio * lot_size))
            breakeven_below = atm_strike - (max_risk / (buy_ratio * lot_size))
        
        return {
            "status": "success",
            "strategy": f"{buy_ratio}:{sell_ratio} ratio backspread",
            "option_type": option_type,
            "atm_strike": atm_strike,
            "itm_strike": best_itm_strike,
            "max_risk": max_risk,
            "breakeven_above": breakeven_above,
            "breakeven_below": breakeven_below,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        logger.error(f"Error in execute_ratio_backspread: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            "status": "error",
            "message": str(e),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    """Execute the NIFTY ratio backspread strategy with PUT options (Buy 8 ATM, Sell 4 ITM)"""
    logger.info("Starting NIFTY ratio backspread strategy execution for PUT options (8:4)...")
    
    try:
        # Initialize Tradehull
        tsl = Tradehull(client_code, token_id)
        
        # Step 1: Get the ATM strike for NIFTY
        CE_symbol_name, PE_symbol_name, strike_price = tsl.ATM_Strike_Selection(Underlying='NIFTY', Expiry=0)
        logger.info(f"ATM Strike identified: {strike_price}, PE Symbol: {PE_symbol_name}")
        
        # Get ATM option price
        try:
            atm_price_data = tsl.get_ltp_data(names=[PE_symbol_name])
            atm_price = atm_price_data.get(PE_symbol_name, 0)
            logger.info(f"ATM option price: {atm_price}")
        except Exception as e:
            logger.error(f"Error getting ATM price: {str(e)}")
            logger.info("Continuing with default strategy...")
            atm_price = None
        
        # Use constant lot size
        CE_symbol_name, PE_symbol_name, strike_price = tsl.ATM_Strike_Selection(Underlying='NIFTY', Expiry=0)
        lot_size = tsl.get_lot_size(tradingsymbol=CE_symbol_name)
        logger.info(f"Lot size: {lot_size}")
        
        # Step 2: Find an ITM strike with a good premium
        found_itm_strike = False
        best_itm_strike = None
        best_itm_symbol = None
        best_itm_premium = 0
        smallest_net_difference = float('inf')
        
        # Extract expiry date from the ATM symbol
        expiry_components = PE_symbol_name.split(" ")
        if len(expiry_components) >= 3:
            expiry_str = " ".join(expiry_components[1:3])
            
            # Get all ITM strike prices in one batch
            strike_prices = get_batch_strike_prices(
                tsl=tsl,
                base_strike=strike_price,
                expiry_str=expiry_str,
                option_type='PUT',
                num_strikes=10,  # Check 10 strikes
                strike_step=50   # 50 point steps
            )
            
            # Calculate 8x ATM cost
            atm_cost_8x = 8 * atm_price
            
            # Check each ITM strike
            for strike, data in strike_prices.items():
                if strike <= strike_price:  # Skip OTM strikes for PUTS
                    continue
                    
                itm_price = data['price']
                net_difference = (4 * itm_price) - atm_cost_8x
                
                logger.info(f"Checking ITM PUT strike {strike}, price: {itm_price}, vs 8× ATM cost: {atm_cost_8x}, net: {net_difference:.2f}")
                
                # Update best strike if this one is better (closer to zero)
                if abs(net_difference) < abs(smallest_net_difference):
                    smallest_net_difference = net_difference
                    best_itm_strike = strike
                    best_itm_symbol = data['symbol']
                    best_itm_premium = itm_price
                    found_itm_strike = True
            
            if not found_itm_strike:
                logger.error("No suitable ITM strike found")
                return None
                
            logger.info(f"Selected ITM PUT strike to sell: {best_itm_strike}, Symbol: {best_itm_symbol}")
            
            # Calculate quantities
            atm_quantity = 8 * lot_size
            itm_quantity = 4 * lot_size
            
            # Place orders
            logger.info("FIRST STEP: Placing BUY orders for 8 ATM PUTs")
            atm_order = tsl.place_slice_order(
                tradingsymbol=PE_symbol_name,
                exchange='NFO', 
                quantity=atm_quantity,
                price=0,  # Market order
                trigger_price=0, 
                order_type='MARKET', 
                transaction_type='BUY', 
                trade_type='MIS',
                disclosed_quantity=0,
                after_market_order=False,
                validity='DAY',
                amo_time='OPEN'
            )
            
            logger.info(f"BUY order placed for ATM PUT {PE_symbol_name}, Order ID: {atm_order}")
            
            # Pause for 0.5 second
            logger.info("Pausing for 0.5 second...")
            time.sleep(0.5)
            
            logger.info("SECOND STEP: Placing SELL order for 4 ITM PUTs")
            itm_order = tsl.place_slice_order(
                tradingsymbol=best_itm_symbol,
                exchange='NFO', 
                quantity=itm_quantity,
                price=0,  # Market order
                trigger_price=0, 
                order_type='MARKET', 
                transaction_type='SELL', 
                trade_type='MIS',
                disclosed_quantity=0,
                after_market_order=False,
                validity='DAY',
                amo_time='OPEN'
            )
            
            logger.info(f"SELL order placed for ITM PUT {best_itm_symbol}, Order ID: {itm_order}")
            
            # Calculate net position
            net_position = (4 * best_itm_premium) - (8 * atm_price)
            
            # Calculate risk profile
            max_risk = net_position * lot_size
            breakeven_point = strike_price - (net_position / 8)  # For PUTS, breakeven is below strike
            
            return {
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                'strategy_type': 'Ratio Backspread - PUT (Buy 8 ATM, Sell 4 ITM)',
                'atm_strike': strike_price,
                'atm_symbol': PE_symbol_name,
                'atm_price': atm_price,
                'atm_buy_orderid': atm_order,
                'atm_quantity': atm_quantity,
                'itm_strike': best_itm_strike,
                'itm_symbol': best_itm_symbol,
                'itm_price': best_itm_premium,
                'itm_sell_orderid': itm_order,
                'itm_quantity': itm_quantity,
                'net_position': net_position,
                'order_sequence': 'BUY first, then SELL (with 0.5-second pause)',
                'risk_profile': {
                    'max_risk': max_risk,
                    'unlimited_profit': True,
                    'breakeven_point': breakeven_point
                }
            }
            
    except Exception as e:
        logger.error(f"Error in PUT-8 strategy execution: {str(e)}")
        return None


    """Execute the NIFTY ratio backspread strategy with CALL options (Buy 16 ATM, Sell 8 ITM)"""
    logger.info("Starting NIFTY ratio backspread strategy execution for CALL options (16:8)...")
    
    try:
        # Initialize Tradehull
        tsl = Tradehull(client_code, token_id)
        
        # Step 1: Get the ATM strike for NIFTY
        CE_symbol_name, PE_symbol_name, strike_price = tsl.ATM_Strike_Selection(Underlying='NIFTY', Expiry=0)
        logger.info(f"ATM Strike identified: {strike_price}, CE Symbol: {CE_symbol_name}")
        
        # Get ATM option price
        try:
            atm_price_data = tsl.get_ltp_data(names=[CE_symbol_name])
            atm_price = atm_price_data.get(CE_symbol_name, 0)
            logger.info(f"ATM option price: {atm_price}")
        except Exception as e:
            logger.error(f"Error getting ATM price: {str(e)}")
            logger.info("Continuing with default strategy...")
            atm_price = None
        
        # Use constant lot size
        CE_symbol_name, PE_symbol_name, strike_price = tsl.ATM_Strike_Selection(Underlying='NIFTY', Expiry=0)
        lot_size = tsl.get_lot_size(tradingsymbol=CE_symbol_name)
        logger.info(f"Lot size: {lot_size}")
        
        
        # Step 2: Find an ITM strike with a good premium
        found_itm_strike = False
        best_itm_strike = None
        best_itm_symbol = None
        best_itm_premium = 0
        smallest_net_difference = float('inf')
        
        # Extract expiry date from the ATM symbol
        expiry_components = CE_symbol_name.split(" ")
        if len(expiry_components) >= 3:
            expiry_str = " ".join(expiry_components[1:3])
            
            # Get all ITM strike prices in one batch
            strike_prices = get_batch_strike_prices(
                tsl=tsl,
                base_strike=strike_price,
                expiry_str=expiry_str,
                option_type='CALL',
                num_strikes=10,  # Check 10 strikes
                strike_step=50   # 50 point steps
            )
            
            # Calculate 16x ATM cost
            atm_cost_16x = 16 * atm_price
            
            # Check each ITM strike
            for strike, data in strike_prices.items():
                if strike >= strike_price:  # Skip OTM strikes for CALLS
                    continue
                    
                itm_price = data['price']
                net_difference = (8 * itm_price) - atm_cost_16x
                
                logger.info(f"Checking ITM CALL strike {strike}, price: {itm_price}, vs 16× ATM cost: {atm_cost_16x}, net: {net_difference:.2f}")
                
                # Update best strike if this one is better (closer to zero)
                if abs(net_difference) < abs(smallest_net_difference):
                    smallest_net_difference = net_difference
                    best_itm_strike = strike
                    best_itm_symbol = data['symbol']
                    best_itm_premium = itm_price
                    found_itm_strike = True
            
            if not found_itm_strike:
                logger.error("No suitable ITM strike found")
                return None
                
            logger.info(f"Selected ITM CALL strike to sell: {best_itm_strike}, Symbol: {best_itm_symbol}")
            
            # Calculate quantities
            atm_quantity = 16 * lot_size
            itm_quantity = 8 * lot_size
            
            # Place orders
            logger.info("FIRST STEP: Placing BUY orders for 16 ATM CALLs")
            atm_order = tsl.place_slice_order(
                tradingsymbol=CE_symbol_name,
                exchange='NFO', 
                quantity=atm_quantity,
                price=0,  # Market order
                trigger_price=0, 
                order_type='MARKET', 
                transaction_type='BUY', 
                trade_type='MIS',
                disclosed_quantity=0,
                after_market_order=False,
                validity='DAY',
                amo_time='OPEN'
            )
            
            logger.info(f"BUY order placed for ATM CALL {CE_symbol_name}, Order ID: {atm_order}")
            
            # Pause for 0.5 second
            logger.info("Pausing for 0.5 second...")
            time.sleep(0.5)
            
            logger.info("SECOND STEP: Placing SELL order for 8 ITM CALLs")
            itm_order = tsl.place_slice_order(
                tradingsymbol=best_itm_symbol,
                exchange='NFO', 
                quantity=itm_quantity,
                price=0,  # Market order
                trigger_price=0, 
                order_type='MARKET', 
                transaction_type='SELL', 
                trade_type='MIS',
                disclosed_quantity=0,
                after_market_order=False,
                validity='DAY',
                amo_time='OPEN'
            )
            
            logger.info(f"SELL order placed for ITM CALL {best_itm_symbol}, Order ID: {itm_order}")
            
            # Calculate net position
            net_position = (8 * best_itm_premium) - (16 * atm_price)
            
            # Calculate risk profile
            max_risk = net_position * lot_size
            breakeven_point = strike_price + (net_position / 16)  # For CALLS, breakeven is above strike
            
            return {
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                'strategy_type': 'Ratio Backspread - CALL (Buy 16 ATM, Sell 8 ITM)',
                'atm_strike': strike_price,
                'atm_symbol': CE_symbol_name,
                'atm_price': atm_price,
                'atm_buy_orderid': atm_order,
                'atm_quantity': atm_quantity,
                'itm_strike': best_itm_strike,
                'itm_symbol': best_itm_symbol,
                'itm_price': best_itm_premium,
                'itm_sell_orderid': itm_order,
                'itm_quantity': itm_quantity,
                'net_position': net_position,
                'order_sequence': 'BUY first, then SELL (with 0.5-second pause)',
                'risk_profile': {
                    'max_risk': max_risk,
                    'unlimited_profit': True,
                    'breakeven_point': breakeven_point
                }
            }
            
    except Exception as e:
        logger.error(f"Error in CALL-16 strategy execution: {str(e)}")
        return None

def close_nifty_all_positions():
    """Close all NIFTY-related positions using market orders"""
    logger.info("Starting to close all NIFTY positions...")
    
    try:
        # Initialize Tradehull
        tsl = Tradehull(client_code, token_id)
        
        # Get current month expiry details
        ce_name, pe_name, strike = tsl.ATM_Strike_Selection(Underlying='NIFTY', Expiry=0)
        expiry_parts = ce_name.split()  # Format: "NIFTY DD MMM STRIKE CALL"
        current_expiry_day = expiry_parts[1]
        current_expiry_month = expiry_parts[2]
        
        logger.info(f"Current expiry: {current_expiry_day} {current_expiry_month}")
        
        # Get all positions
        positions = tsl.get_positions()
        logger.info(f"Found positions: {positions}")
        
        # Check if positions is None or empty
        if positions is None or (hasattr(positions, 'empty') and positions.empty):
            logger.info("No positions found to close")
            return {
                "status": "success",
                "message": "No positions found to close",
                "positions_closed": 0,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        
        # Count total positions and NIFTY positions
        total_positions = len(positions)
        nifty_positions = positions[positions['tradingSymbol'].str.startswith('NIFTY')]
        total_nifty_positions = len(nifty_positions)
        
        logger.info(f"Total positions found: {total_positions}")
        logger.info(f"Total NIFTY positions found: {total_nifty_positions}")
        
        # Log position details for debugging
        logger.info("\nPosition Details:")
        for _, pos in positions.iterrows():
            logger.info(f"Symbol: {pos['tradingSymbol']}, NetQty: {pos['netQty']}, PositionType: {pos['positionType']}")
        
        # Filter for active NIFTY positions only
        active_positions = positions[
            (positions['tradingSymbol'].str.startswith('NIFTY')) &  # Only NIFTY options
            (positions['netQty'].astype(float) != 0) &  # Non-zero quantity
            (positions['positionType'] != 'CLOSED')  # Not already closed
        ]
        
        logger.info(f"Active NIFTY positions found: {len(active_positions)}")
        
        if active_positions.empty:
            logger.info("No active NIFTY positions found to close")
            return {
                "status": "success",
                "message": "No active NIFTY positions found to close",
                "positions_closed": 0,
                "total_positions": total_positions,
                "total_nifty_positions": total_nifty_positions,
                "active_positions": len(active_positions),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        
        closed_positions = []
        positions_closed = 0
        
        # Process each active NIFTY position
        for _, position in active_positions.iterrows():
            try:
                # Get current quantity
                current_qty = abs(float(position['netQty']))
                
                logger.info(f"\nExiting position for {position['tradingSymbol']}:")
                logger.info(f"Product Type: {position['productType']}")
                logger.info(f"Position Type: {position['positionType']}")
                logger.info(f"Current Quantity: {current_qty}")
                
                # Map product type to trade type
                trade_type = "MIS" if position['productType'] == "INTRADAY" else position['productType']
                
                # Format the trading symbol for current month expiry
                if 'drvOptionType' in position and 'drvStrikePrice' in position:
                    # Get option type (CE/PE)
                    option_type = position['drvOptionType']
                    
                    # Get strike price
                    strike = str(int(position['drvStrikePrice']))
                    
                    # Create formatted symbol using current expiry
                    trading_symbol = f"NIFTY {current_expiry_day} {current_expiry_month} {strike} {option_type}"
                    logger.info(f"Formatted Trading Symbol: {trading_symbol}")
                else:
                    logger.error(f"Missing required position data for {position['tradingSymbol']}")
                    continue
                
                # Place market order to close position
                try:
                    # Determine transaction type based on position type
                    transaction_type = 'SELL' if position['positionType'] == 'LONG' else 'BUY'
                    
                    logger.info(f"Placing {transaction_type} order for {current_qty} quantity")
                    
                    # Always use place_slice_order - it will handle slicing automatically
                    order_ids = tsl.place_slice_order(
                        tradingsymbol=trading_symbol,
                        exchange='NFO',
                        transaction_type=transaction_type,
                        quantity=current_qty,
                        order_type='MARKET',
                        trade_type=trade_type,
                        price=0,
                        trigger_price=0,
                        after_market_order=False,
                        validity='DAY',
                        amo_time='OPEN'
                    )
                    logger.info(f"Orders placed successfully with IDs: {order_ids}")
                    if order_ids:
                        closed_positions.append({
                            'symbol': trading_symbol,
                            'quantity': current_qty,
                            'order_ids': order_ids if isinstance(order_ids, list) else [order_ids],
                            'transaction_type': transaction_type
                        })
                        positions_closed += 1
                except Exception as e:
                    logger.error(f"Error placing order: {str(e)}")
                    logger.error(f"Order details - Symbol: {trading_symbol}, Quantity: {current_qty}")
                    continue
            
                # Add a small delay between orders
                time.sleep(0.5)
            
            except Exception as e:
                logger.error(f"Error closing position for {position['tradingSymbol']}: {str(e)}", exc_info=True)
                continue
        
        logger.info(f"Successfully closed {positions_closed} NIFTY positions")
        
        return {
            "status": "success",
            "message": f"Closed {positions_closed} NIFTY positions",
            "closed_positions": closed_positions,
            "total_positions": total_positions,
            "total_nifty_positions": total_nifty_positions,
            "active_positions": len(active_positions),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
    except Exception as e:
        logger.error(f"Error in close_nifty_all_positions: {str(e)}")
        return {
            "status": "error",
            "message": f"Error closing positions: {str(e)}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

def close_nifty_half_positions():
    """Close half of all NIFTY-related positions using market orders"""
    logger.info("Starting to close half of all NIFTY positions...")
    
    try:
        # Initialize Tradehull
        tsl = Tradehull(client_code, token_id)



        # Get current month expiry details
        ce_name, pe_name, strike = tsl.ATM_Strike_Selection(Underlying='NIFTY', Expiry=0)
        expiry_parts = ce_name.split()  # Format: "NIFTY DD MMM STRIKE CALL"
        current_expiry_day = expiry_parts[1]
        current_expiry_month = expiry_parts[2]
        
        logger.info(f"Current expiry: {current_expiry_day} {current_expiry_month}")
        
        # Get all positions
        positions = tsl.get_positions()
        logger.info(f"Found positions: {positions}")
        
        # Check if positions is None or empty
        if positions is None or (hasattr(positions, 'empty') and positions.empty):
            logger.info("No positions found to close")
            return {
                "status": "success",
                "message": "No positions found to close",
                "positions_closed": 0,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        
        # Count total positions and NIFTY positions
        total_positions = len(positions)
        nifty_positions = positions[positions['tradingSymbol'].str.startswith('NIFTY')]
        total_nifty_positions = len(nifty_positions)
        
        logger.info(f"Total positions found: {total_positions}")
        logger.info(f"Total NIFTY positions found: {total_nifty_positions}")
        
        # Log position details for debugging
        logger.info("\nPosition Details:")
        for _, pos in positions.iterrows():
            logger.info(f"Symbol: {pos['tradingSymbol']}, NetQty: {pos['netQty']}, PositionType: {pos['positionType']}")
        
        # Filter for active NIFTY positions only
        active_positions = positions[
            (positions['tradingSymbol'].str.startswith('NIFTY')) &  # Only NIFTY options
            (positions['netQty'].astype(float) != 0) &  # Non-zero quantity
            (positions['positionType'] != 'CLOSED')  # Not already closed
        ]
        
        logger.info(f"Active NIFTY positions found: {len(active_positions)}")
        
        if active_positions.empty:
            logger.info("No active NIFTY positions found to close")
            return {
                "status": "success",
                "message": "No active NIFTY positions found to close",
                "positions_closed": 0,
                "total_positions": total_positions,
                "total_nifty_positions": total_nifty_positions,
                "active_positions": len(active_positions),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        
        closed_positions = []
        
        # Process each active NIFTY position
        for _, position in active_positions.iterrows():
            try:
                # Get current quantity
                current_qty = abs(float(position['netQty']))
                CE_symbol_name, PE_symbol_name, strike_price = tsl.ATM_Strike_Selection(Underlying='NIFTY', Expiry=0)
                lot_size = tsl.get_lot_size(tradingsymbol=CE_symbol_name)
                logger.info(f"Lot size: {lot_size}")
                
                # Calculate how many lots we have
                current_lots = current_qty // lot_size
                # Calculate half of the lots (rounded down)
                half_lots = current_lots // 2
                # If we have odd number of lots, round up to ensure we close at least half
                if current_lots % 2 != 0:
                    half_lots += 1
                
                # Convert back to quantity
                half_qty = half_lots * lot_size
                
                logger.info(f"\nProcessing position for {position['tradingSymbol']}:")
                logger.info(f"Product Type: {position['productType']}")
                logger.info(f"Position Type: {position['positionType']}")
                logger.info(f"Current Quantity: {current_qty}")
                logger.info(f"Current Lots: {current_lots}")
                logger.info(f"Half Lots: {half_lots}")
                logger.info(f"Exit Quantity: {half_qty}")
                
                # Map product type to trade type
                trade_type = "MIS" if position['productType'] == "INTRADAY" else position['productType']
                
                # Format the trading symbol for current month expiry
                if 'drvOptionType' in position and 'drvStrikePrice' in position:
                    # Get option type (CE/PE)
                    option_type = position['drvOptionType']
                    
                    # Get strike price
                    strike = str(int(position['drvStrikePrice']))
                    
                    # Create formatted symbol using current expiry
                    trading_symbol = f"NIFTY {current_expiry_day} {current_expiry_month} {strike} {option_type}"
                    logger.info(f"Formatted Trading Symbol: {trading_symbol}")
                else:
                    logger.error(f"Missing required position data for {position['tradingSymbol']}")
                    continue
                
                # Place market order to close half position
                try:
                    # Determine transaction type based on position type
                    transaction_type = 'SELL' if position['positionType'] == 'LONG' else 'BUY'
                    
                    logger.info(f"Placing {transaction_type} order for {half_qty} quantity")
                    
                    order_id = tsl.place_slice_order(
                        tradingsymbol=trading_symbol,
                        exchange='NFO',
                        quantity=half_qty,
                        price=0,
                        trigger_price=0, 
                        order_type='MARKET', 
                        transaction_type=transaction_type,
                        trade_type=trade_type,
                        disclosed_quantity=0,
                        after_market_order=False,
                        validity='DAY',
                        amo_time='OPEN'
                    )
                    logger.info(f"Order placed successfully with ID: {order_id}")
                    if order_id:
                        closed_positions.append({
                            'symbol': trading_symbol,
                            'quantity': half_qty,
                            'order_id': order_id,
                            'transaction_type': transaction_type
                        })
                except Exception as e:
                    logger.error(f"Error placing order: {str(e)}")
                    logger.error(f"Order details - Symbol: {trading_symbol}, Quantity: {half_qty}")
                    continue
            
                # Add a small delay between orders
                time.sleep(0.5)
            
            except Exception as e:
                logger.error(f"Error closing half position for {position['tradingSymbol']}: {str(e)}", exc_info=True)
                continue
        
        logger.info(f"Successfully closed half of {len(closed_positions)} positions")
            
        return {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "success",
            "message": f"Closed half of {len(closed_positions)} positions",
            "closed_positions": closed_positions,
            "total_positions": total_positions,
            "total_nifty_positions": total_nifty_positions,
            "active_positions": len(active_positions)
        }
            
    except Exception as e:
        logger.error(f"Error in close_nifty_half_positions: {str(e)}", exc_info=True)
        return {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "error",
            "message": f"Error closing half positions: {str(e)}"
        }

def get_batch_strike_prices(tsl, base_strike, expiry_str, option_type, num_strikes=10, strike_step=50):
    """
    Get prices for multiple strikes in one batch
    tsl: Tradehull instance
    base_strike: The ATM strike price
    expiry_str: Expiry date string (e.g., "15 MAY")
    option_type: 'CALL' or 'PUT'
    num_strikes: Number of strikes to check
    strike_step: Step size between strikes
    """
    try:
        strike_prices = {}
        
        # Generate strike prices to check
        if option_type == 'CALL':
            # For calls, check strikes below ATM
            strikes = [base_strike - (i * strike_step) for i in range(1, num_strikes + 1)]
        else:
            # For puts, check strikes above ATM
            strikes = [base_strike + (i * strike_step) for i in range(1, num_strikes + 1)]
        
        # Create symbols for all strikes
        symbols = []
        for strike in strikes:
            symbol = f"NIFTY {expiry_str} {strike} {option_type}"
            symbols.append(symbol)
        
        # Get prices for all symbols in one batch
        price_data = tsl.get_ltp_data(names=symbols)
        
        # Process the results
        for strike, symbol in zip(strikes, symbols):
            if symbol in price_data:
                strike_prices[strike] = {
                    'symbol': symbol,
                    'price': price_data[symbol]
                }
                logger.info(f"Got price for {symbol}: {price_data[symbol]}")
            else:
                logger.warning(f"No price data for {symbol}")
        
        # Log all available strikes and their prices
        logger.info("\nAvailable strikes and prices:")
        for strike, data in strike_prices.items():
            logger.info(f"Strike: {strike}, Price: {data['price']}, Symbol: {data['symbol']}")
        
        return strike_prices
        
    except Exception as e:
        logger.error(f"Error in get_batch_strike_prices: {str(e)}", exc_info=True)
        return {}

def execute_nifty_ratio_backspread_call_12():
    """Execute the NIFTY ratio backspread strategy with CALL options (Buy 12 ATM, Sell 6 ITM)"""
    logger.info("Starting NIFTY ratio backspread strategy execution for CALL options (12:6)...")
    
    try:
        # Initialize Tradehull
        tsl = Tradehull(client_code, token_id)
        
        # Step 1: Get the ATM strike for NIFTY
        CE_symbol_name, PE_symbol_name, strike_price = tsl.ATM_Strike_Selection(Underlying='NIFTY', Expiry=0)
        logger.info(f"ATM Strike identified: {strike_price}, CE Symbol: {CE_symbol_name}")
        
        # Get ATM option price
        try:
            atm_price_data = tsl.get_ltp_data(names=[CE_symbol_name])
            atm_price = atm_price_data.get(CE_symbol_name, 0)
            logger.info(f"ATM option price: {atm_price}")
        except Exception as e:
            logger.error(f"Error getting ATM price: {str(e)}")
            logger.info("Continuing with default strategy...")
            atm_price = None
        
        # Use constant lot size
        CE_symbol_name, PE_symbol_name, strike_price = tsl.ATM_Strike_Selection(Underlying='NIFTY', Expiry=0)
        lot_size = tsl.get_lot_size(tradingsymbol=CE_symbol_name)
        logger.info(f"Lot size: {lot_size}")
        
        
        # Step 2: Find an ITM strike with a good premium
        found_itm_strike = False
        best_itm_strike = None
        best_itm_symbol = None
        best_itm_premium = 0
        smallest_net_difference = float('inf')
        
        # Extract expiry date from the ATM symbol
        expiry_components = CE_symbol_name.split(" ")
        if len(expiry_components) >= 3:
            expiry_str = " ".join(expiry_components[1:3])
            
            # Get all ITM strike prices in one batch
            strike_prices = get_batch_strike_prices(
                tsl=tsl,
                base_strike=strike_price,
                expiry_str=expiry_str,
                option_type='CALL',
                num_strikes=10,  # Check 10 strikes
                strike_step=50   # 50 point steps
            )
            
            # Calculate 12x ATM cost
            atm_cost_12x = 12 * atm_price
            
            # Check each ITM strike
            for strike, data in strike_prices.items():
                if strike >= strike_price:  # Skip OTM strikes for CALLS
                    continue
                    
                itm_price = data['price']
                net_difference = (6 * itm_price) - atm_cost_12x
                
                logger.info(f"Checking ITM CALL strike {strike}, price: {itm_price}, vs 12× ATM cost: {atm_cost_12x}, net: {net_difference:.2f}")
                
                # Update best strike if this one is better (closer to zero)
                if abs(net_difference) < abs(smallest_net_difference):
                    smallest_net_difference = net_difference
                    best_itm_strike = strike
                    best_itm_symbol = data['symbol']
                    best_itm_premium = itm_price
                    found_itm_strike = True
            
            if not found_itm_strike:
                logger.error("No suitable ITM strike found")
                return None
                
            logger.info(f"Selected ITM CALL strike to sell: {best_itm_strike}, Symbol: {best_itm_symbol}")
            
            # Calculate quantities
            atm_quantity = 12 * lot_size
            itm_quantity = 6 * lot_size
            
            # Place orders
            logger.info("FIRST STEP: Placing BUY orders for 12 ATM CALLs")
            atm_order = tsl.place_slice_order(
                tradingsymbol=CE_symbol_name,
                exchange='NFO', 
                quantity=atm_quantity,
                price=0,  # Market order
                trigger_price=0, 
                order_type='MARKET', 
                transaction_type='BUY', 
                trade_type='MIS',
                disclosed_quantity=0,
                after_market_order=False,
                validity='DAY',
                amo_time='OPEN'
            )
            
            logger.info(f"BUY order placed for ATM CALL {CE_symbol_name}, Order ID: {atm_order}")
            
            # Pause for 0.5 second
            logger.info("Pausing for 0.5 second...")
            time.sleep(0.5)
            
            logger.info("SECOND STEP: Placing SELL order for 6 ITM CALLs")
            itm_order = tsl.place_slice_order(
                tradingsymbol=best_itm_symbol,
                exchange='NFO', 
                quantity=itm_quantity,
                price=0,  # Market order
                trigger_price=0, 
                order_type='MARKET', 
                transaction_type='SELL', 
                trade_type='MIS',
                disclosed_quantity=0,
                after_market_order=False,
                validity='DAY',
                amo_time='OPEN'
            )
            
            logger.info(f"SELL order placed for ITM CALL {best_itm_symbol}, Order ID: {itm_order}")
            
            # Calculate net position
            net_position = (6 * best_itm_premium) - (12 * atm_price)
            
            # Calculate risk profile
            max_risk = net_position * lot_size
            breakeven_point = strike_price + (net_position / 12)  # For CALLS, breakeven is above strike
            
            return {
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                'strategy_type': 'Ratio Backspread - CALL (Buy 12 ATM, Sell 6 ITM)',
                'atm_strike': strike_price,
                'atm_symbol': CE_symbol_name,
                'atm_price': atm_price,
                'atm_buy_orderid': atm_order,
                'atm_quantity': atm_quantity,
                'itm_strike': best_itm_strike,
                'itm_symbol': best_itm_symbol,
                'itm_price': best_itm_premium,
                'itm_sell_orderid': itm_order,
                'itm_quantity': itm_quantity,
                'net_position': net_position,
                'order_sequence': 'BUY first, then SELL (with 0.5-second pause)',
                'risk_profile': {
                    'max_risk': max_risk,
                    'unlimited_profit': True,
                    'breakeven_point': breakeven_point
                }
            }
            
    except Exception as e:
        logger.error(f"Error in CALL-12 strategy execution: {str(e)}")
        return None

def execute_nifty_ratio_backspread_put_12():
    """Execute the NIFTY ratio backspread strategy with PUT options (Buy 12 ATM, Sell 6 ITM)"""
    logger.info("Starting NIFTY ratio backspread strategy execution for PUT options (12:6)...")
    
    try:
        # Initialize Tradehull
        tsl = Tradehull(client_code, token_id)
        
        # Step 1: Get the ATM strike for NIFTY
        CE_symbol_name, PE_symbol_name, strike_price = tsl.ATM_Strike_Selection(Underlying='NIFTY', Expiry=0)
        logger.info(f"ATM Strike identified: {strike_price}, PE Symbol: {PE_symbol_name}")
        
        # Get ATM option price
        try:
            atm_price_data = tsl.get_ltp_data(names=[PE_symbol_name])
            atm_price = atm_price_data.get(PE_symbol_name, 0)
            logger.info(f"ATM option price: {atm_price}")
        except Exception as e:
            logger.error(f"Error getting ATM price: {str(e)}")
            logger.info("Continuing with default strategy...")
            atm_price = None
        
        # Use constant lot size
        CE_symbol_name, PE_symbol_name, strike_price = tsl.ATM_Strike_Selection(Underlying='NIFTY', Expiry=0)
        lot_size = tsl.get_lot_size(tradingsymbol=CE_symbol_name)
        logger.info(f"Lot size: {lot_size}")
        
        
        
        # Step 2: Find an ITM strike with a good premium
        found_itm_strike = False
        best_itm_strike = None
        best_itm_symbol = None
        best_itm_premium = 0
        smallest_net_difference = float('inf')
        
        # Extract expiry date from the ATM symbol
        expiry_components = PE_symbol_name.split(" ")
        if len(expiry_components) >= 3:
            expiry_str = " ".join(expiry_components[1:3])
            
            # Get all ITM strike prices in one batch
            strike_prices = get_batch_strike_prices(
                tsl=tsl,
                base_strike=strike_price,
                expiry_str=expiry_str,
                option_type='PUT',
                num_strikes=10,  # Check 10 strikes
                strike_step=50   # 50 point steps
            )
            
            # Calculate 12x ATM cost
            atm_cost_12x = 12 * atm_price
            
            # Check each ITM strike
            for strike, data in strike_prices.items():
                if strike <= strike_price:  # Skip OTM strikes for PUTS
                    continue
                    
                itm_price = data['price']
                net_difference = (6 * itm_price) - atm_cost_12x
                
                logger.info(f"Checking ITM PUT strike {strike}, price: {itm_price}, vs 12× ATM cost: {atm_cost_12x}, net: {net_difference:.2f}")
                
                # Update best strike if this one is better (closer to zero)
                if abs(net_difference) < abs(smallest_net_difference):
                    smallest_net_difference = net_difference
                    best_itm_strike = strike
                    best_itm_symbol = data['symbol']
                    best_itm_premium = itm_price
                    found_itm_strike = True
            
            if not found_itm_strike:
                logger.error("No suitable ITM strike found")
                return None
                
            logger.info(f"Selected ITM PUT strike to sell: {best_itm_strike}, Symbol: {best_itm_symbol}")
            
            # Calculate quantities
            atm_quantity = 12 * lot_size
            itm_quantity = 6 * lot_size
            
            # Place orders
            logger.info("FIRST STEP: Placing BUY orders for 12 ATM PUTs")
            atm_order = tsl.place_slice_order(
                tradingsymbol=PE_symbol_name,
                exchange='NFO', 
                quantity=atm_quantity,
                price=0,  # Market order
                trigger_price=0, 
                order_type='MARKET', 
                transaction_type='BUY', 
                trade_type='MIS',
                disclosed_quantity=0,
                after_market_order=False,
                validity='DAY',
                amo_time='OPEN'
            )
            
            logger.info(f"BUY order placed for ATM PUT {PE_symbol_name}, Order ID: {atm_order}")
            
            # Pause for 0.5 second
            logger.info("Pausing for 0.5 second...")
            time.sleep(0.5)
            
            logger.info("SECOND STEP: Placing SELL order for 6 ITM PUTs")
            itm_order = tsl.place_slice_order(
                tradingsymbol=best_itm_symbol,
                exchange='NFO', 
                quantity=itm_quantity,
                price=0,  # Market order
                trigger_price=0, 
                order_type='MARKET', 
                transaction_type='SELL', 
                trade_type='MIS',
                disclosed_quantity=0,
                after_market_order=False,
                validity='DAY',
                amo_time='OPEN'
            )
            
            logger.info(f"SELL order placed for ITM PUT {best_itm_symbol}, Order ID: {itm_order}")
            
            # Calculate net position
            net_position = (6 * best_itm_premium) - (12 * atm_price)
            
            # Calculate risk profile
            max_risk = net_position * lot_size
            breakeven_point = strike_price - (net_position / 12)  # For PUTS, breakeven is below strike
            
            return {
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                'strategy_type': 'Ratio Backspread - PUT (Buy 12 ATM, Sell 6 ITM)',
                'atm_strike': strike_price,
                'atm_symbol': PE_symbol_name,
                'atm_price': atm_price,
                'atm_buy_orderid': atm_order,
                'atm_quantity': atm_quantity,
                'itm_strike': best_itm_strike,
                'itm_symbol': best_itm_symbol,
                'itm_price': best_itm_premium,
                'itm_sell_orderid': itm_order,
                'itm_quantity': itm_quantity,
                'net_position': net_position,
                'order_sequence': 'BUY first, then SELL (with 0.5-second pause)',
                'risk_profile': {
                    'max_risk': max_risk,
                    'unlimited_profit': True,
                    'breakeven_point': breakeven_point
                }
            }
            
    except Exception as e:
        logger.error(f"Error in PUT-12 strategy execution: {str(e)}")
        return None

def execute_nifty_ratio_backspread_call_24():
    """Execute the NIFTY ratio backspread strategy with CALL options (Buy 24 ATM, Sell 12 ITM)"""
    logger.info("Starting NIFTY ratio backspread strategy execution for CALL options (24:12)...")
    
    try:
        # Initialize Tradehull
        tsl = Tradehull(client_code, token_id)
        
        # Step 1: Get the ATM strike for NIFTY
        CE_symbol_name, PE_symbol_name, strike_price = tsl.ATM_Strike_Selection(Underlying='NIFTY', Expiry=0)
        logger.info(f"ATM Strike identified: {strike_price}, CE Symbol: {CE_symbol_name}")
        
        # Get ATM option price
        try:
            atm_price_data = tsl.get_ltp_data(names=[CE_symbol_name])
            atm_price = atm_price_data.get(CE_symbol_name, 0)
            logger.info(f"ATM option price: {atm_price}")
        except Exception as e:
            logger.error(f"Error getting ATM price: {str(e)}")
            logger.info("Continuing with default strategy...")
            atm_price = None
        
        # Use constant lot size
        CE_symbol_name, PE_symbol_name, strike_price = tsl.ATM_Strike_Selection(Underlying='NIFTY', Expiry=0)
        lot_size = tsl.get_lot_size(tradingsymbol=CE_symbol_name)
        logger.info(f"Lot size: {lot_size}")
        
        
        # Step 2: Find an ITM strike with a good premium
        found_itm_strike = False
        best_itm_strike = None
        best_itm_symbol = None
        best_itm_premium = 0
        smallest_net_difference = float('inf')
        
        # Extract expiry date from the ATM symbol
        expiry_components = CE_symbol_name.split(" ")
        if len(expiry_components) >= 3:
            expiry_str = " ".join(expiry_components[1:3])
            
            # Get all ITM strike prices in one batch
            strike_prices = get_batch_strike_prices(
                tsl=tsl,
                base_strike=strike_price,
                expiry_str=expiry_str,
                option_type='CALL',
                num_strikes=10,  # Check 10 strikes
                strike_step=50   # 50 point steps
            )
            
            # Calculate 24x ATM cost
            atm_cost_24x = 24 * atm_price
            
            # Check each ITM strike
            for strike, data in strike_prices.items():
                if strike >= strike_price:  # Skip OTM strikes for CALLS
                    continue
                    
                itm_price = data['price']
                net_difference = (12 * itm_price) - atm_cost_24x
                
                logger.info(f"Checking ITM CALL strike {strike}, price: {itm_price}, vs 24× ATM cost: {atm_cost_24x}, net: {net_difference:.2f}")
                
                # Update best strike if this one is better (closer to zero)
                if abs(net_difference) < abs(smallest_net_difference):
                    smallest_net_difference = net_difference
                    best_itm_strike = strike
                    best_itm_symbol = data['symbol']
                    best_itm_premium = itm_price
                    found_itm_strike = True
            
            if not found_itm_strike:
                logger.error("No suitable ITM strike found")
                return None
                
            logger.info(f"Selected ITM CALL strike to sell: {best_itm_strike}, Symbol: {best_itm_symbol}")
            
            # Calculate quantities
            atm_quantity = 24 * lot_size
            itm_quantity = 12 * lot_size
            
            # Place orders
            logger.info("FIRST STEP: Placing BUY orders for 24 ATM CALLs")
            atm_order = tsl.place_slice_order(
                tradingsymbol=CE_symbol_name,
                exchange='NFO', 
                quantity=atm_quantity,
                price=0,  # Market order
                trigger_price=0, 
                order_type='MARKET', 
                transaction_type='BUY', 
                trade_type='MIS',
                disclosed_quantity=0,
                after_market_order=False,
                validity='DAY',
                amo_time='OPEN'
            )
            
            logger.info(f"BUY order placed for ATM CALL {CE_symbol_name}, Order ID: {atm_order}")
            
            # Pause for 0.5 second
            logger.info("Pausing for 0.5 second...")
            time.sleep(0.5)
            
            logger.info("SECOND STEP: Placing SELL order for 12 ITM CALLs")
            itm_order = tsl.place_slice_order(
                tradingsymbol=best_itm_symbol,
                exchange='NFO', 
                quantity=itm_quantity,
                price=0,  # Market order
                trigger_price=0, 
                order_type='MARKET', 
                transaction_type='SELL', 
                trade_type='MIS',
                disclosed_quantity=0,
                after_market_order=False,
                validity='DAY',
                amo_time='OPEN'
            )
            
            logger.info(f"SELL order placed for ITM CALL {best_itm_symbol}, Order ID: {itm_order}")
            
            # Calculate net position
            net_position = (12 * best_itm_premium) - (24 * atm_price)
            
            # Calculate risk profile
            max_risk = net_position * lot_size
            breakeven_point = strike_price + (net_position / 24)  # For CALLS, breakeven is above strike
            
            return {
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                'strategy_type': 'Ratio Backspread - CALL (Buy 24 ATM, Sell 12 ITM)',
                'atm_strike': strike_price,
                'atm_symbol': CE_symbol_name,
                'atm_price': atm_price,
                'atm_buy_orderid': atm_order,
                'atm_quantity': atm_quantity,
                'itm_strike': best_itm_strike,
                'itm_symbol': best_itm_symbol,
                'itm_price': best_itm_premium,
                'itm_sell_orderid': itm_order,
                'itm_quantity': itm_quantity,
                'net_position': net_position,
                'order_sequence': 'BUY first, then SELL (with 0.5-second pause)',
                'risk_profile': {
                    'max_risk': max_risk,
                    'unlimited_profit': True,
                    'breakeven_point': breakeven_point
                }
            }
            
    except Exception as e:
        logger.error(f"Error in CALL-24 strategy execution: {str(e)}")
        return None

def execute_nifty_ratio_backspread_put_24():
    """Execute the NIFTY ratio backspread strategy with PUT options (Buy 24 ATM, Sell 12 ITM)"""
    logger.info("Starting NIFTY ratio backspread strategy execution for PUT options (24:12)...")
    
    try:
        # Initialize Tradehull
        tsl = Tradehull(client_code, token_id)
        
        # Step 1: Get the ATM strike for NIFTY
        CE_symbol_name, PE_symbol_name, strike_price = tsl.ATM_Strike_Selection(Underlying='NIFTY', Expiry=0)
        logger.info(f"ATM Strike identified: {strike_price}, PE Symbol: {PE_symbol_name}")
        
        # Get ATM option price
        try:
            atm_price_data = tsl.get_ltp_data(names=[PE_symbol_name])
            atm_price = atm_price_data.get(PE_symbol_name, 0)
            logger.info(f"ATM option price: {atm_price}")
        except Exception as e:
            logger.error(f"Error getting ATM price: {str(e)}")
            logger.info("Continuing with default strategy...")
            atm_price = None
        
        # Use constant lot size
        CE_symbol_name, PE_symbol_name, strike_price = tsl.ATM_Strike_Selection(Underlying='NIFTY', Expiry=0)
        lot_size = tsl.get_lot_size(tradingsymbol=CE_symbol_name)
        logger.info(f"Using NIFTY lot size: {lot_size}")
        
        # Step 2: Find an ITM strike with a good premium
        found_itm_strike = False
        best_itm_strike = None
        best_itm_symbol = None
        best_itm_premium = 0
        smallest_net_difference = float('inf')
        
        # Extract expiry date from the ATM symbol
        expiry_components = PE_symbol_name.split(" ")
        if len(expiry_components) >= 3:
            expiry_str = " ".join(expiry_components[1:3])
            
            # Get all ITM strike prices in one batch
            strike_prices = get_batch_strike_prices(
                tsl=tsl,
                base_strike=strike_price,
                expiry_str=expiry_str,
                option_type='PUT',
                num_strikes=10,  # Check 10 strikes
                strike_step=50   # 50 point steps
            )
            
            # Calculate 24x ATM cost
            atm_cost_24x = 24 * atm_price
            
            # Check each ITM strike
            for strike, data in strike_prices.items():
                if strike <= strike_price:  # Skip OTM strikes for PUTS
                    continue
                    
                itm_price = data['price']
                net_difference = (12 * itm_price) - atm_cost_24x
                
                logger.info(f"Checking ITM PUT strike {strike}, price: {itm_price}, vs 24× ATM cost: {atm_cost_24x}, net: {net_difference:.2f}")
                
                # Update best strike if this one is better (closer to zero)
                if abs(net_difference) < abs(smallest_net_difference):
                    smallest_net_difference = net_difference
                    best_itm_strike = strike
                    best_itm_symbol = data['symbol']
                    best_itm_premium = itm_price
                    found_itm_strike = True
            
            if not found_itm_strike:
                logger.error("No suitable ITM strike found")
                return None
                
            logger.info(f"Selected ITM PUT strike to sell: {best_itm_strike}, Symbol: {best_itm_symbol}")
            
            # Calculate quantities
            atm_quantity = 24 * lot_size
            itm_quantity = 12 * lot_size
            
            # Place orders
            logger.info("FIRST STEP: Placing BUY orders for 24 ATM PUTs")
            atm_order = tsl.place_slice_order(
                tradingsymbol=PE_symbol_name,
                exchange='NFO', 
                quantity=atm_quantity,
                price=0,  # Market order
                trigger_price=0, 
                order_type='MARKET', 
                transaction_type='BUY', 
                trade_type='MIS',
                disclosed_quantity=0,
                after_market_order=False,
                validity='DAY',
                amo_time='OPEN'
            )
            
            logger.info(f"BUY order placed for ATM PUT {PE_symbol_name}, Order ID: {atm_order}")
            
            # Pause for 0.5 second
            logger.info("Pausing for 0.5 second...")
            time.sleep(0.5)
            
            logger.info("SECOND STEP: Placing SELL order for 12 ITM PUTs")
            itm_order = tsl.place_slice_order(
                tradingsymbol=best_itm_symbol,
                exchange='NFO', 
                quantity=itm_quantity,
                price=0,  # Market order
                trigger_price=0, 
                order_type='MARKET', 
                transaction_type='SELL', 
                trade_type='MIS',
                disclosed_quantity=0,
                after_market_order=False,
                validity='DAY',
                amo_time='OPEN'
            )
            
            logger.info(f"SELL order placed for ITM PUT {best_itm_symbol}, Order ID: {itm_order}")
            
            # Calculate net position
            net_position = (12 * best_itm_premium) - (24 * atm_price)
            
            # Calculate risk profile
            max_risk = net_position * lot_size
            breakeven_point = strike_price - (net_position / 24)  # For PUTS, breakeven is below strike
            
            return {
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                'strategy_type': 'Ratio Backspread - PUT (Buy 24 ATM, Sell 12 ITM)',
                'atm_strike': strike_price,
                'atm_symbol': PE_symbol_name,
                'atm_price': atm_price,
                'atm_buy_orderid': atm_order,
                'atm_quantity': atm_quantity,
                'itm_strike': best_itm_strike,
                'itm_symbol': best_itm_symbol,
                'itm_price': best_itm_premium,
                'itm_sell_orderid': itm_order,
                'itm_quantity': itm_quantity,
                'net_position': net_position,
                'order_sequence': 'BUY first, then SELL (with 0.5-second pause)',
                'risk_profile': {
                    'max_risk': max_risk,
                    'unlimited_profit': True,
                    'breakeven_point': breakeven_point
                }
            }
            
    except Exception as e:
        logger.error(f"Error in PUT-24 strategy execution: {str(e)}")
        return None

def execute_nifty_ratio_backspread_call_36():
    """Execute the NIFTY ratio backspread strategy with CALL options (Buy 36 ATM, Sell 18 ITM)"""
    logger.info("Starting NIFTY ratio backspread strategy execution for CALL options (36:18)...")
    
    try:
        # Initialize Tradehull
        tsl = Tradehull(client_code, token_id)
        
        # Step 1: Get the ATM strike for NIFTY
        CE_symbol_name, PE_symbol_name, strike_price = tsl.ATM_Strike_Selection(Underlying='NIFTY', Expiry=0)
        logger.info(f"ATM Strike identified: {strike_price}, CE Symbol: {CE_symbol_name}")
        
        # Get ATM option price
        try:
            atm_price_data = tsl.get_ltp_data(names=[CE_symbol_name])
            atm_price = atm_price_data.get(CE_symbol_name, 0)
            logger.info(f"ATM option price: {atm_price}")
        except Exception as e:
            logger.error(f"Error getting ATM price: {str(e)}")
            logger.info("Continuing with default strategy...")
            atm_price = None
        
        # Use constant lot size
        CE_symbol_name, PE_symbol_name, strike_price = tsl.ATM_Strike_Selection(Underlying='NIFTY', Expiry=0)
        lot_size = tsl.get_lot_size(tradingsymbol=CE_symbol_name)
        logger.info(f"Using NIFTY lot size: {lot_size}")
        
        # Step 2: Find an ITM strike with a good premium
        found_itm_strike = False
        best_itm_strike = None
        best_itm_symbol = None
        best_itm_premium = 0
        smallest_net_difference = float('inf')
        
        # Extract expiry date from the ATM symbol
        expiry_components = CE_symbol_name.split(" ")
        if len(expiry_components) >= 3:
            expiry_str = " ".join(expiry_components[1:3])
            
            # Get all ITM strike prices in one batch
            strike_prices = get_batch_strike_prices(
                tsl=tsl,
                base_strike=strike_price,
                expiry_str=expiry_str,
                option_type='CALL',
                num_strikes=10,  # Check 10 strikes
                strike_step=50   # 50 point steps
            )
            
            # Calculate 36x ATM cost
            atm_cost_36x = 36 * atm_price
            
            # Check each ITM strike
            for strike, data in strike_prices.items():
                if strike >= strike_price:  # Skip OTM strikes for CALLS
                    continue
                    
                itm_price = data['price']
                net_difference = (18 * itm_price) - atm_cost_36x
                
                logger.info(f"Checking ITM CALL strike {strike}, price: {itm_price}, vs 36× ATM cost: {atm_cost_36x}, net: {net_difference:.2f}")
                
                # Update best strike if this one is better (closer to zero)
                if abs(net_difference) < abs(smallest_net_difference):
                    smallest_net_difference = net_difference
                    best_itm_strike = strike
                    best_itm_symbol = data['symbol']
                    best_itm_premium = itm_price
                    found_itm_strike = True
            
            if not found_itm_strike:
                logger.error("No suitable ITM strike found")
                return None
                
            logger.info(f"Selected ITM CALL strike to sell: {best_itm_strike}, Symbol: {best_itm_symbol}")
            
            # Calculate quantities
            atm_quantity = 36 * lot_size
            itm_quantity = 18 * lot_size
            
            # Place BUY orders for ATM options using place_slice_order
            try:
                atm_orders = tsl.place_slice_order(
                    tradingsymbol=CE_symbol_name,
                    exchange='NFO',
                    transaction_type='BUY',
                    quantity=atm_quantity,
                    order_type='MARKET',
                    trade_type='MIS',
                    price=0,
                    trigger_price=0,
                    after_market_order=False,
                    validity='DAY',
                    amo_time='OPEN'
                )
                logger.info(f"Placed BUY orders for ATM CALL {CE_symbol_name}, Quantity: {atm_quantity}, Order IDs: {atm_orders}")
            except Exception as e:
                logger.error(f"Error placing ATM BUY orders: {str(e)}")
                return None
            
            # Wait for ATM orders to execute
            time.sleep(1)
            
            # Place SELL orders for ITM options using place_slice_order
            try:
                itm_orders = tsl.place_slice_order(
                    tradingsymbol=best_itm_symbol,
                    exchange='NFO',
                    transaction_type='SELL',
                    quantity=itm_quantity,
                    order_type='MARKET',
                    trade_type='MIS',
                    price=0,
                    trigger_price=0,
                    after_market_order=False,
                    validity='DAY',
                    amo_time='OPEN'
                )
                logger.info(f"Placed SELL orders for ITM CALL {best_itm_symbol}, Quantity: {itm_quantity}, Order IDs: {itm_orders}")
            except Exception as e:
                logger.error(f"Error placing ITM SELL orders: {str(e)}")
                return None
            
            # Calculate net position
            net_position = (18 * best_itm_premium) - (36 * atm_price)
            
            # Calculate risk profile
            max_risk = net_position * lot_size
            breakeven_point = strike_price + (net_position / 36)  # For CALLS, breakeven is above strike
            
            return {
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                'strategy_type': 'Ratio Backspread - CALL (Buy 36 ATM, Sell 18 ITM)',
                'atm_strike': strike_price,
                'atm_symbol': CE_symbol_name,
                'atm_price': atm_price,
                'atm_buy_orders': atm_orders if isinstance(atm_orders, list) else [atm_orders],
                'atm_quantity': atm_quantity,
                'itm_strike': best_itm_strike,
                'itm_symbol': best_itm_symbol,
                'itm_price': best_itm_premium,
                'itm_sell_orders': itm_orders if isinstance(itm_orders, list) else [itm_orders],
                'itm_quantity': itm_quantity,
                'net_position': net_position,
                'order_sequence': 'BUY first (sliced), then SELL (sliced) with delays',
                'risk_profile': {
                    'max_risk': max_risk,
                    'unlimited_profit': True,
                    'breakeven_point': breakeven_point
                }
            }
            
    except Exception as e:
        logger.error(f"Error in CALL-36 strategy execution: {str(e)}")
        return None

def execute_nifty_ratio_backspread_put_36():
    """Execute the NIFTY ratio backspread strategy with PUT options (Buy 36 ATM, Sell 18 ITM)"""
    logger.info("Starting NIFTY ratio backspread strategy execution for PUT options (36:18)...")
    
    try:
        # Initialize Tradehull
        tsl = Tradehull(client_code, token_id)
        
        # Step 1: Get the ATM strike for NIFTY
        CE_symbol_name, PE_symbol_name, strike_price = tsl.ATM_Strike_Selection(Underlying='NIFTY', Expiry=0)
        logger.info(f"ATM Strike identified: {strike_price}, PE Symbol: {PE_symbol_name}")
        
        # Get ATM option price
        try:
            atm_price_data = tsl.get_ltp_data(names=[PE_symbol_name])
            atm_price = atm_price_data.get(PE_symbol_name, 0)
            logger.info(f"ATM option price: {atm_price}")
        except Exception as e:
            logger.error(f"Error getting ATM price: {str(e)}")
            logger.info("Continuing with default strategy...")
            atm_price = None
        
        # Use constant lot size
        CE_symbol_name, PE_symbol_name, strike_price = tsl.ATM_Strike_Selection(Underlying='NIFTY', Expiry=0)
        lot_size = tsl.get_lot_size(tradingsymbol=CE_symbol_name)
        logger.info(f"Using NIFTY lot size: {lot_size}")
        
        # Step 2: Find an ITM strike with a good premium
        found_itm_strike = False
        best_itm_strike = None
        best_itm_symbol = None
        best_itm_premium = 0
        smallest_net_difference = float('inf')
        
        # Extract expiry date from the ATM symbol
        expiry_components = PE_symbol_name.split(" ")
        if len(expiry_components) >= 3:
            expiry_str = " ".join(expiry_components[1:3])
            
            # Get all ITM strike prices in one batch
            strike_prices = get_batch_strike_prices(
                tsl=tsl,
                base_strike=strike_price,
                expiry_str=expiry_str,
                option_type='PUT',
                num_strikes=10,  # Check 10 strikes
                strike_step=50   # 50 point steps
            )
            
            # Calculate 36x ATM cost
            atm_cost_36x = 36 * atm_price
            
            # Check each ITM strike
            for strike, data in strike_prices.items():
                if strike <= strike_price:  # Skip OTM strikes for PUTS
                    continue
                    
                itm_price = data['price']
                net_difference = (18 * itm_price) - atm_cost_36x
                
                logger.info(f"Checking ITM PUT strike {strike}, price: {itm_price}, vs 36× ATM cost: {atm_cost_36x}, net: {net_difference:.2f}")
                
                # Update best strike if this one is better (closer to zero)
                if abs(net_difference) < abs(smallest_net_difference):
                    smallest_net_difference = net_difference
                    best_itm_strike = strike
                    best_itm_symbol = data['symbol']
                    best_itm_premium = itm_price
                    found_itm_strike = True
            
            if not found_itm_strike:
                logger.error("No suitable ITM strike found")
                return None
                
            logger.info(f"Selected ITM PUT strike to sell: {best_itm_strike}, Symbol: {best_itm_symbol}")
            
            # Calculate quantitie
            atm_quantity = 36 * lot_size
            itm_quantity = 18 * lot_size
            
            # Place BUY orders for ATM options using place_slice_order
            try:
                atm_orders = tsl.place_slice_order(
                    tradingsymbol=PE_symbol_name,
                    exchange='NFO',
                    transaction_type='BUY',
                    quantity=atm_quantity,
                    order_type='MARKET',
                    trade_type='MIS',
                    price=0,
                    trigger_price=0,
                    after_market_order=False,
                    validity='DAY',
                    amo_time='OPEN'
                )
                logger.info(f"Placed BUY orders for ATM PUT {PE_symbol_name}, Quantity: {atm_quantity}, Order IDs: {atm_orders}")
            except Exception as e:
                logger.error(f"Error placing ATM BUY orders: {str(e)}")
                return None
            
            # Wait for ATM orders to execute
            time.sleep(1)
            
            # Place SELL orders for ITM options using place_slice_order
            try:
                itm_orders = tsl.place_slice_order(
                    tradingsymbol=best_itm_symbol,
                    exchange='NFO',
                    transaction_type='SELL',
                    quantity=itm_quantity,
                    order_type='MARKET',
                    trade_type='MIS',
                    price=0,
                    trigger_price=0,
                    after_market_order=False,
                    validity='DAY',
                    amo_time='OPEN'
                )
                logger.info(f"Placed SELL orders for ITM PUT {best_itm_symbol}, Quantity: {itm_quantity}, Order IDs: {itm_orders}")
            except Exception as e:
                logger.error(f"Error placing ITM SELL orders: {str(e)}")
                return None
            
            # Calculate net position
            net_position = (18 * best_itm_premium) - (36 * atm_price)
            
            # Calculate risk profile
            max_risk = net_position * lot_size
            breakeven_point = strike_price - (net_position / 36)  # For PUTS, breakeven is below strike
            
            return {
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                'strategy_type': 'Ratio Backspread - PUT (Buy 36 ATM, Sell 18 ITM)',
                'atm_strike': strike_price,
                'atm_symbol': PE_symbol_name,
                'atm_price': atm_price,
                'atm_buy_orders': atm_orders if isinstance(atm_orders, list) else [atm_orders],
                'atm_quantity': atm_quantity,
                'itm_strike': best_itm_strike,
                'itm_symbol': best_itm_symbol,
                'itm_price': best_itm_premium,
                'itm_sell_orders': itm_orders if isinstance(itm_orders, list) else [itm_orders],
                'itm_quantity': itm_quantity,
                'net_position': net_position,
                'order_sequence': 'BUY first (sliced), then SELL (sliced) with delays',
                'risk_profile': {
                    'max_risk': max_risk,
                    'unlimited_profit': True,
                    'breakeven_point': breakeven_point
                }
            }
            
    except Exception as e:
        logger.error(f"Error in PUT-36 strategy execution: {str(e)}")
        return None

# For testing the strategy independently
if __name__ == "__main__":
    # Configure logging for direct script execution
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Uncomment ONLY ONE of these functions to test:
        # result = execute_nifty_ratio_backspread_call_12()  # 12:6 ratio CALL
        # result = execute_nifty_ratio_backspread_put_12()    # 12:6 ratio PUT
        # result = execute_nifty_ratio_backspread_call_24()  # 24:12 ratio CALL
        # result = execute_nifty_ratio_backspread_put_24()   # 24:12 ratio PUT
        # result = execute_nifty_ratio_backspread_call_36()  # 36:18 ratio CALL
        # result = execute_nifty_ratio_backspread_put_36()   # 36:18 ratio PUT
        result = close_nifty_half_positions()                   # Close nifty half positions
        # result = close_nifty_all_positions()                   # Close nifty all positions

        
        logger.info(f"Operation completed: {result}")
    except Exception as e:
        logger.error(f"Error executing operation: {str(e)}", exc_info=True)