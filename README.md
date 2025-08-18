# Wallapop Auto Price Adjuster

Automate price adjustment of your Wallapop sales listings with a safe interactive flow.

![PyPI](https://img.shields.io/pypi/v/wallapop-auto-adjust.svg?label=PyPI&logo=pypi)
![Python versions](https://img.shields.io/pypi/pyversions/wallapop-auto-adjust.svg?logo=python)
![License](https://img.shields.io/github/license/Alexander-Serov/wallapop-auto-adjust.svg)
![CI](https://img.shields.io/github/actions/workflow/status/Alexander-Serov/wallapop-auto-adjust/ci.yml?label=CI&logo=github)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/Alexander-Serov/wallapop-auto-adjust/issues)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Quick links: [Why](#why-this-project-exists) • [Quick Start](#quick-start-guide) • [Use](#using-the-tool-after-the-first-start) • [Config](#configuration-details) • [Safety](#safety-features) • [Troubleshoot](#troubleshooting) • [Privacy](#privacy--disclaimer) • [Developers](#for-developers) • [License](#license)

## Why this project exists

Wallapop is a platform that allows us to give a second life to our items.
This is a laudable objective, but it would also be great to sell your items for the right (market) price.
Not too low, so that you lose on the sale, and not too high, so that your listings stay on Wallapop indefinitely.
The right price.

Finding this price, however, is difficult without access to statistics only Wallapop itself has.
In the absence of the statistics, a reasonable approach can be an iterative price adjustment, similar to what Amazon uses to sell its products: you start with a high price and keep lowering it regularly until the buyer grabs your article.
Doing this by hand is feasible for a couple of articles, but can be tedious if you are selling a dozen articles.
This project is aimed at automating it to a significant extent.
A positive byproduct is an extra service to society: more buyers find their products faster, the price is right for both parties, and the market gets more fluid.

Here is what the Tool can do for you:
- Automatically detect your selling portfolio after login
- Let you decide on the price strategy to use for each product (rate of price adjustment)
- Automatically apply consistent adjustments (e.g., “-10%” or keep price) on user confirmation
- Automatically respect a delay between updates (e.g., only update once every 7 days)
- Keeps a minimum price of €1 to keep articles eligible for shipment
- Maintains a local configuration between runs

Here is what the Tool cannot (yet) do:
- Run automatically at regular intervals 
- Run fully automatically without user confirmation

The user is required to run it and confirm all price changes.

## Quick Start Guide

In your Python environment, run:
```bash
pip install wallapop-auto-adjust
wallapop-auto-adjust
```

What happens on first run:
- You’ll be prompted to log into Wallapop in your browser (captcha/SMS supported)
- The session is saved locally and reused for ~24 hours
- Your products are discovered and a `products_config.json` file is created/updated for you locally
- You can modify it locally if you wish
- Alternatively, you’ll be asked interactively, product by product, which price change (in percent) to apply to each of the products.

### What it will look like

```text
$ wallapop-auto-adjust
✔ Using saved session (valid)
Found 12 products. delay_days = 7

1) Bicycle — current: €120.00 → new: €108.00 (-10%)
  Apply? [y]es / [k]eep / [s]kip: y
  ✓ Updated to €108.00

2) Helmet — current: €15.00 → new: keep
  Apply? [y]es / [k]eep / [s]kip: k
  ↷ Keeping current price

...
Done. Updated: 5, Kept: 6, Skipped: 1
```

## Using the tool (after the first start)

Run the CLI any time:
```bash
wallapop-auto-adjust
```
- Uses the saved session if still valid (no login needed)
- Shows current vs new price and asks for confirmation
- Respects your configured delay in days before revisiting a product

## Configuration Details

The tool creates and manages a local `products_config.json` in the project folder. It contains:
- products: a map of product IDs to settings
  - name: for your reference
  - adjustment: a numeric multiplier like 0.9, 1.1, such that the new price is `old_price * multiplier`. For example, to decrease the price by 15% on each run, set it to 0.85. You can also set it to "keep" (default) to maintain the current price.
  - last_modified: last time a price change was applied (ISO datetime)
- settings:
  - delay_days: minimum days between updates (set 0 to always prompt). Applies to all articles.

Example snippet:
```json
{
  "products": {
    "12345": { "name": "Bicycle", "adjustment": 0.9, "last_modified": "2025-08-15T10:30:00+02:00" },
    "67890": { "name": "Helmet",  "adjustment": "keep", "last_modified": null }
  },
  "settings": { "delay_days": 1 }
}
```

## Safety features
- Minimum price protection: never goes below €1; if a multiplier would drop below €1, the strategy automatically switches to "keep" after applying the €1 update
- Delay between updates: configurable via `delay_days` (0 = always ask)
- Interactive confirmations: you always see current vs new price before applying
- Rounding: prices rounded to 2 decimals

## Troubleshooting
- “No products found”
  - Your session may be expired. Re-run and log in again when prompted.
  - Check that your Wallapop account has active listings.
- “401/unauthorized” or keeps asking to log in
  - Delete the local session file `wallapop_session.json` and re-run.
- “Where are files stored?”
  - `products_config.json` and `wallapop_session.json` are stored locally in the project folder.

## Privacy & disclaimer
- The authors are not affiliated with Wallapop and provide the tool free of charge for your convenience. Use responsibly and respect Wallapop’s Terms of Service.
- Tokens and config live only on your machine; no data is ever collected.
- Although we try hard to squash, bugs may still creep through. Remember the responsibility to check all the prices the tool suggests you lies exclusively with you.

## For developers

**All contributions welcome! All PRs will be reviewed!**
In short, make it your project.
If you miss a feature or find a bug, feel free to create an issue in the [issue tracker](https://github.com/Alexander-Serov/wallapop-auto-adjust/issues).
If you feel like tackling any existing issue, feel free to do it. Even if we don't set it as the default behavior, the extra feature you add can be made available through an option in the config.
If you know how, try adding tests for the new functionality within the existing test structure.

See also: [CONTRIBUTING](CONTRIBUTING.md)


Requirements: Python 3.10+ and Poetry

1) Install Poetry and dependencies
```bash
poetry install
```
2) Run tests
```bash
poetry run pytest -q
```
3) Run the CLI during development
```bash
poetry run wallapop-auto-adjust
```

## License

MIT — see `LICENSE`.