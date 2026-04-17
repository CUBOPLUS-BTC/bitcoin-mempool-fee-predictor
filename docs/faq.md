# ❓ Frequently Asked Questions

Common questions and troubleshooting tips.

---

## 🚀 Getting Started

### Q: What are the minimum requirements?

**A:** 
- Python 3.9+
- 2GB RAM (4GB recommended for training)
- 1GB disk space
- Internet connection for mempool.space API

### Q: Can I run this without Bitcoin Core?

**A:** Yes! The framework primarily uses mempool.space API. Bitcoin Core RPC is optional for additional data sources.

### Q: Do I need a GPU?

**A:** No. Training and inference run fine on CPU. Models are lightweight (XGBoost and LightGBM).

---

## 🔧 Installation Issues

### Q: `ModuleNotFoundError: No module named 'src'`

**A:** Run from the project root directory:
```bash
cd /path/to/bitcoin-onchain-framework
python -m api.main
```

Or install in editable mode:
```bash
pip install -e .
```

### Q: `API_KEY required in production`

**A:** Set the environment variable:
```bash
export API_KEY=$(openssl rand -hex 32)
export ENV=production  # or development to skip
```

### Q: Frontend shows "403 Forbidden"

**A:** Configure the API key in frontend `.env`:
```bash
cd frontend-react
echo "VITE_API_KEY=your-api-key" >> .env
```

### Q: `npm install` shows vulnerability warnings

**A:** Update dependencies:
```bash
cd frontend-react
rm -rf node_modules package-lock.json
npm install
npm audit
```

---

## 🔐 Security Questions

### Q: Is the API secure?

**A:** Yes, security score is 8.5/10. Features include:
- API key authentication
- Rate limiting
- CORS restrictions
- Security headers (CSP, HSTS, etc.)
- Model integrity verification
- Error sanitization

See [Security Guide](./security.md) for details.

### Q: How do I rotate the API key?

**A:** Generate a new key and restart:
```bash
export API_KEY=$(openssl rand -hex 32)
# Restart the API server
```

### Q: Can I disable authentication in production?

**A:** Not recommended. But you can:
```bash
export ENV=development  # Disables API key requirement
```

⚠️ Only do this in trusted, isolated environments.

### Q: How do I verify model integrity?

**A:** Generate and check hashes:
```bash
python scripts/generate_model_hashes.py
export STRICT_MODEL_INTEGRITY=true
```

---

## 📊 Model & Prediction Questions

### Q: How accurate are the predictions?

**A:** Typical performance:
- **MAE**: 2-5 sat/vB (mean absolute error)
- **Stuck Rate**: <10% (predictions that fail to confirm)
- **Savings**: 15-30% vs always paying highest fee

Accuracy varies with mempool conditions. See `results/` for detailed metrics.

### Q: How often are models retrained?

**A:** Automatically every hour via GitHub Actions.

### Q: Can I use my own models?

**A:** Yes! Place them in `models/production/` with the naming convention:
- `xgb_fee_{horizon}block_latest.json`
- `lgbm_fee_{horizon}block_latest.txt`

### Q: What block horizons are supported?

**A:** 1, 3, and 6 blocks by default. Configurable in `config/config.yaml`.

### Q: Why two models (XGBoost + LightGBM)?

**A:** Ensemble approach:
- Reduces overfitting
- Improves generalization
- Provides confidence intervals
- XGBoost: 60% weight, LightGBM: 40% weight

---

## 🔌 API Usage

### Q: What's the rate limit?

**A:** 
- `/fees/predict`: 30 requests/minute
- `/fees/history`: 10 requests/minute
- `/models`: 20 requests/minute
- `/health`, `/`: No limit

### Q: Can I get predictions without authentication?

**A:** Only the health endpoint:
```bash
curl http://localhost:8000/health
```

All prediction endpoints require `X-API-Key` header.

### Q: How do I get an API key?

**A:** Generate one:
```bash
openssl rand -hex 32
```

