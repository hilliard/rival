# API Flow and Payload Map

This is the text-based replacement for the architecture image referenced in [at-rival-architecture.md](at-rival-architecture.md).

## ASCII Flow

```text
HaynesWorld API
  |-- POST /api/v1/auth/bot-login
  |      -> returns short-lived JWT
  |
  |-- GET /api/v1/contest/active-slates
  |      -> returns active slates, match IDs, lines, lock times
  |
  v
Rival Worker
  |-- sends slate data to Data Engine
  |      -> receives picks + confidence + rationale
  |
  |-- sends picks + context to Persona Engine
  |      -> receives benchmark topic/comment text
  |
  |-- POST /api/v1/contest/submissions
  |-- POST /api/v1/forum/topics
  |-- POST /api/v1/forum/comments
  v
HaynesWorld API accepts payloads and applies platform rules
```

## Example Payloads

### Bot Login Request

```json
{
  "api_key": "rival-service-key",
  "client_name": "therival",
  "client_version": "0.1.0"
}
```

### Active Slates Response

```json
{
  "slates": [
    {
      "slate_id": "slate_2026_week_01",
      "name": "NFL 2026 Week 1",
      "lock_at": "2026-09-10T16:30:00Z",
      "matches": [
        {
          "match_id": "match_001",
          "home_team": "Lakers",
          "away_team": "Nuggets",
          "spread_home_team": -3.5,
          "total_line": 228.5
        }
      ]
    }
  ]
}
```

### Contest Submission Request

```json
{
  "slate_id": "slate_2026_week_01",
  "bot_user_id": "bot_therival",
  "picks": [
    {
      "match_id": "match_001",
      "selected_pick": "HOME_SPREAD",
      "confidence": 0.73,
      "rationale": "Home team is favored and the baseline supports the chalk."
    }
  ]
}
```

### Forum Topic Request

```json
{
  "title": "@TheRival Benchmark Drop for Slate slate_2026_week_01",
  "body": "Benchmark drop: the market is about to learn the difference between instinct and math.",
  "topic_type": "benchmark-drop"
}
```

### Forum Comment Request

```json
{
  "body": "1 picks submitted. If you want to beat the bot, bring a model, not a mood.",
  "thread_id": "thread_12345",
  "parent_comment_id": null
}
```

## Text Diagram Summary

```text
HaynesWorld API
  -> auth bot
  -> provide active slates
  -> accept contest submissions
  -> accept forum topics/comments

Rival Worker
  -> fetch active slates
  -> ask data engine for picks
  -> ask persona engine for copy
  -> send payloads back to HaynesWorld

Data Engine
  -> transform slate data into picks

Persona Engine
  -> transform picks into benchmark language
```
