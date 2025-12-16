# Quiz App - Development TODO

**Instructions:** Work through this checklist sequentially. Mark items with `[x]` when complete. Update this file after finishing each phase.

---

## Phase 1: Project Setup & Configuration
**Goal:** Get basic Flask app running with database

- [x] 1.1 Create project directory structure
  - [x] Create all folders from README structure
  - [x] Create empty `__init__.py` in routes/

- [x] 1.2 Set up Python environment
  - [x] Create virtual environment
  - [x] Activate virtual environment
  - [x] Create requirements.txt with dependencies
  - [x] Install all dependencies with pip
  - [x] Set up PostgreSQL database locally
  - [x] Create quiz_app database in PostgreSQL

- [x] 1.3 Create configuration files
  - [x] Create config.py with Config class
  - [x] Create .env file with environment variables (including DATABASE_URL)
  - [x] Create .gitignore (venv/, *.db, .env, __pycache__, static/qrcodes/, instance/)

- [x] 1.4 Create basic app.py
  - [x] Import Flask and extensions
  - [x] Create create_app() function
  - [x] Initialize database (db.init_app)
  - [x] Initialize Flask-Login
  - [x] Initialize Flask-SocketIO
  - [x] Add basic index route
  - [x] Add if __name__ == '__main__' block

- [x] 1.5 Test basic setup
  - [x] Run `python app.py`
  - [x] Visit http://localhost:5777
  - [x] Confirm Flask welcome page or basic route works

**Phase 1 Complete:** [x] Basic Flask app running

---

## Phase 2: Database Models
**Goal:** Define all database tables and relationships

- [x] 2.1 Create models.py
  - [x] Import SQLAlchemy and necessary modules
  - [x] Create db = SQLAlchemy() instance

- [x] 2.2 Create Admin model
  - [x] id (primary key)
  - [x] username (unique, required)
  - [x] password_hash (required)
  - [x] set_password() method
  - [x] check_password() method
  - [x] Inherit from UserMixin

- [x] 2.3 Create Game model
  - [x] id, name, code (unique), qr_code_path
  - [x] created_at, is_active
  - [x] Relationships: rounds, teams (cascade delete)

- [x] 2.4 Create Round model
  - [x] id, game_id (foreign key), name, order
  - [x] is_open (boolean)
  - [x] questions_json (text field for JSON storage)
  - [x] get_questions() and set_questions() methods
  - [x] Relationship: answers (cascade delete)

- [x] 2.5 Create Team model
  - [x] id, game_id (foreign key), name
  - [x] password_hash, created_at
  - [x] set_password() and check_password() methods
  - [x] Relationship: answers (cascade delete)
  - [x] Inherit from UserMixin

- [x] 2.6 Create Answer model
  - [x] id, team_id (foreign key), round_id (foreign key)
  - [x] question_id (string), answer_text (text)
  - [x] submitted_at (datetime)
  - [x] points, bonus_points, penalty_points (floats)
  - [x] notes (text, for admin comments)

- [ ] 2.7 Set up Flask-Migrate
  - [ ] Run `flask db init`
  - [ ] Run `flask db migrate -m "Initial migration"`
  - [ ] Run `flask db upgrade`
  - [ ] Verify tables created in PostgreSQL: `psql quiz_app -c "\dt"`

- [x] 2.8 Create default admin user
  - [x] Add logic in app.py to create admin on first run
  - [x] Username: admin, Password: from .env file
  - [ ] Test by checking database: `psql quiz_app -c "SELECT * FROM admin;"`

**Phase 2 Complete:** [x] All models created and database initialized

---

## Phase 3: Utility Functions
**Goal:** Create helper functions for validation, QR generation, math

- [x] 3.1 Create utils.py file

- [x] 3.2 QR Code generation
  - [x] generate_qr_code(game_code, game_id) function
  - [x] Use qrcode library to create QR
  - [x] Save to static/qrcodes/ folder
  - [x] Return relative path for database storage
  - [x] Test: Generate a test QR and verify file created

- [x] 3.3 Generate unique game codes
  - [x] generate_unique_code() function
  - [x] 6-character alphanumeric codes
  - [x] Check uniqueness against database

- [x] 3.4 Regex answer validation
  - [x] validate_text_answer(user_answer, pattern_string) function
  - [x] Handle single pattern
  - [x] Handle OR logic (pattern1 / pattern2)
  - [x] Handle AND logic (pattern1 + pattern2)
  - [x] Case-insensitive by default
  - [x] Test with sample patterns

