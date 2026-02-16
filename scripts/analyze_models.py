#!/usr/bin/env python3
"""
Análisis completo del rendimiento de los modelos de predicción BTC
"""

import pandas as pd
import numpy as np
from datetime import datetime

def load_data():
    """Carga y prepara los datos"""
    df = pd.read_csv('bitacora_new_models.csv')
    df['timestamp_pred'] = pd.to_datetime(df['timestamp_pred'])
    df['target_time'] = pd.to_datetime(df['target_time'])
    return df

def calculate_win_rate(df, error_threshold_pct=2.0):
    """
    Calcula win rate por timeframe
    Un 'win' es cuando el error es menor al threshold especificado
    """
    df_completed = df[df['status'] == 'COMPLETED'].copy()
    
    # Calcular error relativo (%)
    df_completed['error_pct'] = (df_completed['error_abs'] / df_completed['entry_price']) * 100
    
    # Determinar si es un 'win'
    df_completed['is_win'] = df_completed['error_pct'] < error_threshold_pct
    
    results = []
    
    for tf in ['30m', '1h', '3h', '6h', '12h']:
        df_tf = df_completed[df_completed['timeframe'] == tf]
        
        if len(df_tf) > 0:
            win_rate = (df_tf['is_win'].sum() / len(df_tf)) * 100
            avg_error = df_tf['error_abs'].mean()
            avg_error_pct = df_tf['error_pct'].mean()
            max_error = df_tf['error_abs'].max()
            min_error = df_tf['error_abs'].min()
            
            results.append({
                'timeframe': tf,
                'total_predictions': len(df_tf),
                'wins': df_tf['is_win'].sum(),
                'losses': (~df_tf['is_win']).sum(),
                'win_rate': win_rate,
                'avg_error_usd': avg_error,
                'avg_error_pct': avg_error_pct,
                'max_error': max_error,
                'min_error': min_error
            })
    
    return pd.DataFrame(results)

def find_outliers(df, threshold_pct=5.0):
    """Identifica predicciones con errores extremos"""
    df_completed = df[df['status'] == 'COMPLETED'].copy()
    df_completed['error_pct'] = (df_completed['error_abs'] / df_completed['entry_price']) * 100
    
    outliers = df_completed[df_completed['error_pct'] > threshold_pct].copy()
    outliers = outliers.sort_values('error_pct', ascending=False)
    
    return outliers

def analyze_market_context(df):
    """Analiza el contexto del mercado durante las predicciones"""
    df_completed = df[df['status'] == 'COMPLETED'].copy()
    
    # Calcular volatilidad (cambio porcentual desde entrada hasta resultado)
    df_completed['price_change_pct'] = ((df_completed['actual_price'] - df_completed['entry_price']) / 
                                         df_completed['entry_price']) * 100
    
    # Calcular error porcentual
    df_completed['error_pct'] = (df_completed['error_abs'] / df_completed['entry_price']) * 100
    
    # Clasificar por volatilidad
    df_completed['volatility_category'] = pd.cut(
        df_completed['price_change_pct'].abs(),
        bins=[0, 1, 3, 5, 100],
        labels=['Baja (<1%)', 'Media (1-3%)', 'Alta (3-5%)', 'Extrema (>5%)']
    )
    
    # Analizar precisión por volatilidad
    volatility_analysis = df_completed.groupby('volatility_category').agg({
        'error_pct': ['mean', 'count'],
        'error_abs': 'mean'
    }).round(2)
    
    return df_completed, volatility_analysis

