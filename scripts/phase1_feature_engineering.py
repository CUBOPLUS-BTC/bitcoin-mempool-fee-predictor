#!/usr/bin/env python3
"""
Feature Engineering para Modelo 3h - Fase 1
Calcula todos los indicadores técnicos necesarios para el reentrenamiento
"""

import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class FeatureEngineer:
    """Ingeniero de características para modelo BTC"""
    
    def __init__(self):
        self.features_calculated = []
    
    def calculate_rsi(self, prices, period=14):
        """Relative Strength Index"""
        deltas = np.diff(prices)
        seed = deltas[:period+1]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        rs = up / down if down != 0 else 0
        rsi = np.zeros_like(prices)
        rsi[:period] = 100. - 100. / (1. + rs)
        
        for i in range(period, len(prices)):
            delta = deltas[i - 1]
            if delta > 0:
                upval = delta
                downval = 0.
            else:
                upval = 0.
                downval = -delta
            
            up = (up * (period - 1) + upval) / period
            down = (down * (period - 1) + downval) / period
            rs = up / down if down != 0 else 0
            rsi[i] = 100. - 100. / (1. + rs)
        
        return rsi
    
    def calculate_macd(self, prices, fast=12, slow=26, signal=9):
        """Moving Average Convergence Divergence"""
        exp1 = pd.Series(prices).ewm(span=fast, adjust=False).mean()
        exp2 = pd.Series(prices).ewm(span=slow, adjust=False).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        histogram = macd - signal_line
        return macd.values, signal_line.values, histogram.values
    
    def calculate_bollinger_bands(self, prices, period=20, std_dev=2):
        """Bollinger Bands"""
        sma = pd.Series(prices).rolling(window=period).mean()
        std = pd.Series(prices).rolling(window=period).std()
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        return upper_band.values, sma.values, lower_band.values
    
    def calculate_atr(self, high, low, close, period=14):
        """Average True Range"""
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        atr = pd.Series(tr).rolling(window=period).mean()
        return atr.values
    
    def calculate_moving_averages(self, prices):
        """SMAs de diferentes períodos"""
        sma_7 = pd.Series(prices).rolling(window=7).mean().values
        sma_21 = pd.Series(prices).rolling(window=21).mean().values
        sma_50 = pd.Series(prices).rolling(window=50).mean().values
        
        ema_7 = pd.Series(prices).ewm(span=7, adjust=False).mean().values
        ema_21 = pd.Series(prices).ewm(span=21, adjust=False).mean().values
        
        return {
            'sma_7': sma_7,
            'sma_21': sma_21,
            'sma_50': sma_50,
            'ema_7': ema_7,
            'ema_21': ema_21
        }
    
    def calculate_volatility(self, prices, period=20):
        """Volatilidad histórica"""
        returns = np.diff(np.log(prices))
        volatility = pd.Series(returns).rolling(window=period).std() * np.sqrt(365)
        return np.concatenate([[0], volatility.values])
    
    def add_time_features(self, df):
        """Features basadas en tiempo"""
        df['hour'] = df['timestamp_pred'].dt.hour
        df['day_of_week'] = df['timestamp_pred'].dt.dayofweek
        df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
        
        # Sesiones de trading
        df['session'] = 'other'
        df.loc[df['hour'].between(0, 8), 'session'] = 'asian'
        df.loc[df['hour'].between(8, 16), 'session'] = 'european'
        df.loc[df['hour'].between(16, 23), 'session'] = 'us'
        
        return df
    
    def engineer_features(self, df):
        """Calcula todas las features para el dataset"""
        
        print("\n🔧 INICIANDO FEATURE ENGINEERING")
        print("="*80)
        
        # Preparar datos
        df = df.sort_values('timestamp_pred').copy()
        prices = df['entry_price'].values
        
        print(f"\n📊 Dataset: {len(df):,} registros")
        print(f"   Rango de fechas: {df['timestamp_pred'].min()} → {df['timestamp_pred'].max()}")
        
        # 1. RSI
        print("\n1️⃣  Calculando RSI...")
        df['rsi_14'] = self.calculate_rsi(prices, 14)
        self.features_calculated.append('rsi_14')
        
        # 2. MACD
        print("2️⃣  Calculando MACD...")
        macd, signal, histogram = self.calculate_macd(prices)
        df['macd'] = macd
        df['macd_signal'] = signal
        df['macd_histogram'] = histogram
        self.features_calculated.extend(['macd', 'macd_signal', 'macd_histogram'])
        
        # 3. Bollinger Bands
        print("3️⃣  Calculando Bollinger Bands...")
        upper, middle, lower = self.calculate_bollinger_bands(prices)
        df['bb_upper'] = upper
        df['bb_middle'] = middle
        df['bb_lower'] = lower
        df['bb_width'] = (upper - lower) / middle * 100  # % ancho
        self.features_calculated.extend(['bb_upper', 'bb_middle', 'bb_lower', 'bb_width'])
        
        # 4. Moving Averages
        print("4️⃣  Calculando Moving Averages...")
        mas = self.calculate_moving_averages(prices)
        for name, values in mas.items():
            df[name] = values
            self.features_calculated.append(name)
        
        # 5. Price vs MA divergence
        print("5️⃣  Calculando divergencias...")
        df['price_vs_sma7'] = (prices - df['sma_7']) / df['sma_7'] * 100
        df['price_vs_sma21'] = (prices - df['sma_21']) / df['sma_21'] * 100
        df['ema_cross'] = (df['ema_7'] > df['ema_21']).astype(int)
        self.features_calculated.extend(['price_vs_sma7', 'price_vs_sma21', 'ema_cross'])
        
        # 6. Volatilidad
        print("6️⃣  Calculando volatilidad...")
        df['volatility_20'] = self.calculate_volatility(prices, 20)
        self.features_calculated.append('volatility_20')
        
        # 7. Time features
        print("7️⃣  Agregando features de tiempo...")
        df = self.add_time_features(df)
        self.features_calculated.extend(['hour', 'day_of_week', 'is_weekend'])
        
        # 8. Price momentum
        print("8️⃣  Calculando momentum...")
        df['price_change_1h'] = df['entry_price'].pct_change(2) * 100
        df['price_change_3h'] = df['entry_price'].pct_change(6) * 100
        df['price_change_6h'] = df['entry_price'].pct_change(12) * 100
        self.features_calculated.extend(['price_change_1h', 'price_change_3h', 'price_change_6h'])
        
        print(f"\n✅ Features calculadas: {len(self.features_calculated)}")
        print(f"   Features totales en dataset: {len(df.columns)}")
        
        return df
    
    def validate_features(self, df):
        """Valida calidad de las features"""
        
        print("\n🔍 VALIDANDO CALIDAD DE FEATURES")
        print("="*80)
        
        # Verificar NaN
        nan_counts = df[self.features_calculated].isna().sum()
        features_with_nan = nan_counts[nan_counts > 0]
        
        if len(features_with_nan) > 0:
            print(f"\n⚠️  Features con valores NaN:")
            for feat, count in features_with_nan.items():
                pct = (count / len(df)) * 100
                print(f"   {feat}: {count:,} ({pct:.2f}%)")
        else:
            print("\n✅ No hay valores NaN")
        
        # Verificar features constantes
        constant_features = []
        for feat in self.features_calculated:
            if df[feat].nunique() == 1:
                constant_features.append(feat)
        
        if constant_features:
            print(f"\n⚠️  Features constantes (eliminar): {constant_features}")
        else:
            print("\n✅ No hay features constantes")
        
        # Estadísticas básicas
        print(f"\n📊 Estadísticas de algunas features clave:")
        key_features = ['rsi_14', 'macd', 'bb_width', 'volatility_20', 'price_change_3h']
        stats = df[key_features].describe()
        print(stats.to_string())
        
        return df

