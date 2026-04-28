# flOW

flOW is an operator opportunity engine built on top of SONRIS-style well, production, and permit data.

## What this repo includes

- data intake and production enrichment scripts
- production, decline, downtime, and underperformance scoring
- opportunity creation and ranking
- evidence-backed opportunity dossiers
- operator workflow states and notes
- vendor matching and private opportunity sharing

## Quick start

1. Install dependencies:
   `pip install -r requirements.txt`
2. Refresh opportunities for an operator:
   `python scripts/refresh_opportunities.py`
3. Run the demo workflow:
   `python scripts/opportunity_demo.py`
4. Inspect a dossier and vendor share flow:
   `python scripts/opportunity_dossier.py`

## Current backbone

The included `oilfield_os.db` file is a working local snapshot used to validate the opportunity layer.
