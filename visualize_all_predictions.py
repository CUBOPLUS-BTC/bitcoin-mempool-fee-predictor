#!/usr/bin/env python3
"""
Visualización completa de predicciones de fees
Incluye datos de entrenamiento (ensemble_predictions_*block.csv) 
y datos de producción (predictions/ensemble_predictions.csv)
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import matplotlib.dates as mdates

MODELS_DIR = Path("models")
PREDICTIONS_DIR = Path("predictions")
OUTPUT_FILE = "all_predictions_analysis.png"

def load_training_data():
    """Carga datos de entrenamiento (test set)"""
    data = {}
    for horizon in [1, 3, 6]:
        file_path = MODELS_DIR / f"ensemble_predictions_{horizon}block.csv"
        if file_path.exists():
            df = pd.read_csv(file_path)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['horizon'] = horizon
            df['source'] = 'training'
            data[horizon] = df
            print(f"✓ Training {horizon}-block: {len(df)} muestras")
    return data

def load_production_data():
    """Carga datos de producción (predicciones en vivo)"""
    file_path = PREDICTIONS_DIR / "ensemble_predictions.csv"
    if not file_path.exists():
        return {}
    
    df = pd.read_csv(file_path)
    df['timestamp'] = pd.to_datetime(df['timestamp_pred'], format='mixed', utc=True)
    
    # Usar las nuevas columnas si existen, sino las viejas
    if 'ensemble_fee_sat_vb' in df.columns:
        df['ensemble_fee'] = df['ensemble_fee_exact'].fillna(df['predicted_fee_exact'])
        df['xgb_fee'] = df['xgb_fee_exact'].fillna(df.get('xgb_pred', np.nan))
        df['lgb_fee'] = df['lgb_fee_exact'].fillna(df.get('lgb_pred', np.nan))
    else:
        df['ensemble_fee'] = df['predicted_fee_exact']
        df['xgb_fee'] = df.get('xgb_pred', np.nan)
        df['lgb_fee'] = df.get('lgb_pred', np.nan)
    
    df['actual_fee'] = df['actual_fee']
    df['source'] = 'production'
    
    # Separar por horizonte
    data = {}
    for horizon in [1, 3, 6]:
        hdf = df[df['horizon_blocks'] == horizon].copy()
        if len(hdf) > 0:
            hdf['horizon'] = horizon
            data[horizon] = hdf
            print(f"✓ Production {horizon}-block: {len(hdf)} muestras")
    return data

def calculate_metrics(actual, predicted):
    """Calcula métricas de error"""
    mask = ~np.isnan(predicted)
    actual_clean = actual[mask]
    pred_clean = predicted[mask]
    
    if len(actual_clean) == 0:
        return {'MAE': np.nan, 'RMSE': np.nan, 'MAPE': np.nan, 'count': 0}
    
    mae = np.mean(np.abs(pred_clean - actual_clean))
    rmse = np.sqrt(np.mean((pred_clean - actual_clean) ** 2))
    mape = np.mean(np.abs((actual_clean - pred_clean) / (actual_clean + 1e-10))) * 100
    
    return {'MAE': mae, 'RMSE': rmse, 'MAPE': mape, 'count': len(actual_clean)}

def create_comprehensive_plot(train_data, prod_data):
    """Crea gráfica comparativa completa"""
    fig = plt.figure(figsize=(18, 16))
    gs = fig.add_gridspec(4, 3, hspace=0.3, wspace=0.25)
    
    horizons = [1, 3, 6]
    horizon_names = ['1 Bloque (~10 min)', '3 Bloques (~30 min)', '6 Bloques (~60 min)']
    colors = {'training': '#3498db', 'production': '#e74c3c'}
    
    # Fila 1-2: Series temporales por horizonte
    for idx, (h, name) in enumerate(zip(horizons, horizon_names)):
        ax = fig.add_subplot(gs[idx//2, idx%2 if idx < 2 else 2])
        
        # Datos de entrenamiento
        if h in train_data:
            df = train_data[h]
            ax.scatter(df['timestamp'], df['actual_fee'], c='black', s=30, alpha=0.7, label='Actual', zorder=5)
            ax.plot(df['timestamp'], df['ensemble_fee'], '--', color=colors['training'], linewidth=2, label='Ensemble (Train)', alpha=0.8)
        
        # Datos de producción
        if h in prod_data:
            df = prod_data[h]
            ax.scatter(df['timestamp'], df['actual_fee'], c='black', s=20, alpha=0.5, marker='x', zorder=5)
            ax.plot(df['timestamp'], df['ensemble_fee'], '-', color=colors['production'], linewidth=1.5, label='Ensemble (Prod)', alpha=0.8)
        
        ax.set_title(f'{name}', fontweight='bold', fontsize=12)
        ax.set_ylabel('Fee (sat/vB)')
        ax.legend(loc='upper left', fontsize=8)
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha='right', fontsize=8)
    
    # Fila 3: Métricas comparativas
    ax_metrics = fig.add_subplot(gs[2, :])
    
    metrics_data = []
    for h in horizons:
        for source, data in [('Training', train_data), ('Production', prod_data)]:
            if h in data:
                df = data[h]
                actual = df['actual_fee'].values
                ensemble = df['ensemble_fee'].values
                m = calculate_metrics(actual, ensemble)
                metrics_data.append({
                    'Horizon': f'{h}blk',
                    'Source': source,
                    'MAE': m['MAE'],
                    'RMSE': m['RMSE'],
                    'Samples': m['count']
                })
    
    if metrics_data:
        metrics_df = pd.DataFrame(metrics_data)
        
        x = np.arange(len(metrics_df))
        width = 0.35
        
        bars1 = ax_metrics.bar(x - width/2, metrics_df['MAE'], width, label='MAE', color='#3498db', alpha=0.8)
        bars2 = ax_metrics.bar(x + width/2, metrics_df['RMSE'], width, label='RMSE', color='#e74c3c', alpha=0.8)
        
        ax_metrics.set_ylabel('Error (sat/vB)', fontweight='bold')
        ax_metrics.set_title('Comparación de Métricas: Entrenamiento vs Producción', fontweight='bold', fontsize=12)
        ax_metrics.set_xticks(x)
        ax_metrics.set_xticklabels([f"{r['Horizon']}\n({r['Source']})" for _, r in metrics_df.iterrows()], fontsize=9)
        ax_metrics.legend()
        ax_metrics.grid(True, alpha=0.3, axis='y')
        
        # Añadir valores sobre barras
        for bar in bars1:
            height = bar.get_height()
            if not np.isnan(height):
                ax_metrics.annotate(f'{height:.2f}',
                                    xy=(bar.get_x() + bar.get_width() / 2, height),
                                    xytext=(0, 3), textcoords="offset points",
                                    ha='center', va='bottom', fontsize=8)
    
    # Fila 4: Resumen estadístico
    ax_text = fig.add_subplot(gs[3, :])
    ax_text.axis('off')
    
    summary_text = "RESUMEN DE PREDICCIONES\n" + "="*80 + "\n\n"
    
    for h in horizons:
        summary_text += f"Horizonte {h} Bloque(s):\n"
        summary_text += "-" * 60 + "\n"
        
        for source, data in [('Entrenamiento', train_data), ('Producción', prod_data)]:
            if h in data:
                df = data[h]
                actual = df['actual_fee'].values
                ensemble = df['ensemble_fee'].values
                m = calculate_metrics(actual, ensemble)
                
                # Block inclusion accuracy
                sufficient = ensemble >= actual * 0.95
                inclusion = np.mean(sufficient) * 100
                
                summary_text += f"  {source:12s}: {m['count']:3d} muestras | "
                summary_text += f"MAE: {m['MAE']:.3f} | "
                summary_text += f"Inclusión: {inclusion:.0f}%\n"
        
        summary_text += "\n"
    
    summary_text += "\nNOTA: Los fees actuales están muy bajos (~0.14-2.3 sat/vB), haciendo que MAPE sea alto.\n"
    summary_text += "El ensemble usa pesos: XGBoost 60% + LightGBM 40%\n"
    summary_text += "Block Inclusion = % de predicciones suficientes para confirmar en el bloque objetivo"
    
    ax_text.text(0.05, 0.95, summary_text, transform=ax_text.transAxes,
                 fontsize=10, verticalalignment='top', fontfamily='monospace',
                 bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    fig.suptitle('Análisis Completo de Predicciones de Fees - Bitcoin Mempool', 
                 fontsize=16, fontweight='bold', y=0.995)
    
    plt.savefig(OUTPUT_FILE, dpi=150, bbox_inches='tight')
    print(f"\n✓ Gráfica guardada: {OUTPUT_FILE}")
    return fig

def main():
    print("="*80)
    print("VISUALIZACIÓN COMPLETA DE PREDICCIONES")
    print("="*80)
    
    print("\nCargando datos de entrenamiento...")
    train_data = load_training_data()
    
    print("\nCargando datos de producción...")
    prod_data = load_production_data()
    
    if not train_data and not prod_data:
        print("No se encontraron datos de predicciones.")
        return
    
    print("\nGenerando gráfica...")
    create_comprehensive_plot(train_data, prod_data)
    
    print("\n" + "="*80)
    print("VISUALIZACIÓN COMPLETADA")
    print("="*80)

if __name__ == "__main__":
    main()