def generate_report(df):
    """Genera reporte completo de análisis"""
    
    print("="*80)
    print("📊 ANÁLISIS COMPLETO DE RENDIMIENTO - MODELOS BTC")
    print("="*80)
    print(f"\nFecha de análisis: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Estadísticas generales
    total_predictions = len(df)
    completed = len(df[df['status'] == 'COMPLETED'])
    pending = len(df[df['status'] == 'PENDING'])
    
    print(f"\n📈 ESTADÍSTICAS GENERALES")
    print("-"*80)
    print(f"Total de predicciones: {total_predictions:,}")
    print(f"Completadas: {completed:,} ({completed/total_predictions*100:.2f}%)")
    print(f"Pendientes: {pending:,} ({pending/total_predictions*100:.2f}%)")
    
    # Win Rate por timeframe
    print(f"\n🎯 WIN RATE POR TIMEFRAME (Criterio: error < 2%)")
    print("-"*80)
    win_rate_df = calculate_win_rate(df, error_threshold_pct=2.0)
    print(win_rate_df.to_string(index=False))
    
    # Análisis de contexto de mercado
    print(f"\n📊 PRECISIÓN POR VOLATILIDAD DEL MERCADO")
    print("-"*80)
    df_context, volatility_analysis = analyze_market_context(df)
    print(volatility_analysis)
    
    # Outliers
    print(f"\n⚠️  TOP 10 ERRORES EXTREMOS (>5%)")
    print("-"*80)
    outliers = find_outliers(df, threshold_pct=5.0)
    
    if len(outliers) > 0:
        top_outliers = outliers.head(10)[['timestamp_pred', 'timeframe', 'entry_price', 
                                           'actual_price', 'error_abs', 'error_pct']]
        top_outliers['error_pct'] = top_outliers['error_pct'].round(2)
        print(top_outliers.to_string(index=False))
        
        print(f"\nTotal de outliers (>5%): {len(outliers):,} predicciones")
        print(f"Porcentaje de outliers: {len(outliers)/completed*100:.2f}%")
    else:
        print("No se encontraron outliers con error > 5%")
    
    # Recomendaciones
    print(f"\n💡 RECOMENDACIONES")
    print("-"*80)
    
    # Analizar qué timeframe tiene mejor win rate
    best_timeframe = win_rate_df.loc[win_rate_df['win_rate'].idxmax()]
    worst_timeframe = win_rate_df.loc[win_rate_df['win_rate'].idxmin()]
    
    print(f"1. MEJOR TIMEFRAME: {best_timeframe['timeframe']} ({best_timeframe['win_rate']:.2f}% win rate)")
    print(f"   - Considerar priorizar este horizonte para trading")
    print(f"   - Error promedio: ${best_timeframe['avg_error_usd']:.2f} ({best_timeframe['avg_error_pct']:.2f}%)")
    
    print(f"\n2. TIMEFRAME A MEJORAR: {worst_timeframe['timeframe']} ({worst_timeframe['win_rate']:.2f}% win rate)")
    print(f"   - Requiere optimización del modelo")
    print(f"   - Error promedio: ${worst_timeframe['avg_error_usd']:.2f} ({worst_timeframe['avg_error_pct']:.2f}%)")
    
    print(f"\n3. VOLATILIDAD:")
    print(f"   - Evitar trading en condiciones de volatilidad extrema")
    print(f"   - Los modelos funcionan mejor en volatilidad baja a media")
    
    print(f"\n4. OUTLIERS:")
    if len(outliers) > 0:
        outlier_timeframes = outliers['timeframe'].value_counts()
        print(f"   - Timeframe más afectado por outliers: {outlier_timeframes.index[0]}")
        print(f"   - Implementar filtros para detección de anomalías")
    
    print("\n" + "="*80)
    
    return {
        'win_rate': win_rate_df,
        'outliers': outliers,
        'volatility_analysis': volatility_analysis
    }

if __name__ == '__main__':
    print("Cargando datos...")
    df = load_data()
    
    print(f"Datos cargados: {len(df):,} registros")
    
    results = generate_report(df)
    
    # Guardar resultados
    results['win_rate'].to_csv('win_rate_analysis.csv', index=False)
    results['outliers'].to_csv('outliers_analysis.csv', index=False)
    
    print("\n✅ Análisis completado. Archivos generados:")
    print("   - win_rate_analysis.csv")
    print("   - outliers_analysis.csv")