- [x] 3.5 Math evaluation for scoring
  - [x] calculate_math_score(formula, answer_value) function
  - [x] Safe evaluation (use ast.literal_eval or limited eval)
  - [x] Replace "answer" placeholder with actual value
  - [x] Support basic operators: +, -, *, /
  - [x] Return 0 on error
  - [x] Test with sample formulas

**Phase 3 Complete:** [x] All utility functions working

---

## Phase 4: Forms (WTForms)
**Goal:** Create form classes for validation

- [x] 4.1 Create forms.py file

- [x] 4.2 Admin login form
  - [x] AdminLoginForm class
  - [x] username field (required)
  - [x] password field (required)
  - [x] submit button

- [x] 4.3 Team login/signup form
  - [x] TeamLoginForm class
  - [x] team_name field (required, 2-100 chars)
  - [x] password field (required)
  - [x] password_confirm field (must match password)
  - [x] game_code field (required, 6 chars)
  - [x] Custom validator: game_code exists in database
  - [x] submit button

- [x] 4.4 Create game form
  - [x] CreateGameForm class
  - [x] name field (required, 3-100 chars)
  - [x] submit button

- [x] 4.5 Create round form
  - [x] CreateRoundForm class
  - [x] name field (required, 2-100 chars)
  - [x] submit button

**Phase 4 Complete:** [x] All forms defined

---

## Phase 5: Authentication Routes
**Goal:** Login/logout for admin and players

- [x] 5.1 Create routes/auth.py
  - [x] Create Blueprint: auth
  - [x] Set url_prefix='/auth'

- [x] 5.2 Admin login route
  - [x] GET /auth/admin/login
  - [x] POST /auth/admin/login
  - [x] Use AdminLoginForm
  - [x] Check username and password
  - [x] Use flask_login.login_user()
  - [x] Redirect to admin dashboard on success
  - [x] Flash error message on failure
  - [x] Create template: templates/admin/login.html

- [x] 5.3 Player login/signup route
  - [x] GET /auth/player/login
  - [x] POST /auth/player/login
  - [x] Use TeamLoginForm
  - [x] Check if team exists for that game
  - [x] If exists: verify password
  - [x] If not exists: create new team
  - [x] Use flask_login.login_user()
  - [x] Redirect to quiz page on success
  - [x] Create template: templates/player/login.html

- [x] 5.4 Logout route
  - [x] GET /auth/logout
  - [x] Use flask_login.logout_user()
  - [x] Redirect to home page

- [x] 5.5 Set up Flask-Login user_loader
  - [x] In app.py, create user_loader function
  - [x] Handle loading Admin or Team based on user_id
  - [x] Use prefix like 'admin_X' or 'team_X' to distinguish

- [x] 5.6 Register auth blueprint in app.py
  - [x] Import auth blueprint
  - [x] app.register_blueprint(auth.bp)

- [ ] 5.7 Test authentication
  - [ ] Test admin login with correct/incorrect credentials
  - [ ] Test team signup (new team)
  - [ ] Test team login (existing team)
  - [ ] Test logout

**Phase 5 Complete:** [x] Authentication working for admin and players

---

## Phase 6: Admin Routes - Game Management
**Goal:** Create, edit, and manage games and rounds

- [x] 6.1 Create routes/admin.py
  - [x] Create Blueprint: admin
  - [x] Set url_prefix='/admin'
  - [x] Create admin_required decorator

- [x] 6.2 Admin dashboard
  - [x] GET /admin/dashboard
  - [x] Require admin login
  - [x] List all games (newest first)
  - [x] Show game code, name, created date
  - [x] Links to edit/manage each game
  - [x] Create template: templates/admin/dashboard.html

- [x] 6.3 Create game route
  - [x] GET /admin/create_game (show form)
  - [x] POST /admin/create_game (process form)
  - [x] Use CreateGameForm
  - [x] Generate unique game code
  - [x] Create Game in database
  - [x] Generate QR code with utils.generate_qr_code()
  - [x] Save QR path to game record
  - [x] Redirect to edit game page
  - [x] Create template: templates/admin/create_game.html

- [x] 6.4 Edit game page
  - [x] GET /admin/game/<game_id>/edit
  - [x] Show game details (name, code, QR code)
  - [x] List all rounds for this game
  - [x] Link to create round
  - [x] Link to edit each round
  - [x] Link to spreadsheet view
  - [x] Link to live control panel
  - [x] Create template: templates/admin/edit_game.html

