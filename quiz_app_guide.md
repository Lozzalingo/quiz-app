# Quiz App - Master Project Plan

## Overview
This is a Flask-based quiz application that replicates Google Forms functionality with additional features: timed rounds, team management, and spreadsheet-style answer grading.

---

## Project Structure

```
quiz-app/
├── README.md                           # Project overview and setup instructions
├── TODO.md                             # Development checklist
├── INSTRUCTIONS_FOR_AI.md              # Instructions for AI coding assistant
├── requirements.txt                    # Python dependencies
├── .env                                # Environment variables (not in git)
├── .gitignore                          # Git ignore file
├── config.py                           # Flask configuration
├── app.py                              # Main Flask application entry point
├── models.py                           # Database models (SQLAlchemy)
├── forms.py                            # WTForms form definitions
├── utils.py                            # Helper functions (QR, regex, math)
│
├── docs/                               # Documentation folder
│   ├── DATABASE_SCHEMA.md              # Database design and relationships
│   ├── ROUTES_SPEC.md                  # All routes and endpoints
│   ├── FEATURES_SPEC.md                # Detailed feature specifications
│   └── DEPLOYMENT.md                   # Deployment instructions
│
├── routes/                             # Route blueprints
│   ├── __init__.py                     # Blueprint registration
│   ├── auth.py                         # Authentication routes
│   ├── player.py                       # Player-facing routes
│   ├── admin.py                        # Admin dashboard routes
│   └── api.py                          # JSON API endpoints
│
├── templates/                          # Jinja2 templates
│   ├── base.html                       # Base layout with nav
│   ├── index.html                      # Landing page
│   │
│   ├── player/                         # Player templates
│   │   ├── login.html                  # Team login/signup
│   │   └── quiz.html                   # Quiz interface
│   │
│   └── admin/                          # Admin templates
│       ├── login.html                  # Admin login
│       ├── dashboard.html              # Game list
│       ├── create_game.html            # Create new game
│       ├── edit_game.html              # Edit game settings
│       ├── manage_rounds.html          # Round management
│       ├── edit_questions.html         # Form builder UI
│       ├── spreadsheet.html            # Answer grid view
│       └── live_control.html           # Timer & round control
│
├── static/                             # Static files
│   ├── css/
│   │   ├── style.css                   # Main styles
│   │   └── admin.css                   # Admin-specific styles
│   │
│   ├── js/
│   │   ├── quiz_form.js                # Dynamic form rendering (player)
│   │   ├── form_builder.js             # Form builder (admin)
│   │   ├── spreadsheet.js              # Grid view with Tabulator
│   │   ├── timer.js                    # Real-time timer (Socket.IO)
│   │   └── validation.js               # Client-side validation
│   │
│   └── qrcodes/                        # Generated QR codes (git ignored)
│
├── instance/                           # Instance-specific files (Flask config)
│
├── migrations/                         # Database migrations (Flask-Migrate)
│   └── versions/                       # Migration versions
│
└── tests/                              # Test files (optional)
    ├── test_models.py
    ├── test_routes.py
    └── test_utils.py
```

---

## Core Features Summary

### Player Features
1. Team signup/login with game code
2. View available rounds
3. Submit answers to open rounds (one submission per round)
4. Cannot edit after submission
5. Real-time updates when admin closes rounds

### Admin Features
1. Create games (generates QR code)
2. Create rounds within games
3. Build questions with form editor (text, number, radio buttons)
4. Define answer validation (regex patterns, math formulas)
5. Open/close rounds manually or with timer
6. View all answers in spreadsheet format
7. Edit scores (auto-calculated + manual bonus/penalty)
8. Export results

---

## Technology Stack

**Backend:**
- Python 3.11+
- Flask (web framework)
- SQLAlchemy (ORM)
- PostgreSQL (database - handles concurrent writes perfectly)
- Flask-Login (session management)
- Flask-SocketIO (real-time updates)
- Flask-WTF (forms)
- Flask-Migrate (database migrations)

**Frontend:**
- Jinja2 templates (server-side rendering)
- Vanilla JavaScript (minimal dependencies)
- Socket.IO client (real-time)
- Tabulator.js (spreadsheet grid)
- Pico CSS or Bulma (lightweight styling)

**Database:**
- PostgreSQL (production-ready, excellent concurrency support)

**Additional Libraries:**
- qrcode + Pillow (QR generation)
- python-dotenv (environment variables)
- psycopg2 (PostgreSQL adapter)

---

## Development Phases

### Phase 1: Project Setup & Database
- Initialize project structure
- Install dependencies
- Create database models
- Set up migrations
- Create configuration files

### Phase 2: Authentication System
- Admin login
- Team signup/login
- Session management
- Route protection

### Phase 3: Game Management (Admin)
- Create games
- Generate QR codes
- Create rounds
- Question form builder

### Phase 4: Quiz Interface (Player)
- Game join flow
- Display questions
- Submit answers
- Round restrictions

### Phase 5: Spreadsheet View (Admin)
- Display all answers
- Inline editing
- Score calculation
- Bonus/penalty points

### Phase 6: Real-time Features
- Socket.IO setup
- Timer functionality
- Round closing
- Player notifications

### Phase 7: Testing & Refinement
- Test all flows
- Fix bugs
- Improve UX
- Add error handling

### Phase 8: Deployment
- Prepare for production
- Deploy to server
- Set up backups
- Documentation

---

## Getting Started

1. Read `README.md` for setup instructions
2. Review `TODO.md` for development checklist
3. Read `INSTRUCTIONS_FOR_AI.md` for AI assistant guidance
4. Review documentation in `docs/` folder
5. Begin with Phase 1 in `TODO.md`

---

## Notes for Development

- Start with minimal features, iterate
- Test each phase before moving forward
- Update TODO.md after completing each task
- Keep database migrations organized
- Document complex logic in code comments
- Prioritize working features over polish initially
- PostgreSQL handles concurrent writes well - no need for special locking logic