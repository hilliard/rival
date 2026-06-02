To automatically handle the settlement of picks and update the leaderboard when games conclude, you need an automated background worker. This worker typically runs on a cron schedule (e.g., every 5 minutes during game days) to fetch finished games, grade each user's pick against the final score, and flag the contest slates as fully processed.

Here is the operational logic and the automation script required to drive the backend grading engine.

1. The Core Grading Logic (SQL Driven)
   Instead of pulling thousands of records into memory, processing them individually, and pushing them back to the database, you can execute the grading via highly efficient set-based SQL operations.

When a match status hits 'FINAL', this single query updates all matching submission_picks simultaneously by evaluating the final scores against the lines recorded in slate_matches.

```
-- Grade Point Spreads
UPDATE submission_picks sp
SET is_correct = CASE
    -- Home Spread Win
    WHEN sp.selected_pick = 'HOME_SPREAD' AND (m.home_score + sm.spread_home_team) > m.away_score THEN 'WIN'::pick_result
    -- Away Spread Win (Reverse of home)
    WHEN sp.selected_pick = 'AWAY_SPREAD' AND (m.home_score + sm.spread_home_team) < m.away_score THEN 'WIN'::pick_result
    -- Push Condition
    WHEN (m.home_score + sm.spread_home_team) = m.away_score THEN 'PUSH'::pick_result
    -- Otherwise Loss
    ELSE 'LOSS'::pick_result
END
FROM slate_matches sm
JOIN matches m ON sm.match_id = m.id
WHERE sp.slate_match_id = sm.id
  AND m.status = 'FINAL'
  AND sp.is_correct = 'PENDING';

-- Grade Over/Unders
UPDATE submission_picks sp
SET is_correct = CASE
    -- Over Win
    WHEN sp.selected_pick = 'OVER' AND (m.home_score + m.away_score) > sm.total_line THEN 'WIN'::pick_result
    -- Under Win
    WHEN sp.selected_pick = 'UNDER' AND (m.home_score + m.away_score) < sm.total_line THEN 'WIN'::pick_result
    -- Push Condition
    WHEN (m.home_score + m.away_score) = sm.total_line THEN 'PUSH'::pick_result
    ELSE 'LOSS'::pick_result
END
FROM slate_matches sm
JOIN matches m ON sm.match_id = m.id
WHERE sp.slate_match_id = sm.id
  AND m.status = 'FINAL'
  AND sp.is_correct = 'PENDING'
  AND sp.selected_pick IN ('OVER', 'UNDER');
```

2. The Python Background Worker Script
   This script acts as the scheduler. It connects to the database, looks for recently finished games, triggers the grading engine, and logs the execution output.

```
import os
import time
import logging
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/sports_platform")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def settle_completed_games():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 1. Find matches that are completed but still have pending picks
            cur.execute("""
                SELECT DISTINCT m.id, m.home_team, m.away_team
                FROM matches m
                JOIN slate_matches sm ON sm.match_id = m.id
                JOIN submission_picks sp ON sp.slate_match_id = sm.id
                WHERE m.status = 'FINAL' AND sp.is_correct = 'PENDING';
            """)
            pending_matches = cur.fetchall()

            if not pending_matches:
                logging.info("No newly completed games to grade.")
                return

            logging.info(f"Found {len(pending_matches)} matches ready for grading.")

            # 2. Execute Spreads Grading
            cur.execute("""
                UPDATE submission_picks sp
                SET is_correct = CASE
                    WHEN sp.selected_pick = 'HOME_SPREAD' AND (m.home_score + sm.spread_home_team) > m.away_score THEN 'WIN'::pick_result
                    WHEN sp.selected_pick = 'AWAY_SPREAD' AND (m.home_score + sm.spread_home_team) < m.away_score THEN 'WIN'::pick_result
                    WHEN (m.home_score + sm.spread_home_team) = m.away_score THEN 'PUSH'::pick_result
                    ELSE 'LOSS'::pick_result
                END
                FROM slate_matches sm JOIN matches m ON sm.match_id = m.id
                WHERE sp.slate_match_id = sm.id AND m.status = 'FINAL' AND sp.is_correct = 'PENDING' AND sp.selected_pick IN ('HOME_SPREAD', 'AWAY_SPREAD');
            """)
            spreads_updated = cur.rowcount

            # 3. Execute Totals Grading
            cur.execute("""
                UPDATE submission_picks sp
                SET is_correct = CASE
                    WHEN sp.selected_pick = 'OVER' AND (m.home_score + m.away_score) > sm.total_line THEN 'WIN'::pick_result
                    WHEN sp.selected_pick = 'UNDER' AND (m.home_score + m.away_score) < sm.total_line THEN 'WIN'::pick_result
                    WHEN (m.home_score + m.away_score) = sm.total_line THEN 'PUSH'::pick_result
                    ELSE 'LOSS'::pick_result
                END
                FROM slate_matches sm JOIN matches m ON sm.match_id = m.id
                WHERE sp.slate_match_id = sm.id AND m.status = 'FINAL' AND sp.is_correct = 'PENDING' AND sp.selected_pick IN ('OVER', 'UNDER');
            """)
            totals_updated = cur.rowcount

            conn.commit()
            logging.info(f"Grading complete. Settled {spreads_updated} spread picks and {totals_updated} totals picks.")

            # 4. Check if any slates are now completely finished to close them out
            cur.execute("""
                UPDATE slates s
                SET is_graded = TRUE
                WHERE s.is_graded = FALSE AND NOT EXISTS (
                    SELECT 1 FROM slate_matches sm
                    JOIN submission_picks sp ON sp.slate_match_id = sm.id
                    WHERE sm.slate_id = s.id AND sp.is_correct = 'PENDING'
                );
            """)
            if cur.rowcount > 0:
                logging.info(f"Closed out {cur.rowcount} fully completed contest slates.")

    except Exception as e:
        conn.rollback()
        logging.error(f"Error during background processing: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    logging.info("Starting Background Grading Worker...")
    while True:
        settle_completed_games()
        # Polling intervals can be shortened during heavy live windows
        time.sleep(300)
```

###### Background Simululator

3. Background Pipeline Simulator
   To explore how data transitions inside the processing loop when games finish, use the pipeline simulation panel below. You can simulate setting game results, running the database grading loop, and watching how @TheRival and human leaderboard standings update immediately following data resolution.