Or use Python:
```python
import secrets
print(secrets.token_hex(32))
```

### Q: What format are timestamps in?

**A:** ISO 8601 format: `2026-04-17T17:30:00Z`

---

## 🐛 Troubleshooting

### Q: API returns "Rate limit exceeded"

**A:** Wait 1 minute or check your request frequency. Implement client-side rate limiting:
```javascript
// Wait 2 seconds between requests
await new Promise(r => setTimeout(r, 2000));
```

### Q: Predictions seem inaccurate

**A:** Check:
1. Models are recent (`/models` endpoint)
2. No data collection gaps in logs
3. Try with different horizons (1, 3, 6 blocks)

### Q: Frontend won't connect to API

**A:** Check:
1. API is running: `curl http://localhost:8000/health`
2. CORS origins configured: `ALLOWED_ORIGINS` includes frontend URL
3. No firewall blocking port 8000

### Q: GitHub Actions are failing

**A:** Common causes:
1. **Push conflicts**: Already fixed in workflows
2. **Missing secrets**: Check `API_KEY` in repo settings
3. **Rate limits**: mempool.space API limits

Check Actions logs for specific errors.

### Q: Models won't load

**A:** Check:
1. Files exist in `models/production/`
2. File permissions are readable
3. Model hashes are valid (if strict mode enabled)
4. Check logs: `tail logs/api.log`

---

## 💰 Fee Prediction Questions

### Q: What fee should I use?

**A:** Depends on urgency:
- **Urgent** (next block): Use `recommendation.urgent`
- **Normal** (3-6 blocks): Use `recommendation.normal`
- **Economic** (when mempool clears): Use `recommendation.economic`

### Q: Why does the confidence score matter?

**A:** Higher confidence = more reliable prediction:
- `>0.8`: High confidence
- `0.5-0.8`: Medium confidence
- `<0.5`: Low confidence (volatile mempool)

### Q: How do I calculate transaction fee?

**A:** 
```
fee_sats = predicted_fee_sat_vb * transaction_size_vbytes
```

Example: 20 sat/vB × 250 vB = 5000 sats

---

## 🔧 Configuration

### Q: How do I change the API port?

**A:** Set environment variable:
```bash
export API_PORT=8080
```

### Q: Can I use a different mempool API?

**A:** Currently optimized for mempool.space. To use another:
1. Modify `src/ingestion.py`
2. Update data parsing logic
3. Adjust feature engineering if needed

### Q: How do I adjust prediction horizons?

**A:** Edit `config/config.yaml`:
```yaml
training:
  horizons:
    - 1
    - 3
    - 6
    - 12  # Add custom horizon
```

---

## 📈 Performance

### Q: How much RAM does training need?

**A:** 
- Inference: ~500MB
- Training: ~2-4GB (depends on dataset size)

### Q: Can I run this on a Raspberry Pi?

**A:** Yes, for inference only. Training requires more resources.

### Q: API is slow to respond

**A:** Check:
1. Model loading (first request after restart)
2. Network latency to mempool.space
3. Database/query performance
4. Enable caching (already enabled by default)

---

## 🤝 Contributing

### Q: How can I contribute?

**A:** See [Contributing Guide](./contributing.md). Areas:
- Bug reports
- Feature requests
- Documentation
- Code improvements
- Testing

### Q: What license is this under?

**A**: Open source for educational and research purposes. See LICENSE file.

### Q: How do I report a security vulnerability?

**A:** Email: security@example.com (do not open public issue)

---

## 📞 Still Need Help?

- **GitHub Issues**: [Create an issue](https://github.com/CUBOPLUS-BTC/bitcoin-mempool-fee-predictor/issues)
- **Documentation**: Check other docs in this folder
- **Logs**: Check `logs/` directory for detailed error messages

---

## 🔗 Related Questions

- [Installation Guide](./installation.md)
- [API Reference](./api-reference.md)
- [Security Guide](./security.md)
- [Architecture](./architecture.md)
