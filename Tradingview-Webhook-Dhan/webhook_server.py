from flask import Flask, request, jsonify, render_template
import logging
import time
from waitress import serve
from Dhan_Tradehull import Tradehull
from credentials import client_code, token_id
import traceback

# Import strategy functions from strategies folder
from strategies.nifty_strategy import (
    # NIFTY strategies
    execute_nifty_ratio_backspread_call_12,
    execute_nifty_ratio_backspread_put_12,
    execute_nifty_ratio_backspread_call_24,
    execute_nifty_ratio_backspread_put_24,
    execute_nifty_ratio_backspread_call_36,
    execute_nifty_ratio_backspread_put_36,
    close_nifty_half_positions,
    close_nifty_all_positions
)


from strategies.banknifty_strategy import (
    # BANKNIFTY strategies
    execute_banknifty_ratio_backspread_call_12,
    execute_banknifty_ratio_backspread_put_12,
    execute_banknifty_ratio_backspread_call_24,
    execute_banknifty_ratio_backspread_put_24,
    execute_banknifty_ratio_backspread_call_36,
    execute_banknifty_ratio_backspread_put_36,
    close_banknifty_half_positions,
    close_banknifty_all_positions
)




from strategies.bel_strategy import (
    # BEL strategies
    execute_bel_ratio_backspread_call_4,
    execute_bel_ratio_backspread_put_4,
    execute_bel_ratio_backspread_call_8,
    execute_bel_ratio_backspread_put_8,
    close_bel_half_positions,
    close_bel_all_positions
)




from strategies.hal_strategy import (
    # HAL strategies
    execute_hal_ratio_backspread_call_4,
    execute_hal_ratio_backspread_put_4,
    execute_hal_ratio_backspread_call_8,
    execute_hal_ratio_backspread_put_8,
    close_hal_half_positions,
    close_hal_all_positions
)

from strategies.hindalco_strategy import (
    # HINDALCO strategies
    execute_hindalco_ratio_backspread_call_4,
    execute_hindalco_ratio_backspread_put_4,
    execute_hindalco_ratio_backspread_call_8,
    execute_hindalco_ratio_backspread_put_8,
    close_hindalco_half_positions,
    close_hindalco_all_positions
)


from strategies.coalindia_strategy import (
    # COALINDIA strategies
    execute_coalindia_ratio_backspread_call_4,
    execute_coalindia_ratio_backspread_put_4,
    execute_coalindia_ratio_backspread_call_8,
    execute_coalindia_ratio_backspread_put_8,
    close_coalindia_half_positions,
    close_coalindia_all_positions
)

from strategies.reliance_strategy import (
    # RELIANCE strategies
    execute_reliance_ratio_backspread_call_4,
    execute_reliance_ratio_backspread_put_4,
    execute_reliance_ratio_backspread_call_8,
    execute_reliance_ratio_backspread_put_8,
    close_reliance_half_positions,
    close_reliance_all_positions
)

from strategies.tatamotors_strategy import (
    # TATAMOTORS strategies
    execute_tatamotors_ratio_backspread_call_4,
    execute_tatamotors_ratio_backspread_put_4,
    execute_tatamotors_ratio_backspread_call_8,
    execute_tatamotors_ratio_backspread_put_8,
    close_tatamotors_half_positions,
    close_tatamotors_all_positions
)

from strategies.indusindbk_strategy import (
    # INDUSINDBK strategies
    execute_indusindbk_ratio_backspread_call_4,
    execute_indusindbk_ratio_backspread_put_4,
    execute_indusindbk_ratio_backspread_call_8,
    execute_indusindbk_ratio_backspread_put_8,
    close_indusindbk_half_positions,
    close_indusindbk_all_positions
)

from strategies.hdfcbank_strategy import (
    # HDFCBANK strategies
    execute_hdfcbank_ratio_backspread_call_4,
    execute_hdfcbank_ratio_backspread_put_4,
    execute_hdfcbank_ratio_backspread_call_8,
    execute_hdfcbank_ratio_backspread_put_8,
    close_hdfcbank_half_positions,
    close_hdfcbank_all_positions
)

from strategies.sbin_strategy import (
    # SBIN strategies
    execute_sbin_ratio_backspread_call_4,
    execute_sbin_ratio_backspread_put_4,
    execute_sbin_ratio_backspread_call_8,
    execute_sbin_ratio_backspread_put_8,
    close_sbin_half_positions,
    close_sbin_all_positions
)

