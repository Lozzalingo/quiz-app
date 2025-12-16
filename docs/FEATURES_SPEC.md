# Features Specification

This document describes the features and business logic of the Quiz App.

---

## User Roles

### Admin
- Single admin account (username: admin)
- Can create and manage multiple games
- Can create rounds and questions
- Can open/close rounds in real-time
- Can view and grade all answers
- Can add bonus/penalty points

### Team (Player)
- Created per-game (same team name can exist in different games)
- Can join games via code or QR scan
- Can submit answers to open rounds
- Cannot change answers after submission
- Cannot access closed rounds

---

## Game Management

### Creating a Game

1. Admin logs in and clicks "Create New Game"
2. Enters game name (e.g., "Friday Night Quiz")
3. System generates:
   - Unique 6-character code (alphanumeric, excludes confusing chars)
   - QR code image linking to join URL
4. Game is created as active

**Game Code Format:**
- 6 characters
- Uses: ABCDEFGHJKMNPQRSTUVWXYZ23456789
- Excludes: 0, O, I, 1, L (to avoid confusion)

### Game States

| State | Description | Teams Can Join | Teams Can Play |
|-------|-------------|----------------|----------------|
| Active | Normal state | Yes | Yes |
| Inactive | Manually disabled | No | Yes (existing teams) |
| Deleted | Removed | No | No |

---

## Round Management

### Creating a Round

1. Admin selects a game
2. Clicks "Add Round"
3. Enters round name (e.g., "History", "Music Trivia")
4. Round created with:
   - Order number (auto-incremented)
   - Empty questions array
   - Closed status (default)

### Round States

| State | Description | Players See | Players Can Submit |
|-------|-------------|-------------|-------------------|
| Closed | Default state | Round name | No |
| Open | Accepting answers | Questions | Yes |
| Submitted | Team submitted | "Submitted" badge | No |

---

## Question Builder

### Question Types

#### Text Input
```json
{
  "id": "q1",
  "text": "What is the capital of France?",
  "type": "text",
  "validation": "^[Pp]aris$",
  "points": 1
}
```

#### Number Input
```json
{
  "id": "q2",
  "text": "How many continents are there?",
  "type": "number",
  "validation": "answer * 10",
  "points": 1
}
```

#### Radio (Multiple Choice)
```json
{
  "id": "q3",
  "text": "Which planet is known as the Red Planet?",
  "type": "radio",
  "options": ["Earth", "Mars", "Venus", "Jupiter"],
  "correct_answer": "Mars",
  "points": 1
}
```

### Question Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | Yes | Unique identifier within round |
| text | string | Yes | Question text displayed to players |
| type | string | Yes | "text", "number", or "radio" |
| validation | string | No | Regex pattern or math formula |
| points | number | No | Base points (default: 1) |
| options | array | Radio only | Answer choices |
| correct_answer | string | Radio only | Correct option |

---

## Answer Validation

### Text Validation (Regex)

Text answers are validated against regex patterns.

**Single Pattern:**
```
^[Pp]aris$
```
Matches: "Paris", "paris"

**OR Logic (/):**
```
^[Pp]aris$ / ^[Ll]ondon$
```
Matches: "Paris", "paris", "London", "london"

**AND Logic (+):**
```
.*capital.* + .*France.*
```
Matches: "The capital of France is Paris"

**Validation Rules:**
- Case-insensitive by default
- Uses Python `re.search()` (partial match unless anchored)
- Invalid regex falls back to literal string match

### Number Validation (Math Formula)

Number answers can use math formulas for dynamic scoring.

**Simple Scoring:**
```
answer * 4
```
If answer is 10, score is 40

**Complex Formula:**
```
answer / 2 + 10
```
If answer is 20, score is 20

**Supported Operations:**
- Basic: +, -, *, /
- Functions: abs(), min(), max(), round()
- Variable: `answer` (the submitted value)

**Safety:**
- Formulas are sandboxed (no imports, exec, etc.)
- Division by zero returns 0
- Invalid formulas return 0

### Radio Validation

Radio answers are compared to the `correct_answer` field.

- Case-insensitive comparison
- Whitespace trimmed
- Exact match required

---

## Scoring System

### Auto-Scoring

When a team submits answers:

1. **Text questions:**
   - If regex matches: award `points` value
   - If no match: 0 points

2. **Number questions:**
   - If formula provided: calculate using formula
   - If no formula: award `points` if valid number

3. **Radio questions:**
   - If matches `correct_answer`: award `points`
   - If no match: 0 points

### Manual Adjustments

Admins can adjust scores in the spreadsheet:

| Field | Description |
|-------|-------------|
| points | Auto-calculated, but editable |
| bonus_points | Extra points (positive) |
| penalty_points | Deductions (positive number) |
| notes | Admin comments |

**Total Calculation:**
```
total = points + bonus_points - penalty_points
```

---

## Real-Time Features

### Socket.IO Integration

The app uses Socket.IO for real-time updates:

1. **Player joins game:**
   - Connects to Socket.IO server
   - Joins room `game_{game_id}`

