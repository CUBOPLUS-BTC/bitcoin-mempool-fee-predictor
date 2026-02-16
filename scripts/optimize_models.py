#!/usr/bin/env python3
"""
Script de optimización para modelos BTC
Implementa filtros de volatilidad y mejoras recomendadas
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

class ModelOptimizer:
    """Optimizador de modelos de predicción BTC"""
    
    def __init__(self, volatility_threshold=3.0):
        """
        Args:
            volatility_threshold: Umbral de volatilidad (%) para filtrar predicciones
        """
        self.volatility_threshold = volatility_threshold
        self.confidence_scores = {
            '30m': 0.99,
            '1h': 0.97,
            '6h': 0.80,
            '12h': 0.78,
            '3h': 0.72
        }
    
    def calculate_recent_volatility(self, df, lookback_minutes=60):
        """
        Calcula volatilidad reciente basada en cambios de precio
        
        Args:
            df: DataFrame con datos de precio
            lookback_minutes: Ventana de tiempo para calcular volatilidad
        
        Returns:
            float: Volatilidad como porcentaje
        """
        if len(df) < 2:
            return 0.0
        
        # Calcular cambio porcentual en ventana de tiempo
        recent_prices = df.tail(lookback_minutes // 30)  # Asumiendo datos cada 30 min
        
        if len(recent_prices) < 2:
            return 0.0
        
        price_change = ((recent_prices['entry_price'].iloc[-1] - 
                        recent_prices['entry_price'].iloc[0]) / 
                       recent_prices['entry_price'].iloc[0]) * 100
        
        return abs(price_change)
    
    def should_trade(self, timeframe, current_volatility, spread_pct=0.0, volume_ratio=1.0):
        """
        Determina si se debe realizar una predicción/operación
        
        Args:
            timeframe: Horizonte temporal ('30m', '1h', etc)
            current_volatility: Volatilidad actual (%)
            spread_pct: Spread bid-ask (%)
            volume_ratio: Ratio del volumen actual vs promedio 24h
        
        Returns:
            dict: {should_trade: bool, reason: str, confidence: float}
        """
        
        # Verificar volatilidad
        if current_volatility > self.volatility_threshold:
            return {
                'should_trade': False,
                'reason': f'Alta volatilidad: {current_volatility:.2f}% > {self.volatility_threshold}%',
                'confidence': 0.0
            }
        
        # Verificar spread
        if spread_pct > 0.1:
            return {
                'should_trade': False,
                'reason': f'Spread muy alto: {spread_pct:.2f}% > 0.1%',
                'confidence': 0.0
            }
        
        # Ajustar confianza según volumen
        base_confidence = self.confidence_scores.get(timeframe, 0.5)
        
        if volume_ratio < 0.5:
            adjusted_confidence = base_confidence * 0.8
            reason = 'Bajo volumen - confianza reducida 20%'
        else:
            adjusted_confidence = base_confidence
            reason = 'Condiciones aceptables'
        
        return {
            'should_trade': True,
            'reason': reason,
            'confidence': adjusted_confidence
        }
    
    def ensemble_prediction(self, predictions):
        """
        Combina predicciones de múltiples timeframes usando voto ponderado
        
        Args:
            predictions: dict {timeframe: predicted_price}
        
        Returns:
            dict: {weighted_prediction: float, consensus_strength: float}
        """
        
        if not predictions:
            return {'weighted_prediction': None, 'consensus_strength': 0.0}
        
        weighted_sum = 0.0
        total_weight = 0.0
        
        for tf, price in predictions.items():
            confidence = self.confidence_scores.get(tf, 0.5)
            weighted_sum += price * confidence
            total_weight += confidence
        
        weighted_prediction = weighted_sum / total_weight if total_weight > 0 else None
        
        # Calcular fuerza del consenso (cuán cerca están las predicciones)
        if len(predictions) > 1:
            prices = list(predictions.values())
            std_dev = np.std(prices)
            mean_price = np.mean(prices)
            consensus_strength = 1.0 - min(1.0, (std_dev / mean_price) * 10)
        else:
            consensus_strength = self.confidence_scores.get(list(predictions.keys())[0], 0.5)
        
        return {
            'weighted_prediction': weighted_prediction,
            'consensus_strength': consensus_strength
        }
    
    def detect_anomalies(self, df):
        """
        Detecta anomalías en predicciones recientes
        
        Returns:
            dict: Información sobre anomalías detectadas
        """
        df_recent = df.tail(10)  # Últimas 10 predicciones
        
        anomalies = {
            'consecutive_errors': 0,
            'high_error_rate': False,
            'should_pause': False
        }
        
        if len(df_recent) == 0:
            return anomalies
        
        # Calcular errores > 5%
        df_recent['error_pct'] = (df_recent['error_abs'] / df_recent['entry_price']) * 100
        high_errors = df_recent['error_pct'] > 5.0
        
        # Contar errores consecutivos
        consecutive = 0
        for is_error in high_errors:
            if is_error:
                consecutive += 1
            else:
                consecutive = 0
        
        anomalies['consecutive_errors'] = consecutive
        
        # Verificar tasa de error alta
        error_rate = high_errors.sum() / len(df_recent)
        anomalies['high_error_rate'] = error_rate > 0.3
        
        # Decidir si pausar trading
        anomalies['should_pause'] = consecutive >= 3 or error_rate > 0.5
        
        return anomalies
    
    def generate_trading_report(self, df):
        """Genera reporte de recomendaciones de trading"""
        
        print("\n" + "="*80)
        print("🎯 RECOMENDACIONES DE TRADING - OPTIMIZACIÓN ACTIVA")
        print("="*80)
        
        # Analizar últimas predicciones
        df_recent = df[df['status'] == 'COMPLETED'].tail(50)
        
        print(f"\n📊 Análisis de últimas 50 predicciones:")
        print("-"*80)
        
        for tf in ['30m', '1h', '3h', '6h', '12h']:
            df_tf = df_recent[df_recent['timeframe'] == tf]
            
            if len(df_tf) > 0:
                df_tf = df_tf.copy()
                df_tf['error_pct'] = (df_tf['error_abs'] / df_tf['entry_price']) * 100
                win_rate = (df_tf['error_pct'] < 2.0).sum() / len(df_tf) * 100
                avg_error = df_tf['error_pct'].mean()
                
                confidence = self.confidence_scores.get(tf, 0.5)
                
                # Determinar recomendación
                if win_rate > 95:
                    status = "✅ EXCELENTE"
                elif win_rate > 80:
                    status = "🟢 BUENO"
                elif win_rate > 70:
                    status = "🟡 ACEPTABLE"
                else:
                    status = "🔴 MEJORAR"
                
                print(f"{tf:4s}: {status:15s} | Win Rate: {win_rate:5.1f}% | "
                      f"Error: {avg_error:4.2f}% | Confianza: {confidence*100:.0f}%")
        
        # Detectar anomalías
        anomalies = self.detect_anomalies(df_recent)
        
        print(f"\n⚠️  DETECCIÓN DE ANOMALÍAS:")
        print("-"*80)
        print(f"Errores consecutivos (>5%): {anomalies['consecutive_errors']}")
        print(f"Tasa de error alta: {'SÍ' if anomalies['high_error_rate'] else 'NO'}")
        
        if anomalies['should_pause']:
            print("\n🛑 RECOMENDACIÓN: PAUSAR TRADING AUTOMÁTICO")
            print("   Razón: Demasiados errores consecutivos o tasa muy alta")
        else:
            print("\n✅ Trading automático puede continuar")
        
        print("\n💡 ESTRATEGIA RECOMENDADA:")
        print("-"*80)
        print("1. PRIORIZAR: 30m y 1h (máxima confianza)")
        print("2. CONFIRMAR: Usar múltiples timeframes para validación")
        print("3. EVITAR: Predicciones 3h sin confirmación de otros TF")
        print("4. FILTRAR: No operar si volatilidad reciente > 3%")
        
        print("\n" + "="*80 + "\n")

def main():
    """Función principal"""
    
    print("🚀 Iniciando optimización de modelos...")
    
    # Cargar datos
    df = pd.read_csv('bitacora_new_models.csv')
    df['timestamp_pred'] = pd.to_datetime(df['timestamp_pred'])
    
    # Crear optimizador
    optimizer = ModelOptimizer(volatility_threshold=3.0)
    
    # Generar reporte
    optimizer.generate_trading_report(df)
    
    # Ejemplo de uso del filtro de volatilidad
    print("📋 EJEMPLO DE USO DEL FILTRO:")
    print("-"*80)
    
    test_cases = [
        {'timeframe': '30m', 'volatility': 1.5, 'spread': 0.05, 'volume': 1.2},
        {'timeframe': '3h', 'volatility': 4.2, 'spread': 0.08, 'volume': 0.9},
        {'timeframe': '1h', 'volatility': 2.1, 'spread': 0.15, 'volume': 1.0},
    ]
    
    for case in test_cases:
        result = optimizer.should_trade(
            case['timeframe'],
            case['volatility'],
            case['spread'],
            case['volume']
        )
        
        status = "✅ OPERAR" if result['should_trade'] else "🛑 NO OPERAR"
        print(f"\n{status}")
        print(f"  Timeframe: {case['timeframe']}")
        print(f"  Volatilidad: {case['volatility']:.1f}%")
        print(f"  Razón: {result['reason']}")
        print(f"  Confianza: {result['confidence']*100:.0f}%")
    
    print("\n" + "="*80)
    print("✅ Optimización completada")

if __name__ == '__main__':
    main()
