#!/usr/bin/env python3
"""Database Manager for Arbitrage Monitoring System"""

import sqlite3
import os
from datetime import datetime
from typing import Dict, List, Optional, Any

class ArbitrageDB:
    def __init__(self, db_path='arbitrage-data/arbitrage.db'):
        self.db_path = db_path
        self.conn = None
        self.init_db()

    def init_db(self):
        """Initialize database with schema"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        # Read and execute schema
        schema_path = 'scripts/database_schema.sql'
        if os.path.exists(schema_path):
            with open(schema_path, 'r') as f:
                self.conn.executescript(f.read())
        print(f"✅ Database initialized: {self.db_path}")

    def log_opportunity(self, pool_name: str, pool_address: str,
                       imbalance_pct: float, profit_usd: float,
                       profit_bnb: float = None, block_number: int = None,
                       reserve0: float = None, reserve1: float = None,
                       token0: str = None, token1: str = None) -> int:
        """Log a detected opportunity"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO opportunities
            (timestamp, pool_name, pool_address, token0_address, token1_address,
             reserve0, reserve1, imbalance_pct, estimated_profit_usd,
             estimated_profit_bnb, block_number)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (datetime.now(), pool_name, pool_address, token0, token1,
              reserve0, reserve1, imbalance_pct, profit_usd, profit_bnb, block_number))
        self.conn.commit()
        return cursor.lastrowid

    def log_transaction(self, tx_hash: str, from_address: str,
                       block_number: int, gas_price_gwei: float,
                       swap_count: int = 0, profit_bnb: float = None,
                       profit_usd: float = None, strategy: str = None,
                       pools: List[str] = None, tokens: List[str] = None,
                       opportunity_id: int = None, gas_used: int = None,
                       execution_time_ms: int = None) -> int:
        """Log an observed arbitrage transaction"""
        cursor = self.conn.cursor()

        gas_cost = (gas_price_gwei * (gas_used or 200000) / 1e9) if gas_price_gwei else None

        cursor.execute('''
            INSERT OR IGNORE INTO transactions
            (tx_hash, block_number, timestamp, from_address, gas_price_gwei,
             gas_used, gas_cost_bnb, swap_count, pools_involved, tokens_involved,
             estimated_profit_bnb, estimated_profit_usd, strategy_type,
             opportunity_id, execution_time_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (tx_hash, block_number, datetime.now(), from_address, gas_price_gwei,
              gas_used, gas_cost, swap_count, ','.join(pools or []),
              ','.join(tokens or []), profit_bnb, profit_usd, strategy,
              opportunity_id, execution_time_ms))
        self.conn.commit()
        return cursor.lastrowid

    def update_arbitrageur(self, address: str, profit_bnb: float = 0,
                          profit_usd: float = 0, gas_price: float = None,
                          strategy: str = None, success: bool = True,
                          execution_time_ms: int = None):
        """Update or create arbitrageur record"""
        cursor = self.conn.cursor()

        # Check if exists
        cursor.execute('SELECT * FROM arbitrageurs WHERE address = ?', (address,))
        existing = cursor.fetchone()

        if existing:
            # Update existing
            new_total_trades = existing['total_trades'] + 1
            new_successful = existing['successful_trades'] + (1 if success else 0)
            new_failed = existing['failed_trades'] + (0 if success else 1)
            new_total_profit_bnb = existing['total_profit_bnb'] + profit_bnb
            new_total_profit_usd = existing['total_profit_usd'] + profit_usd
            new_avg_profit = new_total_profit_usd / new_total_trades if new_total_trades > 0 else 0
            new_win_rate = new_successful / new_total_trades if new_total_trades > 0 else 0

            # Calculate avg gas price
            if gas_price and existing['avg_gas_price_gwei']:
                new_avg_gas = (existing['avg_gas_price_gwei'] * existing['total_trades'] + gas_price) / new_total_trades
            else:
                new_avg_gas = gas_price or existing['avg_gas_price_gwei']

            # Update strategies
            strategies = set(existing['strategies_used'].split(',') if existing['strategies_used'] else [])
            if strategy:
                strategies.add(strategy)

            cursor.execute('''
                UPDATE arbitrageurs SET
                    last_seen = ?,
                    total_trades = ?,
                    successful_trades = ?,
                    failed_trades = ?,
                    total_profit_bnb = ?,
                    total_profit_usd = ?,
                    avg_profit_usd = ?,
                    avg_gas_price_gwei = ?,
                    strategies_used = ?,
                    win_rate = ?
                WHERE address = ?
            ''', (datetime.now(), new_total_trades, new_successful, new_failed,
                  new_total_profit_bnb, new_total_profit_usd, new_avg_profit,
                  new_avg_gas, ','.join(strategies), new_win_rate, address))
        else:
            # Insert new
            cursor.execute('''
                INSERT INTO arbitrageurs
                (address, first_seen, last_seen, total_trades, successful_trades,
                 failed_trades, total_profit_bnb, total_profit_usd, avg_profit_usd,
                 avg_gas_price_gwei, strategies_used, win_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (address, datetime.now(), datetime.now(), 1,
                  1 if success else 0, 0 if success else 1,
                  profit_bnb, profit_usd, profit_usd, gas_price,
                  strategy or '', 1.0 if success else 0.0))

        self.conn.commit()

    def mark_opportunity_captured(self, opportunity_id: int,
                                  captured_by: str, delay_ms: int):
        """Mark an opportunity as captured"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE opportunities SET
                was_captured = 1,
                captured_by = ?,
                capture_delay_ms = ?
            WHERE id = ?
        ''', (captured_by, delay_ms, opportunity_id))
        self.conn.commit()

    def log_competition(self, opportunity_id: int, tx_hash: str,
                       from_address: str, time_offset_ms: int,
                       gas_price_gwei: float, won: bool):
        """Log a competition attempt for an opportunity"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO competition
            (opportunity_id, tx_hash, from_address, timestamp,
             time_offset_ms, gas_price_gwei, won)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (opportunity_id, tx_hash, from_address, datetime.now(),
              time_offset_ms, gas_price_gwei, won))
        self.conn.commit()

    def get_recent_opportunities(self, limit: int = 50,
                                captured_only: bool = False) -> List[Dict]:
        """Get recent opportunities"""
        cursor = self.conn.cursor()
        query = 'SELECT * FROM opportunities'
        if captured_only:
            query += ' WHERE was_captured = 1'
        query += ' ORDER BY timestamp DESC LIMIT ?'

        cursor.execute(query, (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def get_arbitrageurs(self, min_trades: int = 0) -> List[Dict]:
        """Get arbitrageur stats"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM arbitrageurs
            WHERE total_trades >= ?
            ORDER BY total_profit_usd DESC
        ''', (min_trades,))
        return [dict(row) for row in cursor.fetchall()]

    def get_transactions(self, limit: int = 50,
                        address: str = None) -> List[Dict]:
        """Get recent transactions"""
        cursor = self.conn.cursor()
        if address:
            cursor.execute('''
                SELECT * FROM transactions
                WHERE from_address = ?
                ORDER BY timestamp DESC LIMIT ?
            ''', (address, limit))
        else:
            cursor.execute('''
                SELECT * FROM transactions
                ORDER BY timestamp DESC LIMIT ?
            ''', (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def get_pool_stats(self) -> List[Dict]:
        """Get pool statistics"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT
                pool_address,
                pool_name,
                COUNT(*) as total_opportunities,
                SUM(CASE WHEN was_captured = 1 THEN 1 ELSE 0 END) as total_captured,
                AVG(imbalance_pct) as avg_imbalance_pct,
                AVG(estimated_profit_usd) as avg_profit_usd,
                MIN(estimated_profit_usd) as min_profit_usd,
                MAX(estimated_profit_usd) as max_profit_usd,
                MAX(timestamp) as last_opportunity
            FROM opportunities
            GROUP BY pool_address, pool_name
            ORDER BY total_opportunities DESC
        ''')
        return [dict(row) for row in cursor.fetchall()]

    def get_competition_for_opportunity(self, opportunity_id: int) -> List[Dict]:
        """Get all competition attempts for an opportunity"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM competition
            WHERE opportunity_id = ?
            ORDER BY time_offset_ms
        ''', (opportunity_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_stats_summary(self) -> Dict[str, Any]:
        """Get overall statistics"""
        cursor = self.conn.cursor()

        stats = {}

        # Total opportunities
        cursor.execute('SELECT COUNT(*) as count FROM opportunities')
        stats['total_opportunities'] = cursor.fetchone()['count']

        # Captured opportunities
        cursor.execute('SELECT COUNT(*) as count FROM opportunities WHERE was_captured = 1')
        stats['captured_opportunities'] = cursor.fetchone()['count']

        # Total arbitrageurs
        cursor.execute('SELECT COUNT(*) as count FROM arbitrageurs')
        stats['total_arbitrageurs'] = cursor.fetchone()['count']

        # Total transactions
        cursor.execute('SELECT COUNT(*) as count FROM transactions')
        stats['total_transactions'] = cursor.fetchone()['count']

        # Total value detected
        cursor.execute('SELECT SUM(estimated_profit_usd) as total FROM opportunities')
        result = cursor.fetchone()
        stats['total_value_detected'] = result['total'] or 0

        # Total value captured
        cursor.execute('SELECT SUM(estimated_profit_usd) as total FROM opportunities WHERE was_captured = 1')
        result = cursor.fetchone()
        stats['total_value_captured'] = result['total'] or 0

        # Avg opportunity size
        cursor.execute('SELECT AVG(estimated_profit_usd) as avg FROM opportunities')
        result = cursor.fetchone()
        stats['avg_opportunity_size'] = result['avg'] or 0

        # Small opportunities (10K-100K)
        cursor.execute('''
            SELECT COUNT(*) as count, AVG(estimated_profit_usd) as avg
            FROM opportunities
            WHERE estimated_profit_usd BETWEEN 10000 AND 100000
        ''')
        result = cursor.fetchone()
        stats['small_opportunities_count'] = result['count']
        stats['small_opportunities_avg'] = result['avg'] or 0

        return stats

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

if __name__ == '__main__':
    # Initialize database
    db = ArbitrageDB()
    print("✅ Database initialized successfully!")

    # Show stats
    stats = db.get_stats_summary()
    print("\n📊 Database Statistics:")
    print(f"  Total Opportunities: {stats['total_opportunities']}")
    print(f"  Captured: {stats['captured_opportunities']}")
    print(f"  Total Arbitrageurs: {stats['total_arbitrageurs']}")
    print(f"  Total Transactions: {stats['total_transactions']}")
    print(f"  Total Value Detected: ${stats['total_value_detected']:,.2f}")
    print(f"  Small Opportunities (10K-100K): {stats['small_opportunities_count']}")

    db.close()
