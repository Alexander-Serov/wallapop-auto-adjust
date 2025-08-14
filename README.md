# Wallapop Auto Price Adjuster

Automatically adjust prices of your Wallapop products based on configurable criteria.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### First Run
```bash
python run.py
```
- Complete manual login once (handles captcha/SMS)
- Session persists for 24 hours
- Discovers all your products
- Creates `products_config.json`

### Configure Products
```bash
python configure.py
```
- Set price adjustments per product:
  - `keep` - No change
  - `0.9` - Reduce by 10%
  - `1.1` - Increase by 10%
- Set delay between updates (days)

### Run Adjustments
```bash
python run.py
```
- Uses saved session (no login needed)
- Applies configured price changes
- Shows confirmation before each update
- Respects delay settings

## Configuration

The `products_config.json` file contains:
- Product settings (adjustment, last_modified)
- Global settings (delay_days)

## Features

✅ **Session Persistence** - Login once, reuse for 24 hours  
✅ **Auto-Discovery** - Finds new products automatically  
✅ **Delay Control** - Configurable time between updates  
✅ **Price Confirmation** - Shows current vs new price  
✅ **API Integration** - Uses official Wallapop API endpoints

## License

This project is licensed under the MIT License — see the `LICENSE` file for details.