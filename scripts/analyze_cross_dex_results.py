#!/usr/bin/env python3
"""
Analyze Cross-DEX Arbitrage Results
Shows statistics and profitability of detected opportunities
"""

import sqlite3
from datetime import datetime, timedelta

DB_PATH = "arbitrage-data/cross_dex_arbitrage.db"

def analyze_results():
    """Analyze cross-DEX arbitrage results"""

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("="*70)
    print("CROSS-DEX ARBITRAGE ANALYSIS")
    print("="*70)

    # 2-way opportunities
    print("\n📊 2-WAY CROSS-DEX OPPORTUNITIES")
    print("-" * 70)

    cursor.execute("SELECT COUNT(*) FROM cross_dex_2way")
    count_2way = cursor.fetchone()[0]

    if count_2way > 0:
        cursor.execute("""
            SELECT
                MIN(timestamp) as first,
                MAX(timestamp) as last,
                COUNT(*) as total,
                AVG(estimated_profit_eur) as avg_profit,
                MAX(estimated_profit_eur) as max_profit,
                MIN(estimated_profit_eur) as min_profit
            FROM cross_dex_2way
        """)

        first, last, total, avg_profit, max_profit, min_profit = cursor.fetchone()

        print(f"Total opportunities: {total}")
        print(f"Period: {first} → {last}")
        print(f"\nProfit Statistics:")
        print(f"  Average: €{avg_profit:.2f}")
        print(f"  Maximum: €{max_profit:.2f}")
        print(f"  Minimum: €{min_profit:.2f}")

        # Top opportunities
        cursor.execute("""
            SELECT token0, token1, dex_buy, dex_sell, price_diff_pct, estimated_profit_eur
            FROM cross_dex_2way
            ORDER BY estimated_profit_eur DESC
            LIMIT 10
        """)

        print(f"\nTop 10 Opportunities:")
        print(f"{'Pair':12} | {'Buy DEX':15} | {'Sell DEX':15} | {'Diff %':>8} | {'Profit':>10}")
        print("-" * 70)

        for row in cursor.fetchall():
            token0, token1, dex_buy, dex_sell, diff, profit = row
            pair = f"{token0}-{token1}"
            print(f"{pair:12} | {dex_buy:15} | {dex_sell:15} | {diff:>7.3f}% | €{profit:>8.2f}")

        # By DEX pair
        cursor.execute("""
            SELECT
                dex_buy || ' → ' || dex_sell as dex_pair,
                COUNT(*) as count,
                AVG(estimated_profit_eur) as avg_profit
            FROM cross_dex_2way
            GROUP BY dex_pair
            ORDER BY count DESC
        """)

        print(f"\nOpportunities by DEX Pair:")
        print(f"{'DEX Pair':35} | {'Count':>6} | {'Avg Profit':>12}")
        print("-" * 70)

        for row in cursor.fetchall():
            dex_pair, count, avg_profit = row
            print(f"{dex_pair:35} | {count:>6} | €{avg_profit:>10.2f}")
    else:
        print("No 2-way opportunities found yet")

    # 3-way opportunities
    print("\n\n🔺 3-WAY TRIANGULAR OPPORTUNITIES")
    print("-" * 70)

    cursor.execute("SELECT COUNT(*) FROM triangular_3way")
    count_3way = cursor.fetchone()[0]

    if count_3way > 0:
        cursor.execute("""
            SELECT
                MIN(timestamp) as first,
                MAX(timestamp) as last,
                COUNT(*) as total,
                AVG(estimated_profit_eur) as avg_profit,
                MAX(estimated_profit_eur) as max_profit,
                MIN(estimated_profit_eur) as min_profit
            FROM triangular_3way
        """)

        first, last, total, avg_profit, max_profit, min_profit = cursor.fetchone()

        print(f"Total opportunities: {total}")
        print(f"Period: {first} → {last}")
        print(f"\nProfit Statistics:")
        print(f"  Average: €{avg_profit:.2f}")
        print(f"  Maximum: €{max_profit:.2f}")
        print(f"  Minimum: €{min_profit:.2f}")

        # Top opportunities
        cursor.execute("""
            SELECT path, dex_combination, profit_pct, estimated_profit_eur
            FROM triangular_3way
            ORDER BY estimated_profit_eur DESC
            LIMIT 10
        """)

        print(f"\nTop 10 Opportunities:")
        print("-" * 70)

        for i, row in enumerate(cursor.fetchall(), 1):
            path, dex_combo, profit_pct, profit = row
            print(f"{i}. {path}")
            print(f"   DEXs: {dex_combo}")
            print(f"   Profit: €{profit:.2f} ({profit_pct:.3f}%)")
    else:
        print("No 3-way opportunities found yet")

    # Summary
    print("\n\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    total_opps = count_2way + count_3way

    if total_opps > 0:
        # Calculate time range
        cursor.execute("""
            SELECT MIN(ts), MAX(ts) FROM (
                SELECT timestamp as ts FROM cross_dex_2way
                UNION ALL
                SELECT timestamp as ts FROM triangular_3way
            )
        """)
        first_time, last_time = cursor.fetchone()

        if first_time and last_time:
            first_dt = datetime.fromisoformat(first_time)
            last_dt = datetime.fromisoformat(last_time)
            duration_hours = (last_dt - first_dt).total_seconds() / 3600

            opps_per_hour = total_opps / duration_hours if duration_hours > 0 else 0

            print(f"\nTotal opportunities found: {total_opps}")
            print(f"  - 2-way: {count_2way}")
            print(f"  - 3-way: {count_3way}")
            print(f"\nDuration: {duration_hours:.1f} hours")
            print(f"Rate: {opps_per_hour:.1f} opportunities/hour")

            # Profit projections
            cursor.execute("""
                SELECT AVG(profit) FROM (
                    SELECT estimated_profit_eur as profit FROM cross_dex_2way
                    UNION ALL
                    SELECT estimated_profit_eur as profit FROM triangular_3way
                )
            """)
            avg_profit_all = cursor.fetchone()[0]

            # Conservative projections (10% win rate)
            win_rate = 0.10
            daily_opps = opps_per_hour * 24
            daily_wins = daily_opps * win_rate
            daily_profit = daily_wins * avg_profit_all

            print(f"\n📈 Projections (Conservative - 10% win rate):")
            print(f"  Avg profit/opportunity: €{avg_profit_all:.2f}")
            print(f"  Opportunities/day: {daily_opps:.0f}")
            print(f"  Wins/day: {daily_wins:.1f}")
            print(f"  Profit/day: €{daily_profit:,.2f}")
            print(f"  Profit/month: €{daily_profit * 30:,.2f}")
            print(f"  Profit/year: €{daily_profit * 365:,.2f}")
    else:
        print("\nNo data available yet. Let the tracker run for a while!")

    conn.close()

if __name__ == "__main__":
    analyze_results()
