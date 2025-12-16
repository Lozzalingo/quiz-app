# Quiz App

A Flask-based quiz platform that combines the simplicity of Google Forms with advanced features like timed rounds, team management, and spreadsheet-style answer grading.

---

## What This App Does

**For Players:**
- Join quiz games with a game code or QR scan
- Create a team with unique name and password
- Answer quiz questions in timed rounds
- Submit answers once per round (no going back)
- See which rounds are open/closed in real-time

**For Admins:**
- Create quiz games and generate QR codes for easy access
- Design rounds (e.g., History, Music, Science)
- Build custom question forms (text input, numbers, multiple choice)
- Define answer validation with regex patterns or math formulas
- Control rounds with manual close or countdown timer
- View all team answers in spreadsheet format
- Grade answers with auto-scoring and manual adjustments
- Add bonus/penalty points per team

---

## Key Features

### Google Forms-Style Interface
- Clean, simple form UI for players
- Form builder for admins to create questions
- Supports text, number, and radio button inputs

### Advanced Validation
- **Text answers:** Validate with regex patterns (e.g., accept "Paris" or "paris" or "PARIS")
- **Multiple valid answers:** Use OR logic (`pattern1 / pattern2`) or AND logic (`pattern1 + pattern2`)
- **Math-based scoring:** Calculate points based on numeric answers (e.g., `answer * 4`)
- **Conditional scoring:** Different points based on other answers (e.g., if color is "red" multiply by 4, else by 2)

### Real-Time Round Control
- Admin can open/close rounds manually
- Timer feature with countdown (e.g., 1 minute warning)
- Socket.IO pushes updates to all connected players instantly
- Players locked out after round closes

### Spreadsheet-Style Grading
- View all teams and answers in a grid (like Google Sheets)
- Inline editing of scores
- Auto-calculated points based on validation
- Manual bonus/penalty columns
- Admin notes per answer

---

## Installation

### Prerequisites
- Python 3.11 or higher
- PostgreSQL 14 or higher
- pip (Python package manager)
- Virtual environment (recommended)

### Setup Steps

1. **Clone or download this project:**
```bash
cd quiz-app
```

2. **Create and activate virtual environment:**
```bash
python -m venv venv

# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Set up PostgreSQL database:**
```bash
# Create a database for the app
createdb quiz_app

# Or using psql:
psql -U postgres
CREATE DATABASE quiz_app;
\q
```

5. **Create environment file:**
```bash
# Create .env file in root directory
touch .env
```

Add these variables to `.env`:
```
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=your-secret-key-change-this-in-production
ADMIN_PASSWORD=admin123
BASE_URL=http://localhost:5777
DATABASE_URL=postgresql://username:password@localhost:5432/quiz_app
```

6. **Initialize database:**
```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

6. **Run the application:**
```bash
python app.py
```

The app will be available at `http://localhost:5777`

---

## Default Credentials

**Admin Login:**
- Username: `admin`
- Password: `admin123` (or whatever you set in `.env`)

**Change the admin password immediately in production!**

---

## Usage Guide

### For Admins

1. **Log in to admin panel:**
   - Go to `/auth/admin/login`
   - Use default credentials

2. **Create a game:**
   - Click "Create New Game"
   - Enter game name (e.g., "Friday Night Quiz")
   - System generates a unique 6-character code and QR code

3. **Create rounds:**
   - Select your game
   - Click "Add Round"
   - Name it (e.g., "History Round", "Music Round")

4. **Build questions:**
   - Click "Edit Questions" on a round
   - Add questions with form builder:
     - Choose type (text, number, radio)
     - Write question text
     - For text: define regex validation pattern
     - For numbers: define math formula for scoring

5. **Manage the game:**
   - Go to "Live Control" panel
   - Open rounds when ready
   - Start timer (optional) or close manually
   - View "Spreadsheet" to see all answers and grade

6. **Grade answers:**
   - Open spreadsheet view
   - Scores auto-calculate based on your rules
   - Add bonus/penalty points manually
   - Add notes for teams

### For Players

1. **Join a game:**
   - Scan QR code or go to `/player/join/GAMECODE`
   - Enter team name (must be unique for that game)
   - Create password (used to log back in if disconnected)

2. **Take the quiz:**
   - See list of rounds
   - Open rounds are highlighted
   - Click to view questions
   - Fill out all answers
   - Submit (cannot change after submission)

