# Wallapop Auto Price Adjuster

Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.

## Application Overview

Wallapop Auto Price Adjuster is a Python CLI application that automatically adjusts product prices on the Wallapop marketplace. The tool's main intentions are:

**Core Purpose**: Automate price adjustments for Wallapop sellers to maintain competitive pricing and increase visibility of their listings. It's a win-win-win for the seller (faster sales), for the buyer (lower price) and for Wallapop (faster & more fluid transactions).

**Key Features**:
- **Automated Login**: Supports both automatic browser automation and manual cookie extraction for Wallapop authentication
- **Session Persistence**: Maintains login sessions to avoid repeated authentication
- **Product Discovery**: Automatically fetches all user's active products from Wallapop API
- **Price Management**: Applies configurable price adjustment rules (percentage-based or fixed amounts)
- **Smart Timing**: Respects user-defined delay periods between price updates to avoid spam detection
- **Configuration Management**: Maintains local product configurations with persistent settings
- **Sold Product Cleanup**: Automatically removes sold items from configuration

**Technology Stack**: Python CLI application using Selenium for browser automation, maintains local session persistence, and provides interactive price adjustment workflows.

## Working Effectively

### System Requirements
- Python 3.10+
- Poetry for dependency management
- Google Chrome browser (required for Selenium automation)
- ChromeDriver (automatically managed by Selenium)

### Bootstrap and Development Setup
Run these commands in exact order:
```bash
# Install Poetry (if not available)
python -m pip install --upgrade pip
pip install pipx
pipx install poetry

# Install dependencies - NEVER CANCEL: Takes ~4-5 seconds for subsequent runs, ~30+ seconds for fresh install
poetry install

# Verify installation works
poetry run python3 -c "from wallapop_auto_adjust.cli import main; print('✓ Installation successful')"
```

### Build and Test
```bash
# Run tests - NEVER CANCEL: Takes ~1-2 seconds. Set timeout to 30+ seconds
poetry run pytest -q

# Check code formatting (will show violations if any) - Takes ~1 second
poetry run black --check .

# Format code automatically - Takes ~1-2 seconds
poetry run black .
```

### IDE Integration
For local development with IDE support:
- **VS Code**: Use the built-in Test Explorer or Python extension's test discovery. Ensure Poetry virtual environment is selected as Python interpreter.
- **PyCharm**: Configure Poetry as the project interpreter. Use the integrated test runner for pytest execution.
- **General IDEs**: Point the IDE to use the Poetry virtual environment (`poetry env info --path`) and configure pytest as the test framework.

**Important**: When using IDEs for testing, ensure the Poetry virtual environment is active. All test execution should go through Poetry's virtual environment, not system Python.

### Running the Application
```bash
# Run the CLI tool (interactive - requires user input)
poetry run wallapop-auto-adjust

# Alternative: Test core components without interaction
poetry run python3 -c "
from wallapop_auto_adjust.config import ConfigManager
from wallapop_auto_adjust.session_manager import SessionManager
print('✓ Core components functional')
"
```

## Validation

### Manual Testing Requirements
After making changes, ALWAYS test these scenarios:

1. **Component Import Test**: Verify all modules import correctly
   ```bash
   poetry run python3 -c "
   from wallapop_auto_adjust.config import ConfigManager
   from wallapop_auto_adjust.session_manager import SessionManager  
   from wallapop_auto_adjust.wallapop_client import WallapopClient
   from wallapop_auto_adjust.price_adjuster import PriceAdjuster
   print('✓ All modules import successfully')
   "
   ```

2. **CLI Startup Test**: Verify the CLI starts without errors
   ```bash
   # This will start the CLI and prompt for email - press Ctrl+C to exit
   timeout 5s poetry run wallapop-auto-adjust || echo "✓ CLI starts correctly"
   ```

3. **Configuration Test**: Verify configuration management works
   ```bash
   poetry run python3 -c "
   from wallapop_auto_adjust.config import ConfigManager
   config = ConfigManager()
   print(f'✓ Config path: {config.config_path}')
   "
   ```

### Pre-commit Validation
Always run these commands before committing:
```bash
poetry run black .
poetry run pytest -q
```


## Common Tasks

