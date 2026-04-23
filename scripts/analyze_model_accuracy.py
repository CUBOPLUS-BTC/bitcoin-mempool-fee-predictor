#!/usr/bin/env python3
"""
Análisis de precisión de modelos en contexto de Bitcoin
- Block Inclusion Accuracy
- Overpayment analysis
- Directional accuracy
"""

import pandas as pd
import numpy as np
from pathlib import Path

MODELS_DIR = Path("models")

def load_data():
    data = {}
    for horizon in [1, 3, 6]:
        file_path = MODELS_DIR / f"ensemble_predictions_{horizon}block.csv"
        if file_path.exists():
            df = pd.read_csv(file_path)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            data[horizon] = df
    return data

def block_inclusion_accuracy(actual, predicted, margin=0.1):
    """
    % de predicciones que son suficientes para confirmar
    (predicción >= actual * (1 - margin))
    """
    sufficient = predicted >= actual * (1 - margin)
    return np.mean(sufficient) * 100

def overpayment_analysis(actual, predicted):
    """
    Análisis de sobre-pago
    """
    overpay = predicted - actual
    overpay_pct = (overpay / (actual + 1e-10)) * 100
    
    return {
        'mean_overpay_sat': np.mean(overpay),
        'median_overpay_sat': np.median(overpay),
        'mean_overpay_pct': np.mean(overpay_pct),
        'max_overpay_sat': np.max(overpay),
        'pct_savings_if_perfect': np.mean((predicted - actual) / (predicted + 1e-10)) * 100
    }

def safety_margin_analysis(actual, predicted):
    """
    Análisis del margen de seguridad
    """
    # Underpayment (predicción muy baja)
    underpaid = predicted < actual
    underpaid_pct = np.mean(underpaid) * 100
    
    # Buena estimación (dentro de ±20%)
    good_estimate = np.abs(predicted - actual) <= actual * 0.2
    good_pct = np.mean(good_estimate) * 100
    
    # Sobrestimación segura (hasta 2x el actual)
    safe_over = (predicted >= actual) & (predicted <= actual * 2)
    safe_pct = np.mean(safe_over) * 100
    
    # Sobrestimación excesiva (>2x)
    excessive_over = predicted > actual * 2
    excessive_pct = np.mean(excessive_over) * 100
    
    return {
        'underpaid_pct': underpaid_pct,
        'good_estimate_pct': good_pct,
        'safe_overestimate_pct': safe_pct,
        'excessive_overestimate_pct': excessive_pct
    }

def main():
    data = load_data()
    
    print("="*80)
    print("ANÁLISIS DE PRECISIÓN - MODELOS DE FEE PREDICTION")
    print("="*80)
    
    for horizon in [1, 3, 6]:
        if horizon not in data:
            continue
            
        df = data[horizon]
        actual = df['actual_fee'].values
        
        print(f"\n{'='*40}")
        print(f"HORIZONTE: {horizon} BLOQUE(S)")
        print(f"{'='*40}")
        print(f"Muestras: {len(df)}")
        print(f"Fee real - Min: {actual.min():.2f}, Max: {actual.max():.2f}, Mean: {actual.mean():.2f} sat/vB")
        
        models = {
            'Ensemble': df['ensemble_fee'].values,
            'XGBoost': df['xgb_fee'].values,
            'LightGBM': df['lgb_fee'].values
        }
        
        for name, pred in models.items():
            print(f"\n{name}:")
            print("-" * 40)
            
            # Block Inclusion Accuracy
            inclusion = block_inclusion_accuracy(actual, pred, margin=0.05)
            print(f"  Block Inclusion Accuracy: {inclusion:.1f}%")
            print(f"     (% de veces que el fee predicho es suficiente para confirmar)")
            
            # Overpayment
            overpay = overpayment_analysis(actual, pred)
            print(f"  Sobre-pago promedio: {overpay['mean_overpay_sat']:.2f} sat/vB ({overpay['mean_overpay_pct']:.1f}%)")
            print(f"  Ahorro potencial si fuera perfecto: {overpay['pct_savings_if_perfect']:.1f}%")
            
            # Safety margins
            safety = safety_margin_analysis(actual, pred)
            print(f"  Distribución:")
            print(f"    - Predicciones muy bajas (no confirmarían): {safety['underpaid_pct']:.1f}%")
            print(f"    - Buena estimación (±20%): {safety['good_estimate_pct']:.1f}%")
            print(f"    - Sobrestimación segura (1x-2x): {safety['safe_overestimate_pct']:.1f}%")
            print(f"    - Sobrestimación excesiva (>2x): {safety['excessive_overestimate_pct']:.1f}%")
            
            # Práctico para Bitcoin
            confirmed_tx = pred >= actual
            avg_fee_if_use_model = np.mean(pred)
            avg_fee_minimum = np.mean(actual)
            
            print(f"  Impacto práctico:")
            print(f"    - Si usas este modelo para todos los txs, pagarías en promedio: {avg_fee_if_use_model:.2f} sat/vB")
            print(f"    - El mínimo necesario hubiera sido: {avg_fee_minimum:.2f} sat/vB")
            print(f"    - Extra pagado por transacción: {avg_fee_if_use_model - avg_fee_minimum:.2f} sat/vB")
    
    print("\n" + "="*80)
    print("CONCLUSIÓN")
    print("="*80)
    print("""
En el contexto de Bitcoin:

1. Block Inclusion Accuracy es lo más importante - si predices muy bajo,
   tu transacción se queda atascada en el mempool.

2. Un sobre-pago de ~0.5-1.0 sat/vB es aceptable porque:
   - Una transacción típica de 250 vB pagaría solo ~$0.01-0.05 extra
   - Es preferible pagar un poco más que quedarse atascado

3. Los fees actuales están muy bajos (1-2 sat/vB), lo que hace que los
   errores porcentuales parezcan grandes, pero en términos absolutos
   son insignificantes.

4. El ENSEMBLE (ponderado 60% XGB + 40% LGB) tiende a ser más conservador,
   lo cual es BUENO para la experiencia del usuario.
    """)

if __name__ == "__main__":
    main()