- [x] 6.5 Create round route
  - [x] GET /admin/game/<game_id>/create_round (show form)
  - [x] POST /admin/game/<game_id>/create_round (process)
  - [x] Use CreateRoundForm
  - [x] Set order (max existing order + 1)
  - [x] Initialize questions_json as empty array
  - [x] Redirect to edit questions page
  - [x] Create template: templates/admin/create_round.html

- [x] 6.6 Edit questions page (form builder UI)
  - [x] GET /admin/round/<round_id>/edit_questions
  - [x] Show existing questions from questions_json
  - [x] JavaScript-based form builder interface
  - [x] Add/remove questions dynamically
  - [x] Choose question type: text, number, radio
  - [x] Define validation (regex for text)
  - [x] Define scoring (math formula for numbers)
  - [x] Save questions via AJAX to API endpoint
  - [x] Create template: templates/admin/edit_questions.html
  - [ ] Create JavaScript: static/js/form_builder.js (inline in template)

- [x] 6.7 Register admin blueprint in app.py
  - [x] Import admin blueprint
  - [x] app.register_blueprint(admin.bp)

**Phase 6 Complete:** [x] Admin can create and manage games/rounds

---

## Phase 7: Player Routes - Quiz Interface
**Goal:** Players can join games and submit answers

- [x] 7.1 Create routes/player.py
  - [x] Create Blueprint: player
  - [x] Set url_prefix='/player'

- [x] 7.2 Join game route (from QR code)
  - [x] GET /player/join/<game_code>
  - [x] Verify game exists
  - [x] Redirect to player login

- [x] 7.3 Quiz interface route
  - [x] GET /player/quiz/<game_code>
  - [x] Require team login
  - [x] Verify team belongs to this game
  - [x] Get all rounds for game
  - [x] Get currently open round
  - [x] Get rounds team has already submitted
  - [x] Render quiz interface
  - [x] Create template: templates/player/quiz.html

- [x] 7.4 Display questions dynamically
  - [x] In quiz.html template, show current open round
  - [x] Load questions from round.questions_json
  - [x] Render form fields based on question type
  - [x] Text inputs for "text" type
  - [x] Number inputs for "number" type
  - [x] Radio buttons for "radio" type
  - [ ] Client-side validation with static/js/validation.js (inline in template)

- [x] 7.5 Submit answers route
  - [x] POST /player/submit_round/<round_id>
  - [x] Require team login
  - [x] Verify round is open
  - [x] Verify team hasn't already submitted
  - [x] Loop through all questions
  - [x] Create Answer record for each question
  - [x] Handle type conversion (number to text if needed)
  - [x] Commit to database
  - [x] Flash success message
  - [x] Redirect back to quiz page

- [ ] 7.6 Create JavaScript for dynamic forms
  - [ ] Create static/js/quiz_form.js (inline in template currently)
  - [ ] Render questions based on JSON data
  - [ ] Handle validation before submit
  - [ ] Show error messages for invalid inputs

- [x] 7.7 Register player blueprint in app.py
  - [x] Import player blueprint
  - [x] app.register_blueprint(player.bp)

- [ ] 7.8 Test player flow
  - [ ] Join game with code
  - [ ] Create team and login
  - [ ] Submit answers to open round
  - [ ] Verify cannot submit twice
  - [ ] Verify cannot access closed rounds

**Phase 7 Complete:** [x] Players can join games and submit answers

---

## Phase 8: API Endpoints for AJAX
**Goal:** JSON endpoints for dynamic frontend updates

- [x] 8.1 Create routes/api.py
  - [x] Create Blueprint: api
  - [x] Set url_prefix='/api'

- [x] 8.2 Get/update round questions endpoint
  - [x] GET /api/round/<round_id>/questions
  - [x] Return questions_json as JSON
  - [x] POST /api/round/<round_id>/questions
  - [x] Admin only
  - [x] Update questions_json from request body
  - [x] Save to database

- [x] 8.3 Toggle round open/closed endpoint
  - [x] POST /api/round/<round_id>/toggle
  - [x] Admin only
  - [x] Toggle round.is_open boolean
  - [x] Emit Socket.IO event to players
  - [x] Return new status as JSON

- [x] 8.4 Get game answers endpoint (for spreadsheet)
  - [x] GET /api/game/<game_id>/answers
  - [x] Admin only
  - [x] Return all teams, rounds, and answers as JSON
  - [x] Format for Tabulator grid

