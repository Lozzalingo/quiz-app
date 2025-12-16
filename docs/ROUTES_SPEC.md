# Routes Specification

This document describes all URL routes in the Quiz App.

---

## Overview

Routes are organized into four blueprints:

| Blueprint | Prefix | Description |
|-----------|--------|-------------|
| auth | /auth | Authentication (login/logout) |
| admin | /admin | Admin game management |
| player | /player | Player quiz interface |
| api | /api | JSON API endpoints |

---

## Public Routes

### Home Page

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/` | Landing page with links to admin/player login |

---

## Auth Blueprint (`/auth`)

### Admin Authentication

| Method | URL | Description | Response |
|--------|-----|-------------|----------|
| GET | `/auth/admin/login` | Show admin login form | HTML form |
| POST | `/auth/admin/login` | Process admin login | Redirect to dashboard or error |

**POST Parameters:**
- `username`: Admin username
- `password`: Admin password

---

### Player Authentication

| Method | URL | Description | Response |
|--------|-----|-------------|----------|
| GET | `/auth/player/login` | Show player login form | HTML form |
| GET | `/auth/player/login/<game_code>` | Login with pre-filled game code | HTML form |
| POST | `/auth/player/login` | Process player login/signup | Redirect to quiz or error |

**POST Parameters:**
- `game_code`: 6-character game code
- `team_name`: Team display name
- `password`: Team password
- `password_confirm`: Password confirmation (for new teams)

**Behavior:**
- If team name exists for game: verify password and log in
- If team name is new: create team and log in

---

### Player Re-login

| Method | URL | Description | Response |
|--------|-----|-------------|----------|
| GET | `/auth/player/relogin/<game_code>` | Show simplified login (existing teams) | HTML form |
| POST | `/auth/player/relogin/<game_code>` | Process re-login | Redirect to quiz or error |

**POST Parameters:**
- `team_name`: Team name
- `password`: Team password

---

### Logout

| Method | URL | Auth Required | Description |
|--------|-----|---------------|-------------|
| GET | `/auth/logout` | Yes | Log out current user (admin or team) |

---

## Admin Blueprint (`/admin`)

All routes require admin authentication.

### Dashboard

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/admin/dashboard` | List all games |

---

### Game Management

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/admin/create_game` | Show create game form |
| POST | `/admin/create_game` | Create new game |
| GET | `/admin/game/<game_id>/edit` | Show game details and rounds |
| POST | `/admin/game/<game_id>/toggle_active` | Toggle game active status |
| POST | `/admin/game/<game_id>/delete` | Delete game and all data |

**Create Game POST Parameters:**
- `name`: Game name (3-100 characters)

---

### Round Management

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/admin/game/<game_id>/create_round` | Show create round form |
| POST | `/admin/game/<game_id>/create_round` | Create new round |
| GET | `/admin/round/<round_id>/edit_questions` | Question form builder |
| POST | `/admin/round/<round_id>/delete` | Delete round and answers |

**Create Round POST Parameters:**
- `name`: Round name (2-100 characters)

---

### Live Control

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/admin/game/<game_id>/live_control` | Real-time round control panel |

**Features:**
- Open/close rounds
- Start timer with countdown
- View submission counts

---

### Spreadsheet

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/admin/game/<game_id>/spreadsheet` | View/edit all answers in grid |

**Features:**
- Tabulator.js grid with all team answers
- Inline editing of scores
- Filter by round/team
- Export to CSV

---

## Player Blueprint (`/player`)

### Join Game

| Method | URL | Auth Required | Description |
|--------|-----|---------------|-------------|
| GET | `/player/join/<game_code>` | No | Join game (from QR code) |

**Behavior:**
- Validates game exists and is active
- Redirects to login if not authenticated
- Redirects to quiz if already logged in for this game

---

### Quiz Interface

| Method | URL | Auth Required | Description |
|--------|-----|---------------|-------------|
| GET | `/player/quiz/<game_code>` | Team | Main quiz page |

**Displays:**
- List of all rounds
- Round status (open/closed/submitted)
- Links to answer open rounds

---

### View Round

| Method | URL | Auth Required | Description |
|--------|-----|---------------|-------------|
| GET | `/player/round/<round_id>` | Team | View questions for a round |

**Validation:**
- Team must belong to the game
- Round must be open
- Team must not have already submitted

---

### Submit Answers

| Method | URL | Auth Required | Description |
|--------|-----|---------------|-------------|
| POST | `/player/submit_round/<round_id>` | Team | Submit answers |

**POST Parameters:**
- `answer_{question_id}`: Answer for each question

**Validation:**
- Team must belong to the game
- Round must be open
- Team must not have already submitted

**Behavior:**
- Creates Answer records for each question
- Auto-calculates points based on validation rules
- Emits Socket.IO event for real-time update

---