from strategies.infy_strategy import (
    # INFY strategies
    execute_infy_ratio_backspread_call_4,
    execute_infy_ratio_backspread_put_4,
    execute_infy_ratio_backspread_call_8,
    execute_infy_ratio_backspread_put_8,
    close_infy_half_positions,
    close_infy_all_positions
)


from strategies.bhartiartl_strategy import (
    # BHARTIARTL strategies
    execute_bhartiartl_ratio_backspread_call_4,
    execute_bhartiartl_ratio_backspread_put_4,
    execute_bhartiartl_ratio_backspread_call_8,
    execute_bhartiartl_ratio_backspread_put_8,
    close_bhartiartl_half_positions,
    close_bhartiartl_all_positions
)

from strategies.icicibank_strategy import (
    # ICICIBANK strategies
    execute_icicibank_ratio_backspread_call_4,
    execute_icicibank_ratio_backspread_put_4,
    execute_icicibank_ratio_backspread_call_8,
    execute_icicibank_ratio_backspread_put_8,
    close_icicibank_half_positions,
    close_icicibank_all_positions
)

from strategies.bhel_strategy import (
    # BHEL strategies
    execute_bhel_ratio_backspread_call_4,
    execute_bhel_ratio_backspread_put_4,
    execute_bhel_ratio_backspread_call_8,
    execute_bhel_ratio_backspread_put_8,
    close_bhel_half_positions,
    close_bhel_all_positions
)

from strategies.canbk_strategy import (
    # CANBK strategies
    execute_canbk_ratio_backspread_call_4,
    execute_canbk_ratio_backspread_put_4,
    execute_canbk_ratio_backspread_call_8,
    execute_canbk_ratio_backspread_put_8,
    close_canbk_half_positions,
    close_canbk_all_positions
)

from strategies.axisbank_strategy import (
    # AXISBANK strategies
    execute_axisbank_ratio_backspread_call_4,
    execute_axisbank_ratio_backspread_put_4,
    execute_axisbank_ratio_backspread_call_8,
    execute_axisbank_ratio_backspread_put_8,
    close_axisbank_half_positions,
    close_axisbank_all_positions
)

from strategies.ntpc_strategy import (
    # NTPC strategies
    execute_ntpc_ratio_backspread_call_4,
    execute_ntpc_ratio_backspread_put_4,
    execute_ntpc_ratio_backspread_call_8,
    execute_ntpc_ratio_backspread_put_8,
    close_ntpc_half_positions,
    close_ntpc_all_positions
)



from strategies.pfc_strategy import (
    # PFC strategies
    execute_pfc_ratio_backspread_call_4,
    execute_pfc_ratio_backspread_put_4,
    execute_pfc_ratio_backspread_call_8,
    execute_pfc_ratio_backspread_put_8,
    close_pfc_half_positions,
    close_pfc_all_positions
)

from strategies.kotakbank_strategy import (
    # KOTAKBANK strategies
    execute_kotakbank_ratio_backspread_call_4,
    execute_kotakbank_ratio_backspread_put_4,
    execute_kotakbank_ratio_backspread_call_8,
    execute_kotakbank_ratio_backspread_put_8,
    close_kotakbank_half_positions,
    close_kotakbank_all_positions
)

from strategies.tatapower_strategy import (
    # TATAPOWER strategies
    execute_tatapower_ratio_backspread_call_4,
    execute_tatapower_ratio_backspread_put_4,
    execute_tatapower_ratio_backspread_call_8,
    execute_tatapower_ratio_backspread_put_8,
    close_tatapower_half_positions,
    close_tatapower_all_positions
)

from strategies.hindunilvr_strategy import (
    # HINDUNILVR strategies
    execute_hindunilvr_ratio_backspread_call_4,
    execute_hindunilvr_ratio_backspread_put_4,
    execute_hindunilvr_ratio_backspread_call_8,
    execute_hindunilvr_ratio_backspread_put_8,
    close_hindunilvr_half_positions,
    close_hindunilvr_all_positions
)



# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("webhook_logs.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Create the Flask app
app = Flask(__name__)