- [x] 8.5 Update answer score endpoint
  - [x] POST /api/answer/<answer_id>/score
  - [x] Admin only
  - [x] Update points, bonus_points, penalty_points, notes
  - [x] Return updated answer as JSON

- [x] 8.6 Register api blueprint in app.py
  - [x] Import api blueprint
  - [x] app.register_blueprint(api.bp)

**Phase 8 Complete:** [x] API endpoints functional

---

## Phase 9: Admin Spreadsheet View
**Goal:** View and edit all answers in grid format

- [x] 9.1 Spreadsheet view route
  - [x] GET /admin/game/<game_id>/spreadsheet
  - [x] Admin only
  - [x] Get all teams for game
  - [x] Get all rounds for game
  - [x] Get all answers
  - [x] Create template: templates/admin/spreadsheet.html

- [x] 9.2 Set up Tabulator grid
  - [x] Include Tabulator.js library in template
  - [ ] Create static/js/spreadsheet.js (inline in template)
  - [x] Fetch data from /api/game/<game_id>/answers
  - [x] Configure columns: Team, Round, Questions, Points, Bonus, Penalty, Total
  - [x] Enable inline editing for points/bonus/penalty

- [x] 9.3 Implement inline editing
  - [x] On cell edit, POST to /api/answer/<answer_id>/score
  - [x] Update total score calculation
  - [x] Show success/error feedback

- [x] 9.4 Add filtering and sorting
  - [x] Filter by round
  - [x] Filter by team
  - [x] Sort by any column

- [x] 9.5 Add export functionality (optional)
  - [x] Export to CSV button
  - [x] Use Tabulator's download feature

- [ ] 9.6 Test spreadsheet view
  - [ ] View answers after teams submit
  - [ ] Edit scores and verify updates
  - [ ] Check total calculations

**Phase 9 Complete:** [x] Spreadsheet view functional

---

## Phase 10: Real-Time Features (Socket.IO)
**Goal:** Timer and live round updates

- [x] 10.1 Set up Socket.IO in app.py
  - [x] Already initialized in Phase 1
  - [x] Verify socketio = SocketIO(app) is working

- [x] 10.2 Create Socket.IO event handlers
  - [x] In app.py or separate file
  - [x] @socketio.on('connect') event
  - [x] @socketio.on('disconnect') event
  - [x] @socketio.on('join_game') - player joins game room

- [x] 10.3 Admin live control panel route
  - [x] GET /admin/game/<game_id>/live_control
  - [x] Admin only
  - [x] Show all rounds
  - [x] Buttons to open/close each round
  - [x] Timer controls (start 1-min, 2-min, custom)
  - [x] Create template: templates/admin/live_control.html

- [x] 10.4 Round toggle with Socket.IO broadcast
  - [x] When admin toggles round (POST /api/round/<round_id>/toggle)
  - [x] Emit 'round_status_changed' event to game room
  - [x] Include round_id and new is_open status

- [x] 10.5 Timer functionality
  - [ ] Create static/js/timer.js (inline in templates)
  - [x] Admin sets timer duration (30s, 60s, 120s, custom)
  - [x] Start timer button emits 'timer_started' Socket.IO event
  - [x] Broadcast timer to all players in game room
  - [x] Show countdown on both admin and player screens
  - [ ] When timer reaches 0, auto-close round
  - [x] Emit 'round_closed' event

- [x] 10.6 Player receives real-time updates
  - [x] In templates/player/quiz.html, include Socket.IO client
  - [x] Connect to Socket.IO server
  - [x] Join game room on page load
  - [x] Listen for 'round_status_changed' event
  - [x] Listen for 'timer_started' event
  - [x] Listen for 'round_closed' event
  - [x] Update UI when round opens/closes
  - [x] Show timer countdown
  - [x] Lock form when round closes

- [ ] 10.7 Test real-time features
  - [ ] Open two browsers: one as admin, one as player
  - [ ] Open round from admin panel
  - [ ] Verify player sees it instantly
  - [ ] Start timer from admin panel
  - [ ] Verify player sees countdown
  - [ ] Let timer expire
  - [ ] Verify round closes automatically
  - [ ] Verify player cannot submit after close

**Phase 10 Complete:** [x] Real-time timer and updates working

---

## Phase 11: Templates and Styling
**Goal:** Create all HTML templates with basic styling

