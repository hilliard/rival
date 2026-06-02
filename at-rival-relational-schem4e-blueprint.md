To build a scalable "Beat the Bot" system, your relational database needs to cleanly separate the underlying sport data from the actual user entries—while treating the bot's entries structurally identical to a human's.

Here is the database schema designed to track performance, handle locking rules, and evaluate wins/losses cleanly over time.

1.  The Relational Schema Blueprint

                         +-------------------+
                         |      slates       |
                         +-------------------+
                                   | 1
                                   |
                                   | M
                         +-------------------+
                         |   slate_matches   |
                         +-------------------+
                                   | M
                                   |
                                   | 1
                         +-------------------+
                         |      matches      |
                         +-------------------+
                                   | 1
                                   |
                                   | M

    +-----------------+ | +-------------------+
    | users |--+--| submissions |
    +-----------------+ 1 +-------------------+
    (IsBot flag here) | 1
    |
    | M
    +-------------------+
    | submission_picks |
    +-------------------+

2.  Core SQL DDL Tables
    Here is the production-ready PostgreSQL layout to support this structure.

Users & Contest Foundations
The key here is the is_bot boolean in the user profile. This flags @TheRival for specialized processing or exclusion from real-world prizes while letting it consume normal platform mechanics.

```
-- 1. Users Table (Handles humans and bots identically)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    is_bot BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Contest Slates (The weekly containers)
CREATE TABLE slates (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL, -- e.g., "NFL 2026 - Week 1"
    lock_at TIMESTAMP WITH TIME ZONE NOT NULL, -- Submissions freeze here
    is_graded BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Sports Matches (The actual athletic events)
CREATE TABLE matches (
    id SERIAL PRIMARY KEY,
    home_team VARCHAR(100) NOT NULL,
    away_team VARCHAR(100) NOT NULL,
    game_start_at TIMESTAMP WITH TIME ZONE NOT NULL,
    home_score INT,
    away_score INT,
    status VARCHAR(20) DEFAULT 'SCHEDULED' -- SCHEDULED, LIVE, FINAL, PUSH, CANCELLED
);
```

The Contest Mappings & Predictions
A many-to-many lookup table defines exactly which matches belong to a specific weekly contest, preserving the point spreads lock-in value.

```
-- 4. Matches assigned to a specific slate with a static line
CREATE TABLE slate_matches (
    id SERIAL PRIMARY KEY,
    slate_id INT REFERENCES slates(id) ON DELETE CASCADE,
    match_id INT REFERENCES matches(id) ON DELETE CASCADE,
    spread_home_team NUMERIC(4,1) NOT NULL, -- e.g., -3.5 or +7.0
    total_line NUMERIC(4,1) NOT NULL,       -- e.g., 48.5
    CONSTRAINT unique_slate_match UNIQUE (slate_id, match_id)
);

-- 5. User Submissions (One per user, per slate)
CREATE TABLE submissions (
    id SERIAL PRIMARY KEY,
    slate_id INT REFERENCES slates(id) ON DELETE CASCADE,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_user_slate UNIQUE (slate_id, user_id)
);

-- 6. Granular Individual Picks inside a submission
CREATE TYPE prediction_type AS ENUM ('HOME_SPREAD', 'AWAY_SPREAD', 'OVER', 'UNDER');
CREATE TYPE pick_result AS ENUM ('PENDING', 'WIN', 'LOSS', 'PUSH');

CREATE TABLE submission_picks (
    id SERIAL PRIMARY KEY,
    submission_id INT REFERENCES submissions(id) ON DELETE CASCADE,
    slate_match_id INT REFERENCES slate_matches(id) ON DELETE CASCADE,
    selected_pick prediction_type NOT NULL,
    is_correct pick_result DEFAULT 'PENDING' NOT NULL,
    CONSTRAINT unique_submission_match UNIQUE (submission_id, slate_match_id)
);
```

3. Querying the Leaderboard: Human vs. Bot
   Because the schema handles bots and humans via an identical relationship pattern, calculating the global win-loss metrics or filtering out the bot's weekly performance is incredibly lightweight.

Fetching @TheRival's Standings for the Week
To pull up the bot's exact performance metrics to pin to the top of your contest interface:

```
|SELECT
    u.username,
    COUNT(CASE WHEN sp.is_correct = 'WIN' THEN 1 END) as wins,
    COUNT(CASE WHEN sp.is_correct = 'LOSS' THEN 1 END) as losses,
    COUNT(CASE WHEN sp.is_correct = 'PUSH' THEN 1 END) as pushes
FROM submissions s
JOIN users u ON s.user_id = u.id
JOIN submission_picks sp ON sp.submission_id = s.id
WHERE s.slate_id = 12  -- Target Week ID
  AND u.is_bot = TRUE
GROUP BY u.username;
```

Finding Users Currently "Beating the Bot"
This query isolates users who have accumulated more total correct picks than the highest-performing bot across the entire system.

```
WITH bot_max_wins AS (
    SELECT COUNT(sp.id) as max_bot_wins
    FROM submissions s
    JOIN users u ON s.user_id = u.id
    JOIN submission_picks sp ON sp.submission_id = s.id
    WHERE u.is_bot = TRUE AND sp.is_correct = 'WIN'
)
SELECT
    u.username,
    COUNT(sp.id) as human_wins
FROM submissions s
JOIN users u ON s.user_id = u.id
JOIN submission_picks sp ON sp.submission_id = s.id
WHERE u.is_bot = FALSE
  AND sp.is_correct = 'WIN'
GROUP BY u.username, bot_max_wins.max_bot_wins
HAVING COUNT(sp.id) > (SELECT max_bot_wins FROM bot_max_wins)
ORDER BY human_wins DESC;
```
