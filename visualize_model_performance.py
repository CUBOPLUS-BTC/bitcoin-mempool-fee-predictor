#!/usr/bin/env python3
"""
Visualización de performance de modelos de predicción de fees
Compara: Actual vs Ensemble vs XGBoost vs LightGBM
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import matplotlib.dates as mdates

# Configuración
MODELS_DIR = Path("models")
OUTPUT_FILE = "model_performance_comparison.png"

def load_ensemble_data():
    """Carga los datos de predicciones del ensemble"""
    data = {}
    for horizon in [1, 3, 6]:
        file_path = MODELS_DIR / f"ensemble_predictions_{horizon}block.csv"
        if file_path.exists():
            df = pd.read_csv(file_path)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['horizon'] = horizon
            data[horizon] = df
            print(f"✓ Cargado {horizon}-block: {len(df)} muestras")
        else:
            print(f"✗ No encontrado: {file_path}")
    return data

def calculate_metrics(df):
    """Calcula métricas de error para cada modelo"""
    metrics = {}
    
    # Actual fee
    actual = df['actual_fee'].values
    
    # Modelos
    models = {
        'Ensemble': df['ensemble_fee'].values,
        'XGBoost': df['xgb_fee'].values,
        'LightGBM': df['lgb_fee'].values
    }
    
    for name, pred in models.items():
        mae = np.mean(np.abs(pred - actual))
        mse = np.mean((pred - actual) ** 2)
        rmse = np.sqrt(mse)
        mape = np.mean(np.abs((actual - pred) / (actual + 1e-10))) * 100
        
        metrics[name] = {
            'MAE': mae,
            'RMSE': rmse,
            'MAPE': mape
        }
    
    return metrics

def create_comparison_plot(data):
    """Crea gráfica comparativa de los modelos"""
    fig, axes = plt.subplots(3, 2, figsize=(16, 14))
    fig.suptitle('Modelos de Predicción de Fees vs Precios Reales', fontsize=16, fontweight='bold')
    
    horizons = [1, 3, 6]
    horizon_names = ['1 Bloque (~10 min)', '3 Bloques (~30 min)', '6 Bloques (~60 min)']
    
    for idx, (horizon, name) in enumerate(zip(horizons, horizon_names)):
        if horizon not in data:
            continue
            
        df = data[horizon]
        
        # Gráfica izquierda: Predicciones vs Actual
        ax1 = axes[idx, 0]
        ax1.plot(df['timestamp'], df['actual_fee'], 'k-', label='Actual', linewidth=2, alpha=0.8)
        ax1.plot(df['timestamp'], df['ensemble_fee'], 'b-', label='Ensemble', linewidth=1.5, alpha=0.8)
        ax1.plot(df['timestamp'], df['xgb_fee'], 'g--', label='XGBoost', linewidth=1, alpha=0.7)
        ax1.plot(df['timestamp'], df['lgb_fee'], 'r:', label='LightGBM', linewidth=1, alpha=0.7)
        
        ax1.set_title(f'{name}', fontweight='bold')
        ax1.set_ylabel('Fee (sat/vB)')
        ax1.legend(loc='upper left', fontsize=8)
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # Gráfica derecha: Error absoluto
        ax2 = axes[idx, 1]
        
        ensemble_error = np.abs(df['ensemble_fee'] - df['actual_fee'])
        xgb_error = np.abs(df['xgb_fee'] - df['actual_fee'])
        lgb_error = np.abs(df['lgb_fee'] - df['actual_fee'])
        
        ax2.plot(df['timestamp'], ensemble_error, 'b-', label='Ensemble', linewidth=1.5, alpha=0.8)
        ax2.plot(df['timestamp'], xgb_error, 'g--', label='XGBoost', linewidth=1, alpha=0.7)
        ax2.plot(df['timestamp'], lgb_error, 'r:', label='LightGBM', linewidth=1, alpha=0.7)
        
        ax2.set_title(f'{name} - Error Absoluto', fontweight='bold')
        ax2.set_ylabel('|Error| (sat/vB)')
        ax2.legend(loc='upper left', fontsize=8)
        ax2.grid(True, alpha=0.3)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    plt.tight_layout()
    plt.savefig(OUTPUT_FILE, dpi=150, bbox_inches='tight')
    print(f"\n✓ Gráfica guardada: {OUTPUT_FILE}")
    return fig

def print_metrics_table(data):
    """Imprime tabla de métricas"""
    print("\n" + "="*80)
    print("MÉTRICAS DE PERFORMANCE POR MODELO")
    print("="*80)
    
    for horizon in [1, 3, 6]:
        if horizon not in data:
            continue
        
        df = data[horizon]
        metrics = calculate_metrics(df)
        
        print(f"\n{horizon} Bloque(s):")
        print("-" * 60)
        print(f"{'Modelo':<12} {'MAE':<12} {'RMSE':<12} {'MAPE (%)':<12}")
        print("-" * 60)
        
        for model_name, m in metrics.items():
            print(f"{model_name:<12} {m['MAE']:<12.4f} {m['RMSE']:<12.4f} {m['MAPE']:<12.2f}")

def main():
    print("Cargando datos de predicciones...")
    data = load_ensemble_data()
    
    if not data:
        print("No se encontraron datos de predicciones.")
        return
    
    print("\nGenerando gráfica comparativa...")
    create_comparison_plot(data)
    
    print_metrics_table(data)
    
    print("\n" + "="*80)
    print("VISUALIZACIÓN COMPLETADA")
    print("="*80)

if __name__ == "__main__":
    main()
