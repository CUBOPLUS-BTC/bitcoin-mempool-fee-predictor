# Bitcoin On-Chain Predictive Framework

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![XGBoost](https://img.shields.io/badge/XGBoost-1.7-orange)
![Status](https://img.shields.io/badge/Status-Prototype-green)

## ⚡ Overview

This repository contains a **Machine Learning framework** developed during the **CUBO+** program in El Salvador. 

While initially designed to analyze Bitcoin price action relative to on-chain metrics, the underlying architecture—utilizing **XGBoost** for time-series regression—is engineered to process high-dimensional data from the Bitcoin blockchain.

**Core Capabilities:**
- Ingestion of raw on-chain data via exchange APIs
- Multi-horizon time-series prediction (30min, 60min, 180min)
- Pattern recognition in transaction volume and block density
- **Potential Application:** Forecasting mempool congestion events and optimizing fee estimation logic based on historical throughput

## 🛠 Tech Stack

- **Core:** Python 3.9+
- **ML/AI:** XGBoost, Scikit-learn
- **Data Processing:** Pandas, NumPy
- **Technical Analysis:** TA-Lib indicators
- **API:** FastAPI (for model serving)
- **Data Sources:** CCXT (exchange data)

## 🏗 Architecture

The framework follows a modular MLOps architecture:

```
Data Ingestion → Feature Engineering → Model Training → Inference → API Serving
      ↓                  ↓                   ↓              ↓           ↓
   (ccxt)          (technical           (XGBoost)    (prediction)  (FastAPI)
                   indicators)                        service
```

### Key Components

- **`src/ingestion.py`** - Fetches OHLCV data from cryptocurrency exchanges
- **`src/features.py`** - Generates technical indicators and rolling statistics
- **`src/train.py`** - Trains multi-horizon XGBoost models
- **`src/inference.py`** - Loads models and makes predictions
- **`api/`** - FastAPI server for real-time predictions
- **`scripts/`** - Operational scripts (retraining, monitoring, backtesting)

## 🚀 Installation

### Prerequisites

- Python 3.9 or higher
- pip package manager
- Virtual environment (recommended)

### Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/marchelo23/bitcoin-onchain-framework.git
   cd bitcoin-onchain-framework
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

## 📊 Usage

### Training Models

Train models for all prediction horizons:

```bash
python -m src.train --all --config config/config.yaml
```

Train a specific horizon:

```bash
python -m src.train --horizon 60
```

### Making Predictions

Run live predictions:

```bash
python scripts/live_predict.py
```

### Starting the API Server

```bash
cd api
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Access the API documentation at: `http://localhost:8000/docs`

### Running Tests

```bash
pytest tests/
```

## 📈 Model Performance

The XGBoost models are trained on historical Bitcoin data with the following horizons:

- **30-minute predictions** - Short-term market movements
- **60-minute predictions** - Medium-term trends
- **180-minute predictions** - Extended trend forecasting

Models are evaluated using:
- RMSE (Root Mean Squared Error)
- MAE (Mean Absolute Error)
- Directional Accuracy
- R² Score

## 🔮 Roadmap & Vision

The current iteration demonstrates the viability of using gradient boosting on standard blockchain metrics. The next phase of development focuses on:

### Phase 1: Network Analysis Enhancement
- **Mempool Visualization:** Adapting the predictive model to visualize incoming transaction pressure
- **Fee Market Analysis:** Using the regression model to suggest optimal fee rates during high-congestion periods
- **Real-time Monitoring:** Building dashboards for network health metrics

### Phase 2: Integration & Deployment
- **API Enhancement:** RESTful endpoints for third-party integrations
- **Docker Containerization:** Easy deployment across environments
- **CI/CD Pipeline:** Automated testing and deployment

### Phase 3: Advanced Features
- **Ensemble Methods:** Combining multiple models for improved accuracy
- **On-Chain Metrics:** Integration with blockchain explorers for richer features
- **Automated Retraining:** Scheduled model updates with fresh data

### Long-term Vision
- **Explorer Integration:** Exploring compatibility with open-source explorer backends (e.g., mempool.space architecture)
- **Multi-Asset Support:** Extending framework to other cryptocurrencies
- **Community Contributions:** Open-source collaboration for feature development

## 📚 Documentation

- [Architecture Guide](docs/ARCHITECTURE.md) - System design and component details
- [API Documentation](docs/API_GUIDE.md) - REST API endpoints and usage
- [Deployment Guide](docs/DEPLOYMENT.md) - Production deployment instructions

## 🧪 Project Status

This project is currently in **prototype** stage. It was developed as part of the CUBO+ accelerator program and serves as a proof-of-concept for applying machine learning to Bitcoin blockchain data analysis.

**Current Features:**
- ✅ Multi-horizon time-series prediction
- ✅ Automated feature engineering
- ✅ FastAPI serving layer
- ✅ Backtesting framework
- ✅ Model monitoring and retraining scripts

**In Development:**
- 🚧 Real-time mempool congestion prediction
- 🚧 Fee optimization algorithms
- 🚧 Production deployment pipeline

## 👤 Author

**Marcelo Guerra**  
CUBO+ Developer & ESEN Student  
El Salvador Bitcoin Community

## 📄 License

This project is open-source and intended for educational and research purposes within the Bitcoin ecosystem.

## 🙏 Acknowledgments

- **CUBO+ Program** - For providing the platform and resources to develop this project
- **Bitcoin Community in El Salvador** - For inspiration and support
- **Open Source Contributors** - XGBoost, FastAPI, and all the amazing libraries used

---

**Note:** This framework is designed for research and educational purposes. Always conduct thorough testing before using any predictions in production or financial decision-making.
