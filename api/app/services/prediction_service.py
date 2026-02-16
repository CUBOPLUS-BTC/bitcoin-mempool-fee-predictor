"""
Prediction Service - Core business logic for predictions
"""

from datetime import datetime, timedelta
from typing import Optional
import logging
import pandas as pd
import numpy as np
import pickle
from pathlib import Path

logger = logging.getLogger(__name__)

class PredictionService:
    """Handles prediction logic with volatility filtering"""
    
    def __init__(self, model_manager, monitoring_service):
        self.model_manager = model_manager
        self.monitoring_service = monitoring_service
        
        # Load volatility filter config if exists
        try:
            import json
            config_path = Path(__file__).parent.parent.parent.parent / 'filter_config.json'
            if config_path.exists():
                with open(config_path, 'r') as f:
                    self.filter_config = json.load(f)
            else:
                self.filter_config = {
                    'volatility_threshold': 3.0,
                    'spread_threshold': 0.1,
                    'volume_ratio_threshold': 0.5
                }
        except Exception as e:
            logger.warning(f"Could not load filter config: {e}")
            self.filter_config = {
                'volatility_threshold': 3.0,
                'spread_threshold': 0.1,
                'volume_ratio_threshold': 0.5
            }
        
        # Confidence scores por timeframe (de análisis)
        self.confidence_scores = {
            '30m': 0.99,
            '1h': 0.97,
            '6h': 0.80,
            '12h': 0.78,
            '3h': 0.72
        }
    
    async def predict(
        self,
        timeframe: str,
        current_price: Optional[float] = None,
        use_volatility_filter: bool = True,
        model_version: Optional[str] = None,
        client_id: str = "anonymous"
    ) -> dict:
        """
        Make prediction with volatility filtering
        
        Args:
            timeframe: Prediction horizon
            current_price: Current BTC price (optional)
            use_volatility_filter: Enable volatility protection
            model_version: Specific model version
            client_id: Client identifier
        
        Returns:
            Prediction result dictionary
        """
        
        # Obtener precio actual si no se proporciona
        if current_price is None:
            current_price = await self._fetch_current_price()
        
        # Obtener precios recientes para volatilidad
        recent_prices = await self._fetch_recent_prices()
        
        # Volatility filter check
        volatility_allowed = True
        volatility_pct = None
        
        if use_volatility_filter:
            volatility_pct = self._calculate_volatility(recent_prices)
            threshold = self.filter_config['volatility_threshold']
            
            if volatility_pct > threshold:
                volatility_allowed = False
                raise ValueError(
                    f"Prediction blocked: High volatility {volatility_pct:.2f}% > {threshold}%"
                )
        
        # Hacer predicción con modelo
        try:
            model = self.model_manager.get_model(model_version)
            predicted_price = self._predict_with_model(
                model=model,
                current_price=current_price,
                recent_prices=recent_prices,
                timeframe=timeframe
            )
            
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            raise ValueError(f"Failed to generate prediction: {e}")
        
        # Calcular métricas
        direction = 'UP' if predicted_price > current_price else 'DOWN'
        change_pct = ((predicted_price - current_price) / current_price) * 100
        horizon_minutes = self._timeframe_to_minutes(timeframe)
        target_time = datetime.now() + timedelta(minutes=horizon_minutes)
        confidence = self.confidence_scores.get(timeframe, 0.5)
        
        # Determinar versión del modelo usada
        used_version = self.model_manager.get_model_version(model_version)
        
        return {
            "timeframe": timeframe,
            "current_price": current_price,
            "predicted_price": predicted_price,
            "direction": direction,
            "change_pct": round(change_pct, 2),
            "confidence": confidence,
            "target_time": target_time,
            "model_version": used_version,
            "volatility_allowed": volatility_allowed,
            "volatility_pct": volatility_pct,
            "timestamp": datetime.now()
        }
    
    def _timeframe_to_minutes(self, timeframe: str) -> int:
        """Convert timeframe string to minutes"""
        mapping = {
            '30m': 30,
            '1h': 60,
            '3h': 180,
            '6h': 360,
            '12h': 720
        }
        return mapping.get(timeframe, 60)
    
    async def _fetch_current_price(self) -> float:
        """Fetch current BTC price from exchange"""
        try:
            import ccxt
            exchange = ccxt.kraken()
            ticker = exchange.fetch_ticker('BTC/USD')
            return ticker['last']
        except Exception as e:
            logger.error(f"Error fetching price: {e}")
            # Fallback: leer de bitácora
            try:
                df = pd.read_csv('bitacora_new_models.csv')
                df['timestamp_pred'] = pd.to_datetime(df['timestamp_pred'])
                latest = df.sort_values('timestamp_pred').iloc[-1]
                return latest['entry_price']
            except:
                raise ValueError("Could not fetch current price")
    
    async def _fetch_recent_prices(self, hours: int = 12) -> list:
        """Fetch recent prices for volatility calculation"""
        try:
            import ccxt
            exchange = ccxt.kraken()
            ohlcv = exchange.fetch_ohlcv('BTC/USD', '30m', limit=24)
            prices = [candle[4] for candle in ohlcv]  # close prices
            return prices
        except Exception as e:
            logger.error(f"Error fetching recent prices: {e}")
            return [65000.0] * 24  # Fallback
    
    def _calculate_volatility(self, prices: list) -> float:
        """Calculate price volatility percentage"""
        if len(prices) < 2:
            return 0.0
        
        returns = np.diff(prices) / prices[:-1]
        volatility = np.std(returns) * np.sqrt(24) * 100  # Annualized volatility as %
        return volatility
    
    def _predict_with_model(
        self, 
        model, 
        current_price: float, 
        recent_prices: list,
        timeframe: str
    ) -> float:
        """
        Make prediction using the model
        
        This is a simplified version. In production, you would:
        1. Prepare features exactly as during training
        2. Use the actual model's predict method
        3. Post-process the output
        """
        try:
            # Si el modelo tiene un método predict
            if hasattr(model, 'predict'):
                # Preparar features básicas
                features = self._prepare_basic_features(recent_prices)
                prediction = model.predict(features)
                
                # Si la predicción es un cambio porcentual, convertir a precio
                if abs(prediction[0]) < 10:  # Likely a percentage
                    predicted_price = current_price * (1 + prediction[0] / 100)
                else:  # Already a price
                    predicted_price = prediction[0]
                
                return float(predicted_price)
            else:
                # Fallback: simple trend-based prediction
                logger.warning("Model doesn't have predict method, using fallback")
                return self._simple_trend_prediction(current_price, recent_prices, timeframe)
                
        except Exception as e:
            logger.error(f"Model prediction failed: {e}, using fallback")
            return self._simple_trend_prediction(current_price, recent_prices, timeframe)
    
    def _prepare_basic_features(self, recent_prices: list) -> np.ndarray:
        """Prepare basic features for model"""
        # Take last 24 prices
        prices = recent_prices[-24:] if len(recent_prices) >= 24 else recent_prices
        
        # Calculate simple features
        features = []
        if len(prices) > 0:
            # Moving averages
            ma_7 = np.mean(prices[-7:]) if len(prices) >= 7 else prices[-1]
            ma_21 = np.mean(prices[-21:]) if len(prices) >= 21 else ma_7
            
            # Price changes
            price_change_1h = (prices[-1] - prices[-2]) / prices[-2] if len(prices) >= 2 else 0
            price_change_3h = (prices[-1] - prices[-4]) / prices[-4] if len(prices) >= 4 else 0
            
            # Volatility
            volatility = self._calculate_volatility(prices)
            
            features = [ma_7, ma_21, price_change_1h, price_change_3h, volatility]
        
        return np.array([features])
    
    def _simple_trend_prediction(
        self, 
        current_price: float, 
        recent_prices: list,
        timeframe: str
    ) -> float:
        """Simple trend-based prediction as fallback"""
        if len(recent_prices) < 2:
            return current_price
        
        # Calculate recent trend
        recent = recent_prices[-6:] if len(recent_prices) >= 6 else recent_prices
        trend = (recent[-1] - recent[0]) / recent[0]
        
        # Predict based on trend and timeframe
        timeframe_multipliers = {
            '30m': 0.3,
            '1h': 0.5,
            '3h': 1.0,
            '6h': 1.5,
            '12h': 2.0
        }
        
        multiplier = timeframe_multipliers.get(timeframe, 1.0)
        predicted_change = trend * multiplier
        predicted_price = current_price * (1 + predicted_change)
        
        return predicted_price
