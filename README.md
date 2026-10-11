# 🍽️ WasteWise AI — Predict Food Waste Before It Happens

> **WeMakeDevs Environmental Hacks 2026** — *Waste & Energy Track*  
> An intelligent full-stack food demand forecasting and waste prevention system designed for college canteens, hostels, cafeterias, and institutional dining halls.

---

## 📌 1. Project Overview & Objective

Food waste in institutional kitchens is largely an **informational failure**: chefs and managers are forced to guess next-day meal turnout without structured predictive insights. When demand is overestimated, huge pans of cooked food end up in trash dumpsters. When demand is underestimated, diners face shortages.

**WasteWise AI** tackles this problem at the root:
1. **Predicts Patron Demand Before Cooking:** Uses historical consumption records, day-of-week trends, academic schedules, holidays, and campus events.
2. **Recommends Calibrated Preparation Quantities:** Applies an asymmetric-loss preparation planner that optimizes safety buffers and rounds portions into practical kitchen batch sizes.
3. **Audits Actual vs. Predicted Outcomes:** Tracks recorded leftover meals and measured bin waste in kilograms, calculating actual savings and avoided waste.
4. **Delivers AI Waste Reduction Guidance:** Built with an **AWS Strands Agents SDK / Bedrock AI** advisory module, backed by a deterministic **Local Expert Rule Engine** fallback when cloud credentials are not configured.

---

## 🛠️ 2. Technology Stack

- **Frontend:** HTML5, CSS3 (Custom green & off-white design system, fully responsive), Vanilla JavaScript.
- **Visualizations:** Plotly.js (interactive multi-axis time-series, bar distributions, forecast intervals).
- **Backend:** Python with FastAPI (RESTful API, asynchronous handlers).
- **Database:** SQLite with SQLAlchemy ORM (ACID-compliant relational store).
- **Machine Learning:** Scikit-learn (`RandomForestRegressor`, `OneHotEncoder`, `ColumnTransformer`, `Pipeline`).
- **Data Analysis & Processing:** Pandas, NumPy.
- **Import / Export:** CSV parsing with duplicate detection, downloadable sample template.
- **Cloud / AI Integration:** AWS Strands Agents SDK (`strands-agents`) & Amazon Bedrock runtime with seamless local rule fallback.
- **Testing:** Pytest with FastAPI TestClient.

---

## 🚀 3. Quickstart & Installation Guide

### Prerequisites
- Python 3.10+ (compatible with Anaconda / Python 3.12 / 3.14)
- Web browser (Chrome, Edge, Firefox)

### Step 1: Clone or Navigate to Project
```bash
cd "c:\Users\HP\Desktop\PlateWise AI"
```

### Step 2: Configure Environment (Optional)
Copy `.env.example` to `.env`:
```bash
copy .env.example .env
```
*Note: WasteWise AI runs 100% locally out-of-the-box without paid API keys! If you have AWS credentials, provide `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` to enable cloud AI agent features.*

### Step 3: Run the Application (Single Command)
Run the automated launcher:
```bash
python run_app.py
```
*(If using Anaconda on Windows: `& "C:\Users\HP\anaconda3\python.exe" run_app.py`)*

The launcher will:
- ✅ Automatically initialize the SQLite database tables (`wastewise.db`).
- ✅ Seed 120 days of realistic synthetic demonstration canteen data across 5 menu items.
- ✅ Fit and chronologically validate the initial Random Forest regression pipeline.
- ✅ Start the FastAPI server on port `8000`.

### Step 4: Open in Your Browser
- 🌐 **Interactive Dashboard:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
- 📖 **FastAPI Swagger API Documentation:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 🧪 4. Running Automated Tests

Run the test suite covering API endpoints, data validation, ML feature engineering, and preparation planning:
```bash
python -m pytest tests -v
```
*(Or with Anaconda: `& "C:\Users\HP\anaconda3\python.exe" -m pytest tests -v`)*

---

## 📊 5. Exploratory Data Analysis (EDA)

