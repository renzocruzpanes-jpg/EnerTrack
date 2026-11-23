# ⚡ EnerTrack — Household Energy & Cost Simulator

EnerTrack is a web-based household electricity consumption and cost simulator tailored for Philippine electric utilities (**BATELEC I**, **BATELEC II**, **Meralco**, and custom utility rates).

## Key Features
- **Multi-Utility Billing Engine:** Calculates 30-day kWh usage, base generation cost, additional charges, fixed fees, and 12% VAT.
- **Interactive Appliance Manager:** Quick-select presets or custom appliances with inline wattage and daily hours editing.
- **Single-Factor "What-If" Analyzer:** Compares switching an appliance's wattage or daily usage hours and projects monthly and annual savings.
- **Whole-House Simulation & Charts:** Interactive Chart.js doughnut and bar charts comparing normal usage against energy-saving scenarios.
- **SQLite Profile Persistence:** Save, load, and delete custom household setups (`enertrack.db`).
- **Smart Recommendations & Export:** Automatically highlights high-impact tips for the top-consuming appliance and supports CSV and print-friendly reports.

## Project Structure
```text
EnerTrack/
├── app.py              # Flask routes and API endpoints
├── calculator.py       # Energy & Philippine utility bill calculation engine
├── database.py         # SQLite database persistence layer
├── enertrack.db        # Auto-generated SQLite database
├── requirements.txt    # Python dependencies
├── README.md           # Project documentation
└── templates/
    └── index.html      # Bootstrap 5 & Chart.js dashboard frontend