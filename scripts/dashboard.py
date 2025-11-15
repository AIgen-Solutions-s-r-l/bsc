#!/usr/bin/env python3
"""Web Dashboard for Arbitrage Monitoring System"""

from flask import Flask, render_template, jsonify, request
from db_manager import ArbitrageDB
from datetime import datetime, timedelta
import json
import os

# Set template folder relative to this script
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=template_dir)
db = ArbitrageDB()

@app.route('/')
def index():
    """Main dashboard"""
    return render_template('dashboard.html')

@app.route('/api/stats')
def stats():
    """Get overall statistics"""
    stats = db.get_stats_summary()

    # Add more detailed stats
    cursor = db.conn.cursor()

    # Opportunities by size
    cursor.execute('''
        SELECT
            CASE
                WHEN estimated_profit_usd < 1000 THEN 'Micro (<$1K)'
                WHEN estimated_profit_usd < 10000 THEN 'Small ($1K-$10K)'
                WHEN estimated_profit_usd < 100000 THEN 'Medium ($10K-$100K)'
                WHEN estimated_profit_usd < 1000000 THEN 'Large ($100K-$1M)'
                ELSE 'Whale (>$1M)'
            END as size_category,
            COUNT(*) as count,
            AVG(estimated_profit_usd) as avg_profit,
            SUM(estimated_profit_usd) as total_value
        FROM opportunities
        GROUP BY size_category
        ORDER BY avg_profit
    ''')
    stats['by_size'] = [dict(row) for row in cursor.fetchall()]

    # Recent activity (last hour)
    one_hour_ago = datetime.now() - timedelta(hours=1)
    cursor.execute('''
        SELECT COUNT(*) as count
        FROM opportunities
        WHERE timestamp > ?
    ''', (one_hour_ago,))
    stats['last_hour_opportunities'] = cursor.fetchone()['count']

    cursor.execute('''
        SELECT COUNT(*) as count
        FROM transactions
        WHERE timestamp > ?
    ''', (one_hour_ago,))
    stats['last_hour_transactions'] = cursor.fetchone()['count']

    return jsonify(stats)