## API Blueprint (`/api`)

All routes return JSON. Admin routes require admin authentication.

### Questions API

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| GET | `/api/round/<round_id>/questions` | Admin | Get questions JSON |
| POST | `/api/round/<round_id>/questions` | Admin | Update questions JSON |

**GET Response:**
```json
{
  "success": true,
  "questions": [...]
}
```

**POST Body:**
```json
{
  "questions": [...]
}
```

---

### Round Control API

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| POST | `/api/round/<round_id>/toggle` | Admin | Toggle round open/closed |

**Response:**
```json
{
  "success": true,
  "is_open": true
}
```

**Side Effects:**
- Emits `round_status_changed` Socket.IO event
- Emits `round_closed` event when closing

---

### Answers API

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| GET | `/api/game/<game_id>/answers` | Admin | Get all answers for spreadsheet (team rows) |
| POST | `/api/answer/<answer_id>/score` | Admin | Update answer score |

**GET /answers Response:**

Returns one row per team with all answers organized by round.

```json
{
  "success": true,
  "columns": [
    {
      "round_id": 1,
      "round_name": "History",
      "questions": [
        {"id": "q1", "text": "Capital of France?", "type": "text"},
        {"id": "q2", "text": "Year of Revolution?", "type": "number"}
      ]
    }
  ],
  "teams": [
    {
      "position": 1,
      "team_id": 1,
      "team_name": "Quiz Masters",
      "total_score": 56,
      "total_bonus": 5,
      "total_penalty": 0,
      "rounds": {
        "1": {
          "round_points": 10,
          "answers": {
            "q1": {"answer_id": 1, "text": "Paris", "points": 1, "bonus": 0, "penalty": 0},
            "q2": {"answer_id": 2, "text": "1789", "points": 1, "bonus": 0, "penalty": 0}
          }
        }
      }
    }
  ]
}
```

**POST /score Body:**
```json
{
  "points": 1.0,
  "bonus_points": 0.5,
  "penalty_points": 0.0,
  "notes": "Good answer!"
}
```

**Side Effects:**
- Emits `score_updated` Socket.IO event to `spreadsheet_{game_id}` room

---

### Teams API

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| GET | `/api/game/<game_id>/teams` | Admin | Get all teams for a game |

**Response:**
```json
{
  "success": true,
  "teams": [
    {
      "id": 1,
      "name": "Team A",
      "created_at": "2025-01-01T12:00:00"
    }
  ]
}
```

---

### Leaderboard API

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| GET | `/api/game/<game_id>/leaderboard` | None | Get public leaderboard |

**Response:**
```json
{
  "success": true,
  "leaderboard": [
    {"team_name": "Team A", "total_points": 25.0},
    {"team_name": "Team B", "total_points": 20.0}
  ]
}
```

---

## Socket.IO Events

### Client to Server

| Event | Data | Description |
|-------|------|-------------|
| `join_game` | `{game_id: int}` | Join game room for player updates |
| `join_admin` | `{game_id: int}` | Join game room for admin control |
| `join_spreadsheet` | `{game_id: int}` | Join spreadsheet room for real-time sync |
| `timer_started` | `{game_id: int, seconds: int}` | Start countdown timer |
| `timer_stopped` | `{game_id: int}` | Stop countdown timer |

### Server to Client

| Event | Data | Description |
|-------|------|-------------|
| `joined_game` | `{game_id: int}` | Confirmation of joining game room |
| `joined_spreadsheet` | `{game_id: int}` | Confirmation of joining spreadsheet room |
| `round_status_changed` | `{round_id: int, is_open: bool}` | Round opened/closed |
| `round_closed` | `{round_id: int}` | Round was closed |
| `timer_started` | `{seconds: int}` | Timer countdown started |
| `timer_stopped` | `{}` | Timer was stopped |
| `submission_update` | `{round_id: int, submissions: int, total_teams: int}` | New submission received |
| `score_updated` | `{answer_id: int, points: float, bonus_points: float, penalty_points: float, notes: str, total: float}` | Score changed in spreadsheet |

### Rooms

| Room Name | Participants | Purpose |
|-----------|--------------|---------|
| `game_{game_id}` | Players and admins | Round status, timer updates |
| `admin_{game_id}` | Admins only | Admin-specific notifications |
| `spreadsheet_{game_id}` | Admins viewing spreadsheet | Real-time score sync |

---

## Error Responses

### HTML Routes

Flash messages with categories:
- `success`: Green - operation succeeded
- `info`: Blue - informational
- `warning`: Yellow - caution
- `danger`: Red - error

### API Routes

```json
{
  "success": false,
  "error": "Error message here"
}
```

HTTP Status Codes:
- `200`: Success
- `400`: Bad request (missing/invalid data)
- `403`: Forbidden (not authorized)
- `404`: Not found