Run the standalone reproducible exploratory analysis script:
```bash
python scripts/eda.py
```
Or open the interactive Jupyter notebook in `notebooks/eda.ipynb`.

### EDA Findings:
1. **Demand Cyclicality:** Mondays and Tuesdays have the highest attendance (~174 meals/day average), while Sundays drop to ~56 meals/day due to day scholars and weekend outings.
2. **Special Dish Surges:** Friday shows a 30% surge for *Chicken Biryani* (mean 223 portions).
3. **Outlier Investigation:** Statistical outliers (IQR method) correlate 100% with Tech Symposiums and Cultural Fests (surges) or Exam/Monsoon days (drops). They are genuine demand shocks, not data entry errors, and are retained to train event sensitivity.
4. **Historical Over-Preparation:** Prior to optimization, the canteen over-prepared by an average of 19.3%, discarding ~5.67 kg of food daily.

---

## 🧠 6. Machine Learning Demand Forecasting Workflow

### Features Used:
- **Calendar & Time Factors:** `day_of_week` (categorical), `day_of_month`, `month`, `is_weekend`, `is_holiday`.
- **Special Campus Events:** `has_event` (Tech Symposium, Finals, Cultural Fest, etc.).
- **Categorical Identifiers:** `menu_item`, `meal_category`.
- **Time-Series Lag Features (Strictly Historical — Zero Leakage):**
  - `lag_demand_1`: Patron demand from the immediate previous preparation of the same menu item.
  - `rolling_mean_3`: 3-day recent moving average demand.
  - `rolling_mean_7`: 7-day recent moving average demand.

### Chronological Train / Test Split:
Time-series forecasting cannot use random K-fold splits due to temporal leakage. WasteWise AI splits records **chronologically**:
- The first 80% of dates form the training set.
- The latest 20% of dates form the held-out test evaluation set.

### Model Comparison & Genuine Evaluation:
- **Baseline Model:** Historical Day-of-Week + Menu-Item median heuristic.
- **Production Model:** `RandomForestRegressor(n_estimators=100, max_depth=8, random_state=42)` combined with a `ColumnTransformer` (OneHotEncoder for categories + passthrough for numericals).
- **Held-Out Test Results:**
  - Baseline MAE: `13.26` meals
  - Random Forest MAE: `13.51` meals
  - Random Forest RMSE: `18.96` meals (vs Baseline RMSE: `22.85` meals)
  - Test $R^2$: `0.923`

---

## 📋 7. Smart Preparation Planner (Newsvendor Decision Rule)

Raw predicted demand is **not** the same as a kitchen preparation plan. Cooking exactly predicted demand risks running out of food when random variation occurs.

WasteWise AI solves this with an asymmetric cost formulation:
$$\text{Effective Buffer} = \text{Base Buffer} \times \sqrt{\frac{\text{Stockout Weight}}{\text{Waste Weight}}}$$
$$\text{Recommended Quantity} = \left\lceil \frac{\text{Predicted Demand} + \text{Buffer Meals}}{5} \right\rceil \times 5$$

1. **Safety Buffer:** Configurable by the kitchen manager (0% to 30%).
2. **Asymmetric Penalty:** Balances hungry student dissatisfaction ($1.2\times$ stockout weight) against food disposal costs ($1.0\times$ waste weight).
3. **Batch Sizing Constraint:** Canteen bulk pans cannot cook fractional meals; quantities automatically round to the nearest practical 5-portion batch.
4. **Transparent Kitchen Rationale:** Every recommendation generates an explicit, plain-English explanation of why this exact portion count was advised.

---

## 💡 8. AI Food-Waste Advisor & AWS Integration

### AWS Architecture:
- Uses the **AWS Strands Agents SDK** (`strands-agents`) and **Amazon Bedrock Runtime** (`boto3`) to synthesize operational insights when AWS credentials are provided in `.env`.
- **Model:** Claude 3 Sonnet on Amazon Bedrock.