# Initialize Dhan client
tsl = Tradehull(client_code, token_id)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        logger.info(f"Received webhook data: {data}")
        
        if not data:
            logger.error("No data received in webhook")
            return jsonify({"status": "error", "message": "No data received"}), 400
            
        # Extract the message from the data
        message = data.get('message', '').strip().upper()
        logger.info(f"Processing message: {message}")
        
        # Handle NIFTY signals
        if message.startswith('NIFTY'):
            if message == 'NIFTY-EXIT-FULL':
                result = close_nifty_all_positions()
            elif message == 'NIFTY-EXIT-HALF':
                result = close_nifty_half_positions()
            elif message == 'NIFTY-ENTRY-CALL-12':
                result = execute_nifty_ratio_backspread_call_12()
            elif message == 'NIFTY-ENTRY-PUT-12':
                result = execute_nifty_ratio_backspread_put_12()
            elif message == 'NIFTY-ENTRY-CALL-24':
                result = execute_nifty_ratio_backspread_call_24()
            elif message == 'NIFTY-ENTRY-PUT-24':
                result = execute_nifty_ratio_backspread_put_24()
            elif message == 'NIFTY-ENTRY-CALL-36':
                result = execute_nifty_ratio_backspread_call_36()
            elif message == 'NIFTY-ENTRY-PUT-36':
                result = execute_nifty_ratio_backspread_put_36()
            else:
                return jsonify({
                    "status": "ignored",
                    "message": f"Unknown NIFTY signal: {message}"
                }), 200


        # Handle BANKNIFTY signals
        if message.startswith('BANKNIFTY'):
            if message == 'BANKNIFTY-EXIT-FULL':
                result = close_banknifty_all_positions()
            elif message == 'BANKNIFTY-EXIT-HALF':
                result = close_banknifty_half_positions()
            elif message == 'BANKNIFTY-ENTRY-CALL-12':
                result = execute_banknifty_ratio_backspread_call_12()
            elif message == 'BANKNIFTY-ENTRY-PUT-12':
                result = execute_banknifty_ratio_backspread_put_12()
            elif message == 'BANKNIFTY-ENTRY-CALL-24':
                result = execute_banknifty_ratio_backspread_call_24()
            elif message == 'BANKNIFTY-ENTRY-PUT-24':
                result = execute_banknifty_ratio_backspread_put_24()
            elif message == 'BANKNIFTY-ENTRY-CALL-36':
                result = execute_banknifty_ratio_backspread_call_36()
            elif message == 'BANKNIFTY-ENTRY-PUT-36':
                result = execute_banknifty_ratio_backspread_put_36()
            else:
                return jsonify({
                    "status": "ignored",
                    "message": f"Unknown BANKNIFTY signal: {message}"
                }), 200














        # Handle BEL signals
        elif message.startswith('BEL'):
            if message == 'BEL-EXIT-FULL':
                result = close_bel_all_positions()
            elif message == 'BEL-EXIT-HALF':
                result = close_bel_half_positions()
            elif message == 'BEL-ENTRY-CALL-4':
                result = execute_bel_ratio_backspread_call_4()
            elif message == 'BEL-ENTRY-PUT-4':
                result = execute_bel_ratio_backspread_put_4()
            elif message == 'BEL-ENTRY-CALL-8':
                result = execute_bel_ratio_backspread_call_8()
            elif message == 'BEL-ENTRY-PUT-8':
                result = execute_bel_ratio_backspread_put_8()
            else:
                return jsonify({
                    "status": "ignored",
                    "message": f"Unknown BEL signal: {message}"
                }), 200


        # Handle HAL signals
        elif message.startswith('HAL'):
            if message == 'HAL-EXIT-FULL':
                result = close_hal_all_positions()
            elif message == 'HAL-EXIT-HALF':
                result = close_hal_half_positions()
            elif message == 'HAL-ENTRY-CALL-4':
                result = execute_hal_ratio_backspread_call_4()
            elif message == 'HAL-ENTRY-PUT-4':
                result = execute_hal_ratio_backspread_put_4()
            elif message == 'HAL-ENTRY-CALL-8':
                result = execute_hal_ratio_backspread_call_8()
            elif message == 'HAL-ENTRY-PUT-8':
                result = execute_hal_ratio_backspread_put_8()
            else:
                return jsonify({
                    "status": "ignored",
                    "message": f"Unknown HAL signal: {message}"
                }), 200

        # Handle HINDALCO signals
        elif message.startswith('HINDALCO'):
            if message == 'HINDALCO-EXIT-FULL':
                result = close_hindalco_all_positions()
            elif message == 'HINDALCO-EXIT-HALF':
                result = close_hindalco_half_positions()
            elif message == 'HINDALCO-ENTRY-CALL-4':
                result = execute_hindalco_ratio_backspread_call_4()
            elif message == 'HINDALCO-ENTRY-PUT-4':
                result = execute_hindalco_ratio_backspread_put_4()
            elif message == 'HINDALCO-ENTRY-CALL-8':
                result = execute_hindalco_ratio_backspread_call_8()
            elif message == 'HINDALCO-ENTRY-PUT-8':
                result = execute_hindalco_ratio_backspread_put_8()
            else:
                return jsonify({
                    "status": "ignored",
                    "message": f"Unknown HINDALCO signal: {message}"
                }), 200

        # Handle COALINDIA signals
        elif message.startswith('COALINDIA'):
            if message == 'COALINDIA-EXIT-FULL':
                result = close_coalindia_all_positions()
            elif message == 'COALINDIA-EXIT-HALF':
                result = close_coalindia_half_positions()
            elif message == 'COALINDIA-ENTRY-CALL-4':
                result = execute_coalindia_ratio_backspread_call_4()
            elif message == 'COALINDIA-ENTRY-PUT-4':
                result = execute_coalindia_ratio_backspread_put_4()
            elif message == 'COALINDIA-ENTRY-CALL-8':
                result = execute_coalindia_ratio_backspread_call_8()
            elif message == 'COALINDIA-ENTRY-PUT-8':
                result = execute_coalindia_ratio_backspread_put_8()
            else:
                return jsonify({
                    "status": "ignored",
                    "message": f"Unknown COALINDIA signal: {message}"
                }), 200

        # Handle RELIANCE signals
        elif message.startswith('RELIANCE'):
            if message == 'RELIANCE-EXIT-FULL':
                result = close_reliance_all_positions()
            elif message == 'RELIANCE-EXIT-HALF':
                result = close_reliance_half_positions()
            elif message == 'RELIANCE-ENTRY-CALL-4':
                result = execute_reliance_ratio_backspread_call_4()
            elif message == 'RELIANCE-ENTRY-PUT-4':
                result = execute_reliance_ratio_backspread_put_4()
            elif message == 'RELIANCE-ENTRY-CALL-8':
                result = execute_reliance_ratio_backspread_call_8()
            elif message == 'RELIANCE-ENTRY-PUT-8':
                result = execute_reliance_ratio_backspread_put_8()
            else:
                return jsonify({
                    "status": "ignored",
                    "message": f"Unknown RELIANCE signal: {message}"
                }), 200

        # Handle TATAMOTORS signals
        elif message.startswith('TATAMOTORS'):
            if message == 'TATAMOTORS-EXIT-FULL':
                result = close_tatamotors_all_positions()
            elif message == 'TATAMOTORS-EXIT-HALF':
                result = close_tatamotors_half_positions()
            elif message == 'TATAMOTORS-ENTRY-CALL-4':
                result = execute_tatamotors_ratio_backspread_call_4()
            elif message == 'TATAMOTORS-ENTRY-PUT-4':
                result = execute_tatamotors_ratio_backspread_put_4()
            elif message == 'TATAMOTORS-ENTRY-CALL-8':
                result = execute_tatamotors_ratio_backspread_call_8()
            elif message == 'TATAMOTORS-ENTRY-PUT-8':
                result = execute_tatamotors_ratio_backspread_put_8()
            else:
                return jsonify({
                    "status": "ignored",
                    "message": f"Unknown TATAMOTORS signal: {message}"
                }), 200


        # Handle INDUSINDBK signals
        elif message.startswith('INDUSINDBK'):
            if message == 'INDUSINDBK-EXIT-FULL':
                result = close_indusindbk_all_positions()
            elif message == 'INDUSINDBK-EXIT-HALF':
                result = close_indusindbk_half_positions()
            elif message == 'INDUSINDBK-ENTRY-CALL-4':
                result = execute_indusindbk_ratio_backspread_call_4()
            elif message == 'INDUSINDBK-ENTRY-PUT-4':
                result = execute_indusindbk_ratio_backspread_put_4()
            elif message == 'INDUSINDBK-ENTRY-CALL-8':
                result = execute_indusindbk_ratio_backspread_call_8()
            elif message == 'INDUSINDBK-ENTRY-PUT-8':
                result = execute_indusindbk_ratio_backspread_put_8()
            else:
                return jsonify({
                    "status": "ignored",
                    "message": f"Unknown INDUSINDBK signal: {message}"
                }), 200


        # Handle HDFCBANK signals
        elif message.startswith('HDFCBANK'):
            if message == 'HDFCBANK-EXIT-FULL':
                result = close_hdfcbank_all_positions()
            elif message == 'HDFCBANK-EXIT-HALF':
                result = close_hdfcbank_half_positions()
            elif message == 'HDFCBANK-ENTRY-CALL-4':
                result = execute_hdfcbank_ratio_backspread_call_4()
            elif message == 'HDFCBANK-ENTRY-PUT-4':
                result = execute_hdfcbank_ratio_backspread_put_4()
            elif message == 'HDFCBANK-ENTRY-CALL-8':
                result = execute_hdfcbank_ratio_backspread_call_8()
            elif message == 'HDFCBANK-ENTRY-PUT-8':
                result = execute_hdfcbank_ratio_backspread_put_8()
            else:
                return jsonify({
                    "status": "ignored",
                    "message": f"Unknown HDFCBANK signal: {message}"
                }), 200

        # Handle SBIN signals
        elif message.startswith('SBIN'):
            if message == 'SBIN-EXIT-FULL':
                result = close_sbin_all_positions()
            elif message == 'SBIN-EXIT-HALF':
                result = close_sbin_half_positions()
            elif message == 'SBIN-ENTRY-CALL-4':
                result = execute_sbin_ratio_backspread_call_4()
            elif message == 'SBIN-ENTRY-PUT-4':
                result = execute_sbin_ratio_backspread_put_4()
            elif message == 'SBIN-ENTRY-CALL-8':
                result = execute_sbin_ratio_backspread_call_8()
            elif message == 'SBIN-ENTRY-PUT-8':
                result = execute_sbin_ratio_backspread_put_8()
            else:
                return jsonify({
                    "status": "ignored",
                    "message": f"Unknown SBI signal: {message}"
                }), 200

        # Handle INFY signals
        elif message.startswith('INFY'):
            if message == 'INFY-EXIT-FULL':
                result = close_infy_all_positions()
            elif message == 'INFY-EXIT-HALF':
                result = close_infy_half_positions()
            elif message == 'INFY-ENTRY-CALL-4':
                result = execute_infy_ratio_backspread_call_4()
            elif message == 'INFY-ENTRY-PUT-4':
                result = execute_infy_ratio_backspread_put_4()
            elif message == 'INFY-ENTRY-CALL-8':
                result = execute_infy_ratio_backspread_call_8()
            elif message == 'INFY-ENTRY-PUT-8':
                result = execute_infy_ratio_backspread_put_8()
            else:
                return jsonify({
                    "status": "ignored",
                    "message": f"Unknown INFY signal: {message}"
                }), 200

        # Handle BHARTIARTL signals
        elif message.startswith('BHARTIARTL'):
            if message == 'BHARTIARTL-EXIT-FULL':
                result = close_bhartiartl_all_positions()
            elif message == 'BHARTIARTL-EXIT-HALF':
                result = close_bhartiartl_half_positions()
            elif message == 'BHARTIARTL-ENTRY-CALL-4':
                result = execute_bhartiartl_ratio_backspread_call_4()
            elif message == 'BHARTIARTL-ENTRY-PUT-4':
                result = execute_bhartiartl_ratio_backspread_put_4()
            elif message == 'BHARTIARTL-ENTRY-CALL-8':
                result = execute_bhartiartl_ratio_backspread_call_8()
            elif message == 'BHARTIARTL-ENTRY-PUT-8':
                result = execute_bhartiartl_ratio_backspread_put_8()
            else:
                return jsonify({
                    "status": "ignored",
                    "message": f"Unknown BHARTIARTL signal: {message}"
                }), 200

        # Handle ICICIBANK signals
        elif message.startswith('ICICIBANK'):
            if message == 'ICICIBANK-EXIT-FULL':
                result = close_icicibank_all_positions()
            elif message == 'ICICIBANK-EXIT-HALF':
                result = close_icicibank_half_positions()
            elif message == 'ICICIBANK-ENTRY-CALL-4':
                result = execute_icicibank_ratio_backspread_call_4()
            elif message == 'ICICIBANK-ENTRY-PUT-4':
                result = execute_icicibank_ratio_backspread_put_4()
            elif message == 'ICICIBANK-ENTRY-CALL-8':
                result = execute_icicibank_ratio_backspread_call_8()
            elif message == 'ICICIBANK-ENTRY-PUT-8':
                result = execute_icicibank_ratio_backspread_put_8()
            else:
                return jsonify({
                    "status": "ignored",
                    "message": f"Unknown ICICIBANK signal: {message}"
                }), 200

        # Handle BHEL signals
        elif message.startswith('BHEL'):
            if message == 'BHEL-EXIT-FULL':
                result = close_bhel_all_positions()
            elif message == 'BHEL-EXIT-HALF':
                result = close_bhel_half_positions()
            elif message == 'BHEL-ENTRY-CALL-4':
                result = execute_bhel_ratio_backspread_call_4()
            elif message == 'BHEL-ENTRY-PUT-4':
                result = execute_bhel_ratio_backspread_put_4()
            elif message == 'BHEL-ENTRY-CALL-8':
                result = execute_bhel_ratio_backspread_call_8()
            elif message == 'BHEL-ENTRY-PUT-8':
                result = execute_bhel_ratio_backspread_put_8()
            else:
                return jsonify({
                    "status": "ignored",
                    "message": f"Unknown BHEL signal: {message}"
                }), 200

        # Handle CANBK signals
        elif message.startswith('CANBK'):
            if message == 'CANBK-EXIT-FULL':
                result = close_canbk_all_positions()
            elif message == 'CANBK-EXIT-HALF':
                result = close_canbk_half_positions()
            elif message == 'CANBK-ENTRY-CALL-4':
                result = execute_canbk_ratio_backspread_call_4()
            elif message == 'CANBK-ENTRY-PUT-4':
                result = execute_canbk_ratio_backspread_put_4()
            elif message == 'CANBK-ENTRY-CALL-8':
                result = execute_canbk_ratio_backspread_call_8()
            elif message == 'CANBK-ENTRY-PUT-8':
                result = execute_canbk_ratio_backspread_put_8()
            else:
                return jsonify({
                    "status": "ignored",
                    "message": f"Unknown CANBK signal: {message}"
                }), 200

        # Handle AXISBANK signals
        elif message.startswith('AXISBANK'):
            if message == 'AXISBANK-EXIT-FULL':
                result = close_axisbank_all_positions()
            elif message == 'AXISBANK-EXIT-HALF':
                result = close_axisbank_half_positions()
            elif message == 'AXISBANK-ENTRY-CALL-4':
                result = execute_axisbank_ratio_backspread_call_4()
            elif message == 'AXISBANK-ENTRY-PUT-4':
                result = execute_axisbank_ratio_backspread_put_4()
            elif message == 'AXISBANK-ENTRY-CALL-8':
                result = execute_axisbank_ratio_backspread_call_8()
            elif message == 'AXISBANK-ENTRY-PUT-8':
                result = execute_axisbank_ratio_backspread_put_8()
            else:
                return jsonify({
                    "status": "ignored",
                    "message": f"Unknown AXISBANK signal: {message}"
                }), 200


        # Handle NTPC signals
        elif message.startswith('NTPC'):
            if message == 'NTPC-EXIT-FULL':
                result = close_ntpc_all_positions()
            elif message == 'NTPC-EXIT-HALF':
                result = close_ntpc_half_positions()
            elif message == 'NTPC-ENTRY-CALL-4':
                result = execute_ntpc_ratio_backspread_call_4()
            elif message == 'NTPC-ENTRY-PUT-4':
                result = execute_ntpc_ratio_backspread_put_4()
            elif message == 'NTPC-ENTRY-CALL-8':
                result = execute_ntpc_ratio_backspread_call_8()
            elif message == 'NTPC-ENTRY-PUT-8':
                result = execute_ntpc_ratio_backspread_put_8()
            else:
                return jsonify({
                    "status": "ignored",
                    "message": f"Unknown NTPC signal: {message}"
                }), 200



        # Handle PFC signals
        elif message.startswith('PFC'):
            if message == 'PFC-EXIT-FULL':
                result = close_pfc_all_positions()
            elif message == 'PFC-EXIT-HALF':
                result = close_pfc_half_positions()
            elif message == 'PFC-ENTRY-CALL-4':
                result = execute_pfc_ratio_backspread_call_4()
            elif message == 'PFC-ENTRY-PUT-4':
                result = execute_pfc_ratio_backspread_put_4()
            elif message == 'PFC-ENTRY-CALL-8':
                result = execute_pfc_ratio_backspread_call_8()
            elif message == 'PFC-ENTRY-PUT-8':
                result = execute_pfc_ratio_backspread_put_8()
            else:
                return jsonify({
                    "status": "ignored",
                    "message": f"Unknown PFC signal: {message}"
                }), 200

        # Handle KOTAKBANK signals
        elif message.startswith('KOTAKBANK'):
            if message == 'KOTAKBANK-EXIT-FULL':
                result = close_kotakbank_all_positions()
            elif message == 'KOTAKBANK-EXIT-HALF':
                result = close_kotakbank_half_positions()
            elif message == 'KOTAKBANK-ENTRY-CALL-4':
                result = execute_kotakbank_ratio_backspread_call_4()
            elif message == 'KOTAKBANK-ENTRY-PUT-4':
                result = execute_kotakbank_ratio_backspread_put_4()
            elif message == 'RELIANCE-ENTRY-CALL-8':
                result = execute_kotakbank_ratio_backspread_call_8()
            elif message == 'KOTAKBANK-ENTRY-PUT-8':
                result = execute_kotakbank_ratio_backspread_put_8()
            else:
                return jsonify({
                    "status": "ignored",
                    "message": f"Unknown KOTAKBANK signal: {message}"
                }), 200

        # Handle TATAPOWER signals
        elif message.startswith('TATAPOWER'):
            if message == 'TATAPOWER-EXIT-FULL':
                result = close_tatapower_all_positions()
            elif message == 'TATAPOWER-EXIT-HALF':
                result = close_tatapower_half_positions()
            elif message == 'TATAPOWER-ENTRY-CALL-4':
                result = execute_tatapower_ratio_backspread_call_4()
            elif message == 'TATAPOWER-ENTRY-PUT-4':
                result = execute_tatapower_ratio_backspread_put_4()
            elif message == 'TATAPOWER-ENTRY-CALL-8':
                result = execute_tatapower_ratio_backspread_call_8()
            elif message == 'TATAPOWER-ENTRY-PUT-8':
                result = execute_tatapower_ratio_backspread_put_8()
            else:
                return jsonify({
                    "status": "ignored",
                    "message": f"Unknown TATAPOWER signal: {message}"
                }), 200

        # Handle HINDUNILVR signals
        elif message.startswith('HINDUNILVR'):
            if message == 'HINDUNILVR-EXIT-FULL':
                result = close_hindunilvr_all_positions()
            elif message == 'HINDUNILVR-EXIT-HALF':
                result = close_hindunilvr_half_positions()
            elif message == 'HINDUNILVR-ENTRY-CALL-4':
                result = execute_hindunilvr_ratio_backspread_call_4()
            elif message == 'HINDUNILVR-ENTRY-PUT-4':
                result = execute_hindunilvr_ratio_backspread_put_4()
            elif message == 'HINDUNILVR-ENTRY-CALL-8':
                result = execute_hindunilvr_ratio_backspread_call_8()
            elif message == 'HINDUNILVR-ENTRY-PUT-8':
                result = execute_hindunilvr_ratio_backspread_put_8()
            else:
                return jsonify({
                    "status": "ignored",
                    "message": f"Unknown HINDUNILVR signal: {message}"
                }), 200
            

        # Unknown signal
        else:
            logger.warning(f"Unknown signal received: {message}")
            return jsonify({
                "status": "ignored",
                "message": f"Unknown signal: {message}. Expected NIFTY or RELIANCE signals."
            }), 200

        # Return the result
        logger.info(f"Strategy execution result: {result}")
        return jsonify({
            "status": "success",
            "message": f"Strategy executed successfully",
            "details": result
        }), 200
            
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": f"Error processing webhook: {str(e)}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }), 500

if __name__ == '__main__':
    # Log startup
    logger.info("Starting unified webhook server...")
    
    # For development mode (automatic reloading)
    app.run(debug=True, host='0.0.0.0', port=80) 