def main():
    """Función principal"""
    
    print("\n" + "="*80)
    print("🚀 FASE 1: FEATURE ENGINEERING PARA MODELO 3H")
    print("="*80)
    
    # Cargar datos
    print("\n📥 Cargando datos históricos...")
    df = pd.read_csv('bitacora_new_models.csv')
    df['timestamp_pred'] = pd.to_datetime(df['timestamp_pred'])
    
    # Filtrar solo 3h
    df_3h = df[df['timeframe'] == '3h'].copy()
    print(f"   Total registros 3h: {len(df_3h):,}")
    
    # Crear ingeniero de features
    engineer = FeatureEngineer()
    
    # Calcular features
    df_enhanced = engineer.engineer_features(df_3h)
    
    # Validar features
    df_validated = engineer.validate_features(df_enhanced)
    
    # Guardar dataset con features
    output_file = 'dataset_3h_features.csv'
    df_validated.to_csv(output_file, index=False)
    
    print(f"\n💾 Dataset guardado: {output_file}")
    print(f"   Tamaño: {df_validated.shape}")
    print(f"   Features nuevas: {len(engineer.features_calculated)}")
    
    print("\n" + "="*80)
    print("✅ FASE 1 COMPLETADA")
    print("="*80)
    print("\n📋 Próximos pasos:")
    print("   1. Revisar calidad de features")
    print("   2. Iniciar Fase 2: Experimentación con modelos")
    print("   3. Entrenar múltiples configuraciones de XGBoost")
    
    return df_validated

if __name__ == '__main__':
    df = main()
