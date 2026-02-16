#!/usr/bin/env python3
"""
Plan de reentrenamiento para el modelo de 3 horas
Este script prepara los datos y features para optimizar el modelo 3h
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

class Model3hRetrainer:
    """Preparación de reentrenamiento para modelo 3h"""
    
    def __init__(self):
        self.feature_importance = {}
    
    def load_historical_data(self, csv_file='bitacora_new_models.csv'):
        """Carga datos históricos para análisis"""
        df = pd.read_csv(csv_file)
        df['timestamp_pred'] = pd.to_datetime(df['timestamp_pred'])
        df['target_time'] = pd.to_datetime(df['target_time'])
        
        # Filtrar solo predicciones 3h completadas
        df_3h = df[(df['timeframe'] == '3h') & (df['status'] == 'COMPLETED')].copy()
        
        return df_3h
    
    def analyze_error_patterns(self, df):
        """Analiza patrones en errores del modelo 3h"""
        
        df['error_pct'] = (df['error_abs'] / df['entry_price']) * 100
        df['is_win'] = df['error_pct'] < 2.0
        
        print("="*80)
        print("📊 ANÁLISIS DE ERRORES - MODELO 3H")
        print("="*80)
        
        # Estadísticas generales
        total = len(df)
        wins = df['is_win'].sum()
        losses = total - wins
        
        print(f"\n📈 Estadísticas Generales:")
        print(f"   Total predicciones: {total:,}")
        print(f"   Wins (error <2%): {wins:,} ({wins/total*100:.2f}%)")
        print(f"   Losses (error >=2%): {losses:,} ({losses/total*100:.2f}%)")
        print(f"   Error promedio: {df['error_pct'].mean():.2f}%")
        print(f"   Error máximo: {df['error_pct'].max():.2f}%")
        
        # Analizar por dirección de predicción
        print(f"\n📊 Por Dirección:")
        for direction in df['direction_pred'].unique():
            df_dir = df[df['direction_pred'] == direction]
            win_rate = (df_dir['is_win'].sum() / len(df_dir)) * 100
            print(f"   {direction:4s}: {win_rate:5.2f}% win rate | {len(df_dir):,} predicciones")
        
        # Identificar rangos de precio problemáticos
        print(f"\n💰 Análisis por Rango de Precio:")
        df['price_range'] = pd.cut(df['entry_price'], bins=5)
        for price_range, group in df.groupby('price_range'):
            win_rate = (group['is_win'].sum() / len(group)) * 100
            print(f"   {price_range}: {win_rate:5.2f}% win rate | {len(group):,} predicciones")
        
        return df
    
    def generate_new_features_plan(self):
        """Genera plan de nuevas features a agregar"""
        
        new_features = {
            'Momentum Indicators': [
                'RSI (14 períodos)',
                'MACD (12, 26, 9)',
                'Stochastic Oscillator',
                'Rate of Change (ROC)'
            ],
            'Volatility Indicators': [
                'Bollinger Bands (20, 2)',
                'Average True Range (ATR)',
                'Standard Deviation (20 períodos)',
                'Historical Volatility'
            ],
            'Volume Indicators': [
                'Volume Moving Average',
                'On-Balance Volume (OBV)',
                'Volume Rate of Change',
                'Money Flow Index (MFI)'
            ],
            'Price Patterns': [
                'Moving Averages (SMA 7, 21, 50)',
                'EMA crossovers',
                'Price vs MA divergence',
                'Support/Resistance levels'
            ],
            'Time Features': [
                'Hour of day',
                'Day of week',
                'Time since last high/low',
                'Session (Asian/European/US)'
            ]
        }
        
        print("\n" + "="*80)
        print("🔧 PLAN DE NUEVAS FEATURES")
        print("="*80)
        
        for category, features in new_features.items():
            print(f"\n📌 {category}:")
            for feature in features:
                print(f"   • {feature}")
        
        return new_features
    
    def recommend_hyperparameters(self):
        """Recomienda ajustes de hiperparámetros"""
        
        recommendations = {
            'XGBoost': {
                'max_depth': '6 → 8 (aumentar complejidad)',
                'n_estimators': '100 → 200 (más árboles)',
                'learning_rate': '0.1 → 0.05 (más conservador)',
                'min_child_weight': '1 → 3 (reducir overfitting)',
                'subsample': '1.0 → 0.8 (bootstrap)',
                'colsample_bytree': '1.0 → 0.8 (feature sampling)'
            },
            'Training': {
                'cross_validation': 'TimeSeriesSplit con 5 folds',
                'validation_strategy': 'Walk-forward validation',
                'early_stopping': 'Rounds = 50',
                'objective': 'reg:squarederror (mantener)'
            }
        }
        
        print("\n" + "="*80)
        print("⚙️  AJUSTES RECOMENDADOS DE HIPERPARÁMETROS")
        print("="*80)
        
        for model, params in recommendations.items():
            print(f"\n🔹 {model}:")
            for param, value in params.items():
                print(f"   • {param}: {value}")
        
        return recommendations
    
    def create_retraining_schedule(self):
        """Crea calendario de reentrenamiento"""
        
        today = datetime.now()
        
        schedule = {
            'Fase 1 - Preparación': {
                'inicio': today,
                'fin': today + timedelta(days=2),
                'tareas': [
                    'Calcular nuevas features en datos históricos',
                    'Validar calidad de features',
                    'Preparar pipeline de preprocesamiento'
                ]
            },
            'Fase 2 - Experimentación': {
                'inicio': today + timedelta(days=2),
                'fin': today + timedelta(days=5),
                'tareas': [
                    'Entrenar múltiples configuraciones',
                    'Cross-validation con nuevas features',
                    'Seleccionar mejor modelo candidato'
                ]
            },
            'Fase 3 - Validación': {
                'inicio': today + timedelta(days=5),
                'fin': today + timedelta(days=7),
                'tareas': [
                    'Backtesting en datos recientes',
                    'Comparar con modelo actual',
                    'A/B testing en paper trading'
                ]
            },
            'Fase 4 - Despliegue': {
                'inicio': today + timedelta(days=7),
                'fin': today + timedelta(days=8),
                'tareas': [
                    'Desplegar modelo optimizado',
                    'Monitorear rendimiento inicial',
                    'Rollback plan si necesario'
                ]
            }
        }
        
        print("\n" + "="*80)
        print("📅 CALENDARIO DE REENTRENAMIENTO")
        print("="*80)
        
        for fase, details in schedule.items():
            print(f"\n{fase}")
            print(f"   📆 {details['inicio'].strftime('%Y-%m-%d')} → {details['fin'].strftime('%Y-%m-%d')}")
            print(f"   Tareas:")
            for tarea in details['tareas']:
                print(f"      • {tarea}")
        
        return schedule

def main():
    """Función principal"""
    
    print("\n🚀 INICIANDO PLAN DE REENTRENAMIENTO - MODELO 3H\n")
    
    retrainer = Model3hRetrainer()
    
    # 1. Cargar y analizar datos
    print("📊 Cargando datos históricos...")
    df = retrainer.load_historical_data()
    
    # 2. Analizar patrones de error
    df = retrainer.analyze_error_patterns(df)
    
    # 3. Generar plan de features
    new_features = retrainer.generate_new_features_plan()
    
    # 4. Recomendar hiperparámetros
    hyperparams = retrainer.recommend_hyperparameters()
    
    # 5. Crear calendario
    schedule = retrainer.create_retraining_schedule()
    
    # Resumen final
    print("\n" + "="*80)
    print("✅ PLAN DE REENTRENAMIENTO GENERADO")
    print("="*80)
    print("\n📋 Próximos pasos inmediatos:")
    print("   1. Revisar y aprobar plan de features")
    print("   2. Comenzar cálculo de nuevas features (Fase 1)")
    print("   3. Configurar experimentos de entrenamiento")
    print("   4. Establecer métricas de éxito")
    print("\n🎯 Objetivo: Aumentar win rate de 72.39% → >85%")
    print("⏱️  Timeline: 7-8 días para despliegue\n")

if __name__ == '__main__':
    main()