### Local Expert Rule Engine Fallback:
When AWS credentials are not set, the advisor falls back instantly to a rule-based expert audit engine that:
1. **Surplus Calibration:** Identifies menu items with $>12\%$ recurring surplus and computes exact batch trims.
2. **Weekday Spike Alerts:** Flags low-attendance days to prevent overproduction.
3. **Hotspot Diagnostics:** Detects menu items generating the highest discarded kilograms and recommends staggered batch cooking (e.g. 60% early morning cook, 40% mid-lunch replenishment).
4. **Safe Surplus Food Redistribution Protocol:** Outlines temperature thresholds (hot above 60°C, cold below 5°C), 2-hour recovery windows, and logging procedures for campus charity dispatch.

---

## 📈 9. Longitudinal Impact & Counterfactual Waste Accounting

To prevent inflated claims, WasteWise AI separates **directly measured observations** from **counterfactual estimates**:
- **Discarded Food (kg):** Physical weight recorded on kitchen bin scales.
- **Waste Avoided (kg):** Calculated by comparing the historical baseline waste rate ($5.67\text{ kg} / 1000\text{ meals}$) against actual measured outcomes during the WasteWise AI optimized phase.
- **Cost Savings:** Direct ingredient procurement cost avoided.

---

## 📁 10. Project Directory Structure

```
PlateWise AI/
├── backend/
│   ├── config.py                 # Configuration and environment paths
│   ├── database.py               # SQLite engine & session setup
│   ├── models.py                 # SQLAlchemy ORM models
│   ├── schemas.py                # Pydantic validation schemas
│   ├── main.py                   # FastAPI application & REST endpoints
│   ├── ml/
│   │   ├── train.py              # Chronological training & feature engineering
│   │   ├── predict.py            # Demand prediction & confidence intervals
│   │   └── evaluate.py           # Evaluation metrics & actual vs predicted
│   ├── services/
│   │   ├── planner.py            # Preparation planner & asymmetric loss
│   │   ├── advisor.py            # AWS Strands / Local rule advisory engine
│   │   ├── analytics.py          # Dashboard KPIs & impact metrics
│   │   └── csv_service.py        # CSV import/export & template generation
│   └── requirements.txt          # Python dependencies
├── frontend/
│   ├── index.html                # Single-page dashboard application
│   ├── css/
│   │   └── styles.css            # Responsive green/off-white design system
│   └── js/
│       ├── app.js                # App router, toasts, modal handlers
│       ├── dashboard.js          # KPI stats & Plotly interactive charts
│       ├── entry.js              # Daily entry form & client validation
│       ├── prediction.js         # ML evaluation & interactive predictor
│       ├── planner.js            # Batch preparation planning controls
│       ├── advisor.js            # AI advisory & redistribution protocol
│       ├── analytics.js          # Longitudinal impact tracking
│       └── data_mgmt.js          # Historical data table, edit, delete, CSV upload
├── data/
│   ├── sample_meals.csv          # 600 synthetic meal records
│   └── sample_template.csv       # Blank CSV import template
├── scripts/
│   ├── generate_sample_data.py   # Synthetic data generator & DB seeder
│   └── eda.py                    # Exploratory data analysis script
├── notebooks/
│   └── eda.ipynb                 # Jupyter notebook for EDA
├── tests/
│   ├── test_api.py               # FastAPI testclient suite
│   ├── test_ml.py                # ML feature & training tests
│   └── test_planner.py           # Preparation planner tests
├── run_app.py                    # Single-command application launcher
├── .env.example                  # Environment configuration template
├── .gitignore                    # Git ignore file
└── README.md                     # Project documentation
```

---

## 👥 Hackathon Notes & Transparency

- **Track:** Waste & Energy (WeMakeDevs Environmental Hacks 2026).
- **Synthetic Data Notice:** The initial demo dataset is realistic synthetic data covering 120 days across 5 meal items. The dashboard clearly displays a "Demonstration Data (Synthetic)" badge when sample records are detected.
- **Beginner-Friendly:** Uses standard vanilla HTML5/CSS3/JavaScript without complex build steps or node_modules. Can be run directly from any laptop.