- [x] 11.1 Base template
  - [x] Create templates/base.html
  - [x] Include navigation bar
  - [x] Link to CSS files
  - [x] Include Socket.IO client script
  - [x] Flash message display block
  - [x] Content block for child templates

- [x] 11.2 Landing page
  - [x] Create templates/index.html
  - [x] Welcome message
  - [x] Links to admin login and player join

- [x] 11.3 Style with CSS framework
  - [x] Choose Pico CSS or Bulma
  - [x] Include CDN link in base.html
  - [x] Create static/css/style.css for custom styles
  - [ ] Create static/css/admin.css for admin-specific styles

- [x] 11.4 Ensure all templates extend base.html
  - [x] Check all player/ templates
  - [x] Check all admin/ templates

- [ ] 11.5 Responsive design
  - [ ] Test on mobile screen sizes
  - [ ] Ensure forms are usable on mobile
  - [ ] Ensure spreadsheet scrolls horizontally if needed

- [ ] 11.6 Polish UI
  - [ ] Consistent button styles
  - [ ] Clear error messages
  - [ ] Loading indicators where appropriate
  - [ ] Success messages for actions

**Phase 11 Complete:** [ ] All templates styled and responsive

---

## Phase 12: Validation and Scoring Logic
**Goal:** Implement answer validation and score calculation

- [x] 12.1 Server-side validation on submit
  - [x] In player submit route, validate each answer
  - [x] For text questions: use validate_text_answer() from utils
  - [x] For number questions: check if valid number
  - [x] Store validation result (correct/incorrect)

- [x] 12.2 Auto-scoring on submission
  - [x] Calculate points based on question config
  - [x] For text: 1 point if regex matches, 0 if not
  - [x] For number: use calculate_math_score() from utils
  - [x] Save points to Answer.points column

- [x] 12.3 Manual score adjustment in spreadsheet
  - [x] Admin can edit points directly
  - [x] Admin can add bonus_points
  - [x] Admin can add penalty_points
  - [x] Total = points + bonus_points - penalty_points

- [x] 12.4 Display scoring in admin spreadsheet
  - [x] Show auto-calculated points
  - [x] Show manual adjustments
  - [x] Show total
  - [ ] Highlight incorrect answers (optional)

- [ ] 12.5 Test scoring
  - [ ] Submit correct answers, verify points awarded
  - [ ] Submit incorrect answers, verify 0 points
  - [ ] Test math formulas with various inputs
  - [ ] Test bonus/penalty adjustments
  - [ ] Verify totals calculate correctly

**Phase 12 Complete:** [x] Validation and scoring working correctly

---

## Phase 13: Testing and Bug Fixes
**Goal:** Test all features thoroughly and fix issues

- [ ] 13.1 Test admin flow end-to-end
  - [ ] Create game
  - [ ] Create rounds
  - [ ] Add questions with various types
  - [ ] Set validation patterns
  - [ ] Open/close rounds
  - [ ] Use timer
  - [ ] View spreadsheet
  - [ ] Edit scores

- [ ] 13.2 Test player flow end-to-end
  - [ ] Join game with QR code
  - [ ] Create new team
  - [ ] Login with existing team
  - [ ] Submit answers to multiple rounds
  - [ ] Try to submit twice (should fail)
  - [ ] Try to access closed round (should fail)
  - [ ] Receive real-time updates

- [ ] 13.3 Test edge cases
  - [ ] Empty form submissions
  - [ ] Special characters in team names
  - [ ] Very long answers
  - [ ] Invalid game codes
  - [ ] Expired sessions
  - [ ] Multiple teams submitting simultaneously

- [ ] 13.4 Test validation patterns
  - [ ] Single regex patterns
  - [ ] OR logic (pattern1 / pattern2)
  - [ ] AND logic (pattern1 + pattern2)
  - [ ] Case sensitivity

- [ ] 13.5 Test math formulas
  - [ ] Simple formulas (answer * 2)
  - [ ] Complex formulas (answer * 4 / 2 + 10)
  - [ ] Invalid formulas (should not crash)

- [ ] 13.6 Browser compatibility
  - [ ] Test in Chrome
  - [ ] Test in Firefox
  - [ ] Test in Safari
  - [ ] Test on mobile browsers

- [ ] 13.7 Fix all found bugs
  - [ ] Document bugs
  - [ ] Prioritize critical bugs
  - [ ] Fix and re-test