@app.route('/api/opportunities')
def opportunities():
    """Get recent opportunities"""
    limit = request.args.get('limit', 100, type=int)
    captured_only = request.args.get('captured_only', 'false') == 'true'
    min_profit = request.args.get('min_profit', 0, type=float)
    max_profit = request.args.get('max_profit', 999999999, type=float)

    cursor = db.conn.cursor()
    cursor.execute('''
        SELECT * FROM opportunities
        WHERE estimated_profit_usd >= ? AND estimated_profit_usd <= ?
        AND (? = 0 OR was_captured = ?)
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (min_profit, max_profit, 0 if not captured_only else 1,
          1 if captured_only else 0, limit))

    opps = [dict(row) for row in cursor.fetchall()]

    # Format timestamps
    for opp in opps:
        if opp['timestamp']:
            opp['timestamp'] = opp['timestamp']
            opp['timestamp_human'] = datetime.fromisoformat(opp['timestamp']).strftime('%Y-%m-%d %H:%M:%S')

    return jsonify(opps)

@app.route('/api/transactions')
def transactions():
    """Get recent transactions"""
    limit = request.args.get('limit', 100, type=int)
    address = request.args.get('address', None)

    txs = db.get_transactions(limit=limit, address=address)

    # Format timestamps
    for tx in txs:
        if tx['timestamp']:
            tx['timestamp_human'] = datetime.fromisoformat(tx['timestamp']).strftime('%Y-%m-%d %H:%M:%S')

    return jsonify(txs)

@app.route('/api/arbitrageurs')
def arbitrageurs():
    """Get arbitrageur stats"""
    min_trades = request.args.get('min_trades', 0, type=int)
    arbs = db.get_arbitrageurs(min_trades=min_trades)

    # Format timestamps
    for arb in arbs:
        if arb['first_seen']:
            arb['first_seen_human'] = datetime.fromisoformat(arb['first_seen']).strftime('%Y-%m-%d %H:%M:%S')
        if arb['last_seen']:
            arb['last_seen_human'] = datetime.fromisoformat(arb['last_seen']).strftime('%Y-%m-%d %H:%M:%S')

    return jsonify(arbs)

@app.route('/api/pool_stats')
def pool_stats():
    """Get pool statistics"""
    stats = db.get_pool_stats()
    return jsonify(stats)

@app.route('/api/transaction/<tx_hash>')
def transaction_detail(tx_hash):
    """Get detailed transaction info"""
    cursor = db.conn.cursor()
    cursor.execute('SELECT * FROM transactions WHERE tx_hash = ?', (tx_hash,))
    tx = cursor.fetchone()

    if not tx:
        return jsonify({'error': 'Transaction not found'}), 404

    tx_dict = dict(tx)

    # Get associated opportunity
    if tx_dict.get('opportunity_id'):
        cursor.execute('SELECT * FROM opportunities WHERE id = ?', (tx_dict['opportunity_id'],))
        opp = cursor.fetchone()
        tx_dict['opportunity'] = dict(opp) if opp else None

    # Get arbitrageur info
    if tx_dict.get('from_address'):
        cursor.execute('SELECT * FROM arbitrageurs WHERE address = ?', (tx_dict['from_address'],))
        arb = cursor.fetchone()
        tx_dict['arbitrageur'] = dict(arb) if arb else None

    return jsonify(tx_dict)

@app.route('/api/opportunity/<int:opp_id>')
def opportunity_detail(opp_id):
    """Get detailed opportunity info"""
    cursor = db.conn.cursor()
    cursor.execute('SELECT * FROM opportunities WHERE id = ?', (opp_id,))
    opp = cursor.fetchone()

    if not opp:
        return jsonify({'error': 'Opportunity not found'}), 404

    opp_dict = dict(opp)

    # Get competition for this opportunity
    competition = db.get_competition_for_opportunity(opp_id)
    opp_dict['competition'] = competition

    # Get transaction if captured
    if opp_dict.get('captured_by'):
        cursor.execute('SELECT * FROM transactions WHERE from_address = ? AND block_number = ?',
                      (opp_dict['captured_by'], opp_dict.get('block_number')))
        tx = cursor.fetchone()
        opp_dict['capture_transaction'] = dict(tx) if tx else None

    return jsonify(opp_dict)

@app.route('/api/arbitrageur/<address>')
def arbitrageur_detail(address):
    """Get detailed arbitrageur info"""
    cursor = db.conn.cursor()
    cursor.execute('SELECT * FROM arbitrageurs WHERE address = ?', (address,))
    arb = cursor.fetchone()

    if not arb:
        return jsonify({'error': 'Arbitrageur not found'}), 404

    arb_dict = dict(arb)

    # Get all transactions from this address
    txs = db.get_transactions(limit=1000, address=address)
    arb_dict['transactions'] = txs

    # Get opportunities captured
    cursor.execute('''
        SELECT * FROM opportunities
        WHERE captured_by = ?
        ORDER BY timestamp DESC
    ''', (address,))
    arb_dict['opportunities_captured'] = [dict(row) for row in cursor.fetchall()]

    return jsonify(arb_dict)

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🌐 ARBITRAGE MONITORING DASHBOARD")
    print("="*60)
    print("\n📊 Dashboard URL: http://localhost:3000")
    print("\n💡 Features:")
    print("  • Real-time statistics")
    print("  • Opportunity browser with filters")
    print("  • Transaction analysis")
    print("  • Arbitrageur profiles")
    print("  • Pool statistics")
    print("\n⌨️  Press Ctrl+C to stop\n")

    app.run(debug=True, host='0.0.0.0', port=3000)