### Project Structure
```
.
├── README.md                    # User documentation
├── CONTRIBUTING.md              # Developer guide  
├── TECHNICAL_REQUIREMENTS.md    # Technical specifications
├── pyproject.toml              # Poetry configuration
├── poetry.lock                 # Dependency lock file
├── src/
│   └── wallapop_auto_adjust/
│       ├── cli.py              # Main CLI entry point
│       ├── config.py           # Configuration management
│       ├── session_manager.py  # Legacy session compatibility
│       ├── session_persistence.py # Modern session persistence
│       ├── wallapop_client.py  # API client and browser automation
│       ├── price_adjuster.py   # Price adjustment logic
│       ├── api_analyzer.py     # API endpoint analysis
│       └── cookie_extraction_guide.py # Manual login guide
└── tests/
    ├── conftest.py             # Test configuration
    ├── test_config.py          # Configuration tests
    ├── test_session_manager.py # Session tests
    ├── test_imports.py         # Import validation
    ├── test_price_adjuster.py  # Price logic tests
    ├── test_wallapop_client_workflow.py # Client workflow tests
    ├── test_access_token_refresh.py # Token refresh tests
    └── test_cookie_guide_flow.py # Cookie guide tests
```

### Key Configuration Files
- **pyproject.toml**: Poetry configuration, dependencies, scripts
- **poetry.lock**: Locked dependency versions (DO NOT edit manually, run `poetry lock` instead)
- **.gitignore**: Excludes local files like `products_config.json`, `wallapop_session.json`

### Development Dependencies
Main runtime dependencies:
- `requests`: HTTP client for API calls
- `selenium`: Browser automation for login
- `undetected-chromedriver`: Enhanced Chrome automation to avoid detection
- `beautifulsoup4`: HTML parsing  
- `python-dateutil`: Date/time handling
- `python-dotenv`: Environment variable management

Development dependencies:
- `pytest`: Testing framework
- `black`: Code formatting

### Local Files (Ignored by Git)
These files are created during runtime and should NOT be committed:
- `products_config.json`: User's product configuration and pricing rules
- `wallapop_session.json`: Saved login session (expires after 24 hours)
- `.env`: Optional environment variables for login credentials (WALLAPOP_EMAIL, WALLAPOP_PASSWORD)

### CLI Entry Points
- **Main CLI**: `wallapop-auto-adjust` (defined in pyproject.toml scripts)
- **Direct execution**: `poetry run python -m wallapop_auto_adjust.cli`

### Important Code Locations
- **Main orchestration**: `src/wallapop_auto_adjust/cli.py:main()` - Entry point that coordinates login, product fetching, and price adjustments
- **API client**: `src/wallapop_auto_adjust/wallapop_client.py:WallapopClient` - Handles authentication and API communication
- **Configuration**: `src/wallapop_auto_adjust/config.py:ConfigManager` - Manages product configurations and user preferences
- **Price logic**: `src/wallapop_auto_adjust/price_adjuster.py:PriceAdjuster` - Implements price calculation and update rules
- **Session management**: `src/wallapop_auto_adjust/session_persistence.py:SessionPersistenceManager` - Modern session handling
- **Manual login**: `src/wallapop_auto_adjust/cookie_extraction_guide.py:CookieExtractionGuide` - Guided manual authentication

### Common Workflows

#### Adding New Features
1. Always run tests first: `poetry run pytest -q`
2. Make minimal changes to existing code
3. Add tests for new functionality in `tests/`
4. Format code: `poetry run black .`
5. Verify tests pass: `poetry run pytest -q`

#### Debugging Issues
1. Test component imports individually
2. Check `products_config.json` and `wallapop_session.json` if authentication issues
3. Verify Chrome/ChromeDriver compatibility for Selenium issues
4. Check Poetry environment: `poetry env info`

#### Working with Dependencies
```bash
# Add new dependency
poetry add package-name

# Add development dependency  
poetry add --group dev package-name

# Update dependencies
poetry update

# Show dependency tree
poetry show --tree
```

### Security Notes
- The application stores session cookies locally in `wallapop_session.json`
- Credentials can be provided via `.env` file (WALLAPOP_EMAIL, WALLAPOP_PASSWORD)
- Session files are automatically excluded from git via `.gitignore`
- NEVER commit authentication credentials or session files

### Browser Automation Details
- Uses Chrome browser with undetected-chromedriver for Selenium WebDriver automation
- Requires user interaction for initial login (handles captcha/SMS verification)  
- Sessions persist for ~24 hours automatically in `~/.wallapop-auto-adjust/` directory
- Headless mode is NOT used to support manual login requirements and avoid detection
- Two login methods available: automatic browser automation or manual cookie extraction guide