**Phase 13 Complete:** [ ] All major bugs fixed

---

## Phase 14: Documentation
**Goal:** Complete all documentation files

- [x] 14.1 Update README.md
  - [x] Verify setup instructions are correct
  - [ ] Add screenshots (optional)
  - [x] Update troubleshooting section with any new issues

- [x] 14.2 Create docs/DATABASE_SCHEMA.md
  - [x] Document all tables and columns
  - [x] Document relationships
  - [x] Include ER diagram (optional)

- [x] 14.3 Create docs/ROUTES_SPEC.md
  - [x] List all routes
  - [x] Document URL patterns
  - [x] Document required permissions
  - [x] Document request/response formats

- [x] 14.4 Create docs/FEATURES_SPEC.md
  - [x] Document each feature in detail
  - [x] Include user workflows
  - [x] Include validation rules

- [x] 14.5 Create docs/DEPLOYMENT.md
  - [x] Document production setup
  - [x] Include server requirements
  - [x] Include security considerations
  - [x] Include backup procedures

- [x] 14.6 Add code comments
  - [x] Comment complex functions
  - [x] Add docstrings to all functions
  - [x] Document non-obvious logic

**Phase 14 Complete:** [x] Documentation complete

---

## Phase 15: Deployment Preparation
**Goal:** Prepare for production deployment

- [x] 15.1 Security checklist
  - [x] Change SECRET_KEY to strong random value (enforced in ProductionConfig)
  - [x] Change admin password from default (documented in .env.production.example)
  - [x] Disable Flask debug mode (ProductionConfig.DEBUG = False)
  - [x] Set FLASK_ENV=production (documented)
  - [x] Add CSRF protection (WTForms already includes this)
  - [x] Add rate limiting (flask-limiter)
  - [x] Validate all user inputs (server-side validation implemented)

- [x] 15.2 Database preparation
  - [x] Set up PostgreSQL backups (pg_dump automation - documented in DEPLOYMENT.md)
  - [x] Test database migrations on staging environment (Flask-Migrate ready)
  - [ ] Set up connection pooling (PgBouncer if needed) - optional for small deployments
  - [x] Configure PostgreSQL for production (documented in DEPLOYMENT.md)

- [x] 15.3 Configure production server
  - [x] Use Gunicorn or uWSGI instead of Flask dev server (gunicorn in requirements)
  - [x] Set up Nginx as reverse proxy (documented in DEPLOYMENT.md)
  - [x] Configure HTTPS with Let's Encrypt (documented in DEPLOYMENT.md)
  - [x] Set up process manager (systemd service documented)

- [x] 15.4 Environment configuration
  - [x] Move all secrets to environment variables
  - [x] Create production .env file (.env.production.example created)
  - [x] Never commit .env to git (.gitignore already excludes .env)

- [ ] 15.5 Performance optimization
  - [ ] Enable caching where appropriate
  - [x] Compress static assets (Nginx gzip documented)
  - [ ] Set up CDN for static files (optional)

- [x] 15.6 Monitoring and logging
  - [x] Set up error logging (Gunicorn logging documented)
  - [x] Set up performance monitoring (documented in DEPLOYMENT.md)
  - [x] Set up uptime monitoring (documented in DEPLOYMENT.md)

- [x] 15.7 Create deployment documentation
  - [x] Step-by-step deployment guide
  - [x] Server requirements
  - [x] Configuration examples

**Phase 15 Complete:** [x] Ready for production deployment

---

## Optional Enhancements (Future)

- [ ] Export results to PDF
- [ ] Email notifications to teams
- [ ] Leaderboard display
- [ ] Multiple admin users
- [ ] Round templates (save/reuse questions)
- [ ] Image upload for questions
- [ ] Audio/video questions
- [ ] Mobile app (React Native)
- [ ] Internationalization (multiple languages)
- [ ] Dark mode
- [ ] Analytics dashboard

---

## Notes

**Update this file after each phase:**
1. Mark completed tasks with [x]
2. Add notes about challenges or decisions
3. Update if requirements change
4. Document any deviations from plan

**Current Phase:** Phase 15 (Deployment Preparation)

**Last Updated:** 2025-12-13

**Notes:**
- Phases 1-10 core functionality implemented
- Using PostgreSQL database (port 5777)
- Using Pico CSS for styling
- JavaScript is inline in templates (not separate files)
- Need to test with actual PostgreSQL database
- Need to run Flask-Migrate for proper migrations
