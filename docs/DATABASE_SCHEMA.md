# Database Schema

This document describes the PostgreSQL database schema for the Quiz App.

---

## Tables Overview

| Table | Description |
|-------|-------------|
| admin | Administrator users who manage games |
| game | Quiz games with unique codes |
| round | Rounds within a game (e.g., History, Music) |
| team | Player teams (per game) |
| answer | Individual question answers with scoring |

---

## Entity Relationship Diagram

```
Admin (standalone)

Game ----< Round ----< Answer
  |                      ^
  |                      |
  +------< Team ---------+
```

- One Game has many Rounds
- One Game has many Teams
- One Round has many Answers
- One Team has many Answers
- Answer connects Team to a question in a Round

---

## Table Definitions

### admin

Administrator users who can create and manage games.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | Auto-incrementing ID |
| username | VARCHAR(80) | UNIQUE, NOT NULL | Admin username |
| password_hash | VARCHAR(256) | NOT NULL | Werkzeug password hash |

**Notes:**
- Default admin created on first run with username 'admin'
- Password set via ADMIN_PASSWORD environment variable

---

### game

Quiz games that teams can join.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | Auto-incrementing ID |
| name | VARCHAR(200) | NOT NULL | Display name of the game |
| code | VARCHAR(6) | UNIQUE, NOT NULL | 6-character join code |
| qr_code_path | VARCHAR(500) | | Relative path to QR code image |
| created_at | DATETIME | DEFAULT now() | When game was created |
| is_active | BOOLEAN | DEFAULT true | Whether game accepts new teams |

**Relationships:**
- `rounds`: One-to-many with Round (cascade delete)
- `teams`: One-to-many with Team (cascade delete)

**Notes:**
- Game code is alphanumeric, excludes confusing characters (0, O, I, 1, L)
- QR code links to `/player/join/{code}`

---

### round

Rounds within a game, each containing questions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | Auto-incrementing ID |
| game_id | INTEGER | FOREIGN KEY (game.id), NOT NULL | Parent game |
| name | VARCHAR(200) | NOT NULL | Round name (e.g., "History") |
| order | INTEGER | DEFAULT 0 | Display order within game |
| is_open | BOOLEAN | DEFAULT false | Whether teams can submit answers |
| questions_json | TEXT | NOT NULL, DEFAULT '[]' | JSON array of questions |

**Relationships:**
- `game`: Many-to-one with Game
- `answers`: One-to-many with Answer (cascade delete)

**Questions JSON Structure:**
```json
[
  {
    "id": "q1",
    "text": "What is the capital of France?",
    "type": "text",
    "validation": "^[Pp]aris$",
    "points": 1
  },
  {
    "id": "q2",
    "text": "How many continents are there?",
    "type": "number",
    "validation": "answer * 10",
    "points": 1
  },
  {
    "id": "q3",
    "text": "Which planet is red?",
    "type": "radio",
    "options": ["Earth", "Mars", "Venus"],
    "correct_answer": "Mars",
    "points": 1
  }
]
```

---

### team

Player teams that participate in games.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | Auto-incrementing ID |
| game_id | INTEGER | FOREIGN KEY (game.id), NOT NULL | Parent game |
| name | VARCHAR(100) | NOT NULL | Team display name |
| password_hash | VARCHAR(256) | NOT NULL | Werkzeug password hash |
| created_at | DATETIME | DEFAULT now() | When team registered |

**Constraints:**
- `unique_team_per_game`: UNIQUE(game_id, name) - Team names unique per game

**Relationships:**
- `game`: Many-to-one with Game
- `answers`: One-to-many with Answer (cascade delete)

---

### answer

Individual answers submitted by teams.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | Auto-incrementing ID |
| team_id | INTEGER | FOREIGN KEY (team.id), NOT NULL | Team that submitted |
| round_id | INTEGER | FOREIGN KEY (round.id), NOT NULL | Round answered |
| question_id | VARCHAR(50) | NOT NULL | Question ID from questions_json |
| answer_text | TEXT | | The submitted answer |
| submitted_at | DATETIME | DEFAULT now() | When answer was submitted |
| points | FLOAT | DEFAULT 0.0 | Auto-calculated points |
| bonus_points | FLOAT | DEFAULT 0.0 | Manual bonus from admin |
| penalty_points | FLOAT | DEFAULT 0.0 | Manual penalty from admin |
| notes | TEXT | | Admin notes about this answer |

**Relationships:**
- `team`: Many-to-one with Team
- `round`: Many-to-one with Round

**Computed Property:**
- `total_points`: points + bonus_points - penalty_points

---

## Common Queries

### Get all teams and their total scores for a game

```sql
SELECT
    t.name as team_name,
    COALESCE(SUM(a.points + a.bonus_points - a.penalty_points), 0) as total_score
FROM team t
LEFT JOIN answer a ON t.id = a.team_id
WHERE t.game_id = :game_id
GROUP BY t.id, t.name
ORDER BY total_score DESC;
```

### Get all answers for a round

```sql
SELECT
    t.name as team_name,
    a.question_id,
    a.answer_text,
    a.points,
    a.bonus_points,
    a.penalty_points
FROM answer a
JOIN team t ON a.team_id = t.id
WHERE a.round_id = :round_id
ORDER BY t.name, a.question_id;
```

### Check if team has submitted for a round

```sql
SELECT EXISTS(
    SELECT 1 FROM answer
    WHERE team_id = :team_id AND round_id = :round_id
);
```

### Get open rounds for a game

```sql
SELECT id, name, order
FROM round
WHERE game_id = :game_id AND is_open = true
ORDER BY order;
```

---

## Indexes

The following indexes are automatically created by SQLAlchemy:

- `admin.username` - UNIQUE index
- `game.code` - UNIQUE index
- `team(game_id, name)` - UNIQUE composite index

Consider adding these indexes for performance on large datasets:

```sql
CREATE INDEX idx_answer_team_round ON answer(team_id, round_id);
CREATE INDEX idx_round_game ON round(game_id);
CREATE INDEX idx_team_game ON team(game_id);
```

---

## Migration Commands

```bash
# Initialize migrations (first time only)
flask db init

# Create migration after model changes
flask db migrate -m "Description of changes"

# Apply migrations to database
flask db upgrade

# Rollback last migration
flask db downgrade
```

---

## Backup and Restore

### Backup

```bash
pg_dump quiz_app > backup_$(date +%Y%m%d).sql
```

### Restore

```bash
psql quiz_app < backup_20250101.sql
```

---

## Notes

- All timestamps are stored in UTC
- Password hashes use Werkzeug's `generate_password_hash` (pbkdf2:sha256)
- JSON data is stored as TEXT and parsed in Python
- Cascade deletes ensure no orphaned records
- Answer table changes are broadcast via Socket.IO for real-time spreadsheet sync
- Multiple admins can edit scores simultaneously; changes sync in real-time
