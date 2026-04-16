# Kinetic Void - Bitcoin Fee Prediction Frontend

React + TypeScript + Vite frontend for the Bitcoin Mempool Fee Prediction API.

## Features

- **Cyberpunk terminal aesthetic** with CRT scanline effects
- **Real-time predictions** from XGBoost + LightGBM ensemble
- **Live mempool data** from mempool.space
- **Auto-refresh** every 30s (fees) / 60s (predictions)
- **Interactive execution** button for manual predictions
- **System logs** with color-coded messages

## Prerequisites

- Node.js 18+
- API running on `http://localhost:8000`

## Setup

```bash
cd frontend-react
npm install
npm run dev
```

Open http://localhost:5173

## Build for Production

```bash
npm run build
```

Output in `dist/` folder.

## API Endpoints Used

- `GET /health` - Health check
- `GET /fees/current` - Current mempool fees
- `GET /fees/predict?use_ensemble=true` - ML ensemble predictions

## Project Structure

```
src/
  components/     # React components
    Header.tsx
    FeeCard.tsx
    HexStream.tsx
    SystemLogs.tsx
    ExecuteButton.tsx
    Footer.tsx
    CrtOverlay.tsx
  hooks/
    useApi.ts      # API fetching hook
  types/
    api.ts         # TypeScript types
  App.tsx          # Main app
  main.tsx         # Entry point
```