2. **Admin opens/closes round:**
   - Triggers `round_status_changed` event
   - All players in game room receive update
   - UI updates without page refresh

3. **Timer starts:**
   - Admin sets duration (30s, 60s, 120s, or custom)
   - Triggers `timer_started` event
   - All players see countdown
   - Round auto-closes when timer expires

4. **Real-time spreadsheet sync:**
   - Admin joins `spreadsheet_{game_id}` room
   - Score changes broadcast to all admins viewing spreadsheet
   - Changes appear instantly with visual highlight
   - New team submissions auto-refresh the grid

### Timer Workflow

1. Admin clicks "Start Timer" with duration
2. Server broadcasts `timer_started` with end time
3. All clients show countdown
4. When timer reaches 0:
   - Round is auto-closed
   - `round_closed` event broadcast
   - Players can no longer submit

### Spreadsheet Real-Time Sync

When multiple admins view the spreadsheet simultaneously:

1. Each admin joins the `spreadsheet_{game_id}` Socket.IO room
2. When any admin edits a score (points, bonus, penalty, notes):
   - Change is saved to database via API
   - API broadcasts `score_updated` event to room
   - All other admins see the update instantly
   - Updated row flashes green to indicate change
3. When a team submits answers:
   - `submission_update` event triggers
   - Spreadsheet auto-reloads to show new data

---

## Team Workflow

### Joining a Game

1. **Via QR Code:**
   - Scan QR code with phone camera
   - Opens `/player/join/{code}` URL
   - Redirects to login

2. **Via Code Entry:**
   - Go to player login page
   - Enter 6-character game code
   - Enter team name and password

### Team Creation vs Login

**New Team:**
- Team name doesn't exist for this game
- Password becomes the team password
- Team created and logged in

**Existing Team:**
- Team name exists for this game
- Must enter correct password
- Logged in if password matches

### Submitting Answers

1. View open round
2. Fill in all question fields
3. Click "Submit"
4. **One submission per round** - cannot edit after submit

### Restrictions

- Cannot submit to closed rounds
- Cannot submit twice to same round
- Cannot access other teams' answers
- Cannot access games they're not registered for

---

## Admin Spreadsheet

### Grid Layout

- **Tabulator.js** powered grid
- **One row per team** - teams sorted by total score (highest first)
- Columns organized as:
  - Position (#)
  - Team Name
  - Total Score
  - Total Bonus
  - For each round:
    - Each question's answer text
    - Each question's points (editable)
    - Round total

### Example Layout

```
#  | Team Name      | Total | Bonus | Q1 Answer | Pts | Q2 Answer | Pts | Round 1 Total | ...
1  | Quiz Masters   | 56    | 5     | Paris     | 1   | 1789      | 1   | 10            | ...
2  | Trivia Kings   | 48    | 0     | paris     | 1   | 1788      | 0   | 8             | ...
```

### Inline Editing

Click on point cells to edit scores:
- Points update immediately via API
- Totals recalculate automatically
- Changes sync in real-time to other admins viewing the spreadsheet

### Features

- Frozen position and team name columns (always visible when scrolling)
- Hover over question headers to see full question text
- Color-coded columns:
  - Green: Position and total score
  - Orange: Individual question points
  - Blue: Round totals
- Real-time sync via Socket.IO
- CSV export with all data

### Export

- Click "Export to CSV" to download
- Includes all teams and all answers in spreadsheet format

---

## Security Considerations

### Authentication

- **Passwords:** Hashed with Werkzeug (pbkdf2:sha256)
- **Sessions:** Flask-Login with secure cookies
- **CSRF:** Flask-WTF protection on all forms

### Authorization

- Admin routes check `admin_` prefix in user ID
- Team routes check `team_` prefix in user ID
- Teams can only access their own game

### Input Validation

- Server-side validation on all inputs
- Regex patterns executed safely (re module)
- Math formulas sandboxed (limited eval)
- SQL injection prevented by SQLAlchemy ORM

### Rate Limiting

Consider adding Flask-Limiter for production:
- Login attempts
- API endpoints
- Form submissions

---

## Edge Cases

### Team Name Conflicts

- Team names are unique per game only
- "Team A" in Game 1 is different from "Team A" in Game 2
- Enforced by database constraint

### Simultaneous Submissions

- PostgreSQL handles concurrent writes
- First valid submission wins
- Duplicate check before insert prevents double submission

### Round Closes During Submission

- Server checks `is_open` before saving answers
- If round closed between form load and submit, submission rejected
- Clear error message shown

### Timer Sync Issues

- Timer uses server time as source of truth
- Clients sync on timer start event
- Small desync acceptable (server enforces closure)

### Empty Answers

- Empty strings are valid submissions
- Score 0 points but still count as submitted
- Team cannot re-submit

---

## Planned Enhancements

Future features to consider:

- [ ] Multiple admin users with roles
- [ ] Round templates (save/reuse questions)
- [ ] Image/audio/video questions
- [ ] Leaderboard display page
- [ ] Export results to PDF
- [ ] Email notifications
- [ ] Dark mode theme
- [ ] Internationalization
