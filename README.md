# flOW

flOW is an operator opportunity engine built on top of SONRIS-style well, production, and permit data.

## What this repo includes

- data intake and production enrichment scripts
- production, decline, downtime, and underperformance scoring
- opportunity creation and ranking
- evidence-backed opportunity dossiers
- operator workflow states and notes
- vendor matching and private opportunity sharing

## Reproducible demo (no local snapshot required)

You can now generate a full working opportunity dataset from scratch.

### 1. Install dependencies
```
pip install -r requirements.txt
```

### 2. Bootstrap deterministic demo data
```
python scripts/bootstrap_demo_data.py
```

This will:
- create schema
- seed demo wells, production, and permits
- generate opportunities for operator `A1169`

### 3. Run the API
```
python api/operator_api.py
```

### 4. Example queries

Get opportunity board:
```
GET http://localhost:5000/operators/A1169/opportunities
```

Get opportunity detail:
```
GET http://localhost:5000/opportunities/1
```

Update status:
```
POST /opportunities/1/status
{
  "status": "reviewing"
}
```

Add note:
```
POST /opportunities/1/note
{
  "body": "Reviewing for workover"
}
```

Share with vendors:
```
POST /opportunities/1/share
```

## Legacy scripts

You can still run:
- `python scripts/refresh_opportunities.py`
- `python scripts/opportunity_demo.py`
- `python scripts/opportunity_dossier.py`

## Current backbone

The system is now fully reproducible without requiring a prebuilt database snapshot.