3. **Wait for next round:**
   - Page updates in real-time
   - New rounds appear when admin opens them
   - Timer shows countdown when admin activates it

---

## Project Structure Explained

```
quiz-app/
├── app.py                 # Flask app initialization, SocketIO setup
├── models.py              # Database tables (Game, Round, Team, Answer, Admin)
├── forms.py               # Form definitions for login, game creation
├── utils.py               # Helper functions (QR generation, regex validation, math)
├── config.py              # Flask configuration (database, secret key)
│
├── routes/                # URL routing logic
│   ├── auth.py            # Login/logout for admin and players
│   ├── player.py          # Player quiz interface
│   ├── admin.py           # Admin dashboard and game management
│   └── api.py             # JSON endpoints for AJAX/real-time updates
│
├── templates/             # HTML templates (Jinja2)
│   ├── base.html          # Base layout with navigation
│   ├── player/            # Player-facing pages
│   └── admin/             # Admin-facing pages
│
├── static/                # CSS, JavaScript, QR codes
│   ├── css/               # Stylesheets
│   ├── js/                # Client-side JavaScript
│   └── qrcodes/           # Generated QR codes (auto-created)
│
└── instance/              # Flask instance folder
```

---

## Database Schema Overview

**Admin:** Admin user accounts
**Game:** Quiz games with unique codes
**Round:** Rounds within a game (e.g., "History", "Music")
**Team:** Player teams (per game)
**Answer:** Individual question answers with scoring

See `docs/DATABASE_SCHEMA.md` for detailed schema.

All data is stored in PostgreSQL, which handles concurrent writes from multiple teams efficiently.

---

## Development Workflow

1. Read `TODO.md` for task checklist
2. Review relevant documentation in `docs/`
3. Implement features phase by phase
4. Test each feature before proceeding
5. Update `TODO.md` to mark completed tasks
6. Commit changes with clear messages

---

## Testing

### Manual Testing Checklist
- [ ] Admin can create game
- [ ] QR code generates correctly
- [ ] Players can join with game code
- [ ] Team names must be unique
- [ ] Players can submit answers
- [ ] Players cannot submit twice
- [ ] Admin can open/close rounds
- [ ] Timer closes rounds automatically
- [ ] Spreadsheet displays all answers
- [ ] Scoring calculates correctly
- [ ] Admin can add bonus/penalty points

### Automated Tests (Optional)
```bash
pytest tests/
```

---

## Deployment

See `docs/DEPLOYMENT.md` for production deployment instructions.

**Quick deployment options:**
- **VPS:** DigitalOcean, Linode, Hetzner
- **PaaS:** Railway, Render, PythonAnywhere
- **Docker:** Use provided Dockerfile (coming soon)

**Important for production:**
- Change `SECRET_KEY` in `.env`
- Change admin password
- Use strong PostgreSQL password
- Set up HTTPS (use Caddy or Nginx with Let's Encrypt)
- Enable database backups (PostgreSQL dumps)
- Set up connection pooling for high traffic

---

## Troubleshooting

### PostgreSQL connection errors
- Check PostgreSQL is running: `pg_isready`
- Verify DATABASE_URL in .env is correct
- Check username/password are correct
- Ensure database exists: `psql -l`

### Database migration errors
- Delete migrations/ folder and start over if needed
- Check PostgreSQL permissions
- Verify SQLAlchemy models are correct

### QR codes not generating
- Check `static/qrcodes/` folder exists and is writable
- Check Pillow library installed correctly

### Socket.IO not updating
- Check Flask-SocketIO and python-socketio versions match
- Check firewall allows WebSocket connections
- Check browser console for errors

### Players can submit after round closed
- Check Socket.IO connection is working
- Implement server-side validation (already in routes/player.py)

---

## Contributing

This is a personal project, but suggestions welcome:
1. Review code
2. Test features
3. Submit issues for bugs
4. Suggest improvements

---

## License

[Choose your license - MIT, GPL, etc.]

---

## Credits

Built with:
- Flask (web framework)
- SQLAlchemy (database ORM)
- Socket.IO (real-time updates)
- Tabulator (spreadsheet grid)
- QRCode (QR generation)

Inspired by Google Forms but with quiz-specific features.

---

## Support

For questions or issues:
1. Check documentation in `docs/` folder
2. Review TODO.md for known issues
3. Check troubleshooting section above
4. [Add contact method or issue tracker]

---

**Ready to build your quiz? Start with `TODO.md` and follow the phases!**