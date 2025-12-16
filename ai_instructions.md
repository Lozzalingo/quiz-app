# Instructions for AI Coding Assistant

**Purpose:** This file contains instructions for an AI assistant (CLI or otherwise) to help build the Quiz App project systematically.

---

## Your Role

You are an AI coding assistant helping build a Flask-based quiz application. Your job is to:

1. Read and understand the project requirements from README.md
2. Work through TODO.md sequentially, phase by phase
3. Write clean, well-commented code following best practices
4. Update TODO.md after completing each task
5. Create documentation as you build
6. Ask clarifying questions when requirements are ambiguous

---

## How to Work

### Starting the Project

1. **First, read these files in order:**
   - README.md (understand what we're building)
   - TODO.md (understand the development roadmap)
   - This file (understand your workflow)

2. **Then begin with Phase 1 of TODO.md:**
   - Complete each task in the checklist
   - Mark tasks as complete with [x]
   - Move sequentially through phases

3. **After each phase:**
   - Update TODO.md to mark phase complete
   - Add any notes about decisions made
   - Commit changes with clear commit message
   - Inform the human that phase is complete

### Working Through Tasks

**For each task:**

1. **Read the task carefully** - Understand what needs to be built
2. **Check related documentation** - Review docs/ folder if relevant
3. **Write the code** - Follow Python/Flask best practices
4. **Add comments** - Explain non-obvious logic
5. **Test the code** - Verify it works before moving on
6. **Update TODO.md** - Mark task as complete [x]

**Example workflow for a task:**
```
Task: [ ] 2.2 Create Admin model

Step 1: Read task requirements
Step 2: Check docs/DATABASE_SCHEMA.md for details
Step 3: Write Admin model in models.py
Step 4: Add docstring and comments
Step 5: Test by running migrations
Step 6: Update TODO.md: [x] 2.2 Create Admin model
```

### Code Quality Standards

**Python/Flask:**
- Follow PEP 8 style guide
- Use meaningful variable names
- Write docstrings for all functions and classes
- Handle errors gracefully with try/except
- Use type hints where helpful
- Keep functions focused and small

**Example of good code:**
```python
def validate_text_answer(user_answer: str, pattern_string: str) -> bool:
    """
    Validate user's text answer against regex pattern(s).
    
    Args:
        user_answer: The answer provided by the user
        pattern_string: Regex pattern(s) to validate against.
                       Supports OR logic (pattern1 / pattern2) 
                       and AND logic (pattern1 + pattern2)
    
    Returns:
        bool: True if answer matches pattern, False otherwise
    
    Examples:
        >>> validate_text_answer("Paris", "^[Pp]aris$")
        True
        >>> validate_text_answer("London", "Paris / London")
        True
    """
    if not pattern_string:
        return True
    
    user_answer = str(user_answer).strip()
    
    # Handle OR logic
    if ' / ' in pattern_string:
        patterns = [p.strip() for p in pattern_string.split(' / ')]
        return any(re.search(p, user_answer, re.IGNORECASE) for p in patterns if p)
    
    # ... rest of function
```

**HTML/JavaScript:**
- Use semantic HTML5 elements
- Keep JavaScript modular and well-commented
- Use meaningful CSS class names
- Ensure responsive design

**Database:**
- Use descriptive table and column names
- Add indexes for frequently queried columns
- Use foreign keys for relationships
- Include CASCADE delete where appropriate
- PostgreSQL handles concurrent writes well - no need for special locking
- Use transactions for multi-step operations

---

## Important Patterns and Conventions

### File Organization

**models.py** - All SQLAlchemy models
- One class per table
- Include relationships
- Add helper methods (get_*, set_*)

**routes/** - Organized by user type
- auth.py - Login/logout for all users
- player.py - Player-facing routes only
- admin.py - Admin-facing routes only
- api.py - JSON endpoints only

**templates/** - Organized by user type
- All player templates in templates/player/
- All admin templates in templates/admin/
- Shared templates at root level

**static/** - Organized by type
- CSS files in static/css/
- JS files in static/js/
- Generated files (QR codes) in static/qrcodes/

### Blueprint Registration

Always register blueprints in app.py:
```python
from routes import auth, player, admin, api

app.register_blueprint(auth.bp)
app.register_blueprint(player.bp)
app.register_blueprint(admin.bp)
app.register_blueprint(api.bp)
```

### User Authentication Pattern

Use Flask-Login with custom user_loader:
```python
@login_manager.user_loader
def load_user(user_id):
    # Check prefix to determine user type
    if user_id.startswith('admin_'):
        return Admin.query.get(int(user_id.split('_')[1]))
    elif user_id.startswith('team_'):
        return Team.query.get(int(user_id.split('_')[1]))
    return None
```

When logging in, use prefixed IDs:
```python
login_user(admin, remember=True)  # Flask-Login uses str(admin.id)
```

Override `get_id()` in models:
```python
class Admin(UserMixin, db.Model):
    # ... fields ...
    
    def get_id(self):
        return f'admin_{self.id}'

class Team(UserMixin, db.Model):
    # ... fields ...
    
    def get_id(self):
        return f'team_{self.id}'
```

### JSON Storage Pattern

For flexible data (like questions), use JSON columns:
```python
class Round(db.Model):
    questions_json = db.Column(db.Text, nullable=False)
    
    def get_questions(self):
        """Parse JSON string to Python list"""
        return json.loads(self.questions_json)
    
    def set_questions(self, questions):
        """Serialize Python list to JSON string"""
        self.questions_json = json.dumps(questions)
```

### Socket.IO Pattern

Organize Socket.IO events by game rooms:
```python
# Admin closes round
@socketio.on('close_round')
def handle_close_round(data):
    round_id = data['round_id']
    game_id = data['game_id']
    
    # Update database
    round_obj = Round.query.get(round_id)
    round_obj.is_open = False
    db.session.commit()
    
    # Broadcast to all players in this game
    emit('round_closed', 
         {'round_id': round_id}, 
         room=f'game_{game_id}')
```

### Error Handling Pattern

Always handle errors gracefully:
```python
@bp.route('/some_route')
def some_route():
    try:
        # Your logic here
        result = do_something()
        return render_template('success.html', result=result)
    except ValueError as e:
        flash(f'Invalid input: {str(e)}', 'danger')
        return redirect(url_for('some_form'))
    except Exception as e:
        # Log error
        app.logger.error(f'Unexpected error: {str(e)}')
        flash('An unexpected error occurred', 'danger')
        return redirect(url_for('index'))
```

---

## Testing Guidelines

### After Each Phase

1. **Manual Testing**
   - Run the app: `python app.py`
   - Test the features you just built
   - Try both happy path and error cases
   - Test in browser (check console for JS errors)

2. **Check for Errors**
   - No Python exceptions
   - No 404s or 500s
   - No JavaScript console errors
   - Forms validate correctly

3. **Verify Database**
   - Check tables exist: `psql quiz_app -c "\dt"`
   - Check data is saving correctly: `psql quiz_app -c "SELECT * FROM game;"`
   - Check relationships work
   - Monitor PostgreSQL logs for errors

### Test Checklist Template

After completing a phase, verify:
- [ ] Code runs without errors
- [ ] New features work as expected
- [ ] Existing features still work (no regressions)
- [ ] Database updates applied correctly
- [ ] Templates render properly
- [ ] Forms validate input
- [ ] Error messages display correctly
- [ ] Navigation works

---

## Documentation Guidelines

### Code Comments

**When to comment:**
- Complex algorithms or logic
- Non-obvious business rules
- Workarounds or hacks
- Important security considerations
- Regex patterns (explain what they match)

**When NOT to comment:**
- Obvious code (don't comment "# increment i" on "i += 1")
- Code that explains itself through clear naming

### Docstrings

Add docstrings to all functions and classes:
```python
def function_name(arg1: type, arg2: type) -> return_type:
    """
    Brief description of what function does.
    
    Longer explanation if needed. Explain the business logic,
    not just what the code does.
    
    Args:
        arg1: Description of first argument
        arg2: Description of second argument
    
    Returns:
        Description of return value
    
    Raises:
        ValueError: When invalid input is provided
    
    Examples:
        >>> function_name("test", 42)
        "result"
    """
    pass
```

### Creating Documentation Files

As you build features, create documentation files in docs/ folder:

**docs/DATABASE_SCHEMA.md** - During Phase 2
- List all tables
- Describe each column
- Explain relationships
- Include example queries

**docs/ROUTES_SPEC.md** - As you build routes
- List all URL patterns
- HTTP methods (GET, POST)
- Required permissions
- Request/response formats

**docs/FEATURES_SPEC.md** - As features are completed
- Detailed user workflows
- Validation rules
- Business logic
- Edge cases

---

## Common Pitfalls to Avoid

### Database
- ❌ Forgetting `db.session.commit()` after changes
- ❌ Not handling database exceptions
- ❌ Circular imports between models and routes
- ❌ Not closing database connections (PostgreSQL will handle this but be aware)
- ✅ Always commit after INSERT/UPDATE/DELETE
- ✅ Use try/except around database operations
- ✅ Import db from models in routes
- ✅ Use context managers for transactions when needed

### Flask-Login
- ❌ Forgetting `@login_required` decorator
- ❌ Not checking user type (admin vs team)
- ❌ Accessing current_user without checking is_authenticated
- ✅ Protect all routes that need authentication
- ✅ Use isinstance(current_user, Admin) to check type
- ✅ Always check current_user.is_authenticated first

### Forms
- ❌ Not validating on both client and server
- ❌ Trusting user input without sanitization
- ❌ Not including CSRF tokens
- ✅ Validate with WTForms on server
- ✅ Add JavaScript validation for UX
- ✅ WTForms includes CSRF automatically

### Socket.IO
- ❌ Emitting to wrong room
- ❌ Not joining rooms on connect
- ❌ Forgetting to handle disconnections
- ✅ Use rooms to organize connections by game
- ✅ Join room when player enters game
- ✅ Clean up on disconnect

### Templates
- ❌ Not escaping user input (XSS risk)
- ❌ Hardcoding URLs instead of url_for()
- ❌ Repeating code instead of using includes
- ✅ Jinja2 auto-escapes by default
- ✅ Always use url_for('route_name')
- ✅ Use {% include %} for repeated elements

---

## Communication with Human

### When to Ask Questions

**Always ask if:**
- Requirements are ambiguous or contradictory
- Multiple valid approaches exist (ask for preference)
- You encounter a technical limitation
- You need clarification on business logic
- You find a better approach than specified

**Don't ask about:**
- Standard Flask patterns (use best practices)
- Common Python idioms (follow PEP 8)
- Minor implementation details (make reasonable choices)

### How to Report Progress

**After completing each phase:**
```
Phase X Complete: [Phase Name]

Completed:
- Task 1
- Task 2
- Task 3

Files created/modified:
- file1.py
- file2.html

Tested:
- Feature A works correctly
- Feature B handles errors

Notes:
- [Any important decisions or changes]

Ready to proceed to Phase X+1: [Next Phase Name]?
```

### How to Report Issues

**If you encounter a blocker:**
```
Issue in Phase X, Task Y

Problem:
[Clear description of the issue]

What I tried:
1. Approach 1 - didn't work because...
2. Approach 2 - didn't work because...

Possible solutions:
1. Solution A - pros: ..., cons: ...
2. Solution B - pros: ..., cons: ...

Recommendation:
[Your suggested approach and why]

Waiting for guidance on how to proceed.
```

---

## Working with the Human's Feedback

### When Human Provides Feedback

1. **Read carefully** - Understand exactly what needs to change
2. **Ask questions** - If anything is unclear
3. **Update code** - Make requested changes
4. **Re-test** - Verify changes work
5. **Update docs** - If relevant
6. **Confirm completion** - Report back when done

### Iterating on Code

- Don't delete working code unless explicitly asked
- Keep commit history clean with meaningful messages
- If changing approach, explain why the new approach is better
- Preserve backward compatibility when possible

---

## Workflow Summary

```
1. Read README.md, TODO.md, and this file
2. Start with Phase 1, Task 1
3. For each task:
   a. Read requirements
   b. Check relevant documentation
   c. Write code with comments
   d. Test thoroughly
   e. Update TODO.md
4. After each phase:
   a. Do comprehensive testing
   b. Update documentation
   c. Report completion to human
   d. Wait for approval before next phase
5. Update TODO.md notes section with any important info
6. Proceed to next phase
```

---

## Final Notes

**Remember:**
- Quality over speed
- Test before moving forward
- Document as you go
- Ask when unsure
- Keep code clean and readable

**Your goal is to build a working, maintainable application that matches the specifications in README.md and follows the roadmap in TODO.md.**

**When in doubt, refer back to README.md for the project vision and TODO.md for the specific tasks.**

---

Good luck! Start with Phase 1 of TODO.md and work your way through systematically.