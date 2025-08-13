# Technical Requirements - Wallapop Auto Price Adjuster

## Overview
Automatic price adjustment tool for Wallapop products by intercepting web API requests.

## Core Requirements

### Authentication & Data Retrieval
- **Login Process**: User completes manual browser login once at session start (handles captcha/SMS)
- **Session Persistence**: Automatically saves and reuses authentication tokens/cookies for 24 hours
- **API Integration**: Uses JWT access tokens from cookies for authenticated API calls
- **Price Updates**: Two-step API process (components endpoint + PUT update) with exact payload matching
- Extract product IDs, names, current prices, and last modification dates via API

### Local Configuration Management
- Store product configurations locally (JSON format)
- Product config structure:
  - `id`: Product identifier
  - `name`: Product name for user identification
  - `adjustment`: "keep" or float multiplier (e.g., 0.9 for 10% reduction)
  - `last_modified`: ISO format date with timezone of last price modification
- Auto-discover new products and add with "keep" adjustment
- Preserve existing configurations when updating
- Runtime adjustment override: users can modify adjustment values during execution

### Price Adjustment Logic
- Interactive CLI prompts for each product with runtime adjustment modification
- Show default action from config (user can override by typing new value or press Enter for default)
- Skip products automatically only if delay period hasn't passed
- Show current vs new price before applying with confirmation
- Round prices to 2 decimal places
- Implement configurable delay (days) between updates
- Minimum price protection: €1 floor with automatic strategy switch to "keep"
- If delay = 0, always prompt for user decision

### Technical Decisions
- **Language**: Python (better for web scraping, API interaction, JSON handling)
- **Architecture**: Modular design with separate components:
  - Authentication module
  - Product listing/discovery module  
  - Configuration management module
  - Price adjustment module
  - Main orchestrator
- **Data Storage**: Local JSON files for configuration
- **Logging**: Console output with timestamps

## Design Principles
- Small, independent modules with clear functionality
- Easy contribution/extension for open source
- Minimal dependencies
- Clear separation of concerns
- Error handling and graceful degradation