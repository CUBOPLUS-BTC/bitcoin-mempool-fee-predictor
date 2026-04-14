#!/usr/bin/env python3
"""
Feature Engineering para Modelo de Fees - Fase 1
Calcula todas las features de congestión de mempool necesarias para entrenamiento.
Reemplaza el cálculo de indicadores técnicos de precio (RSI, MACD, etc.)

Uso:
    python scripts/phase1_feature_engineering.py
    python scripts/phase1_feature_engineering.py --input data/snapshots/mempool_snapshots.parquet
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.features import FeatureEngineer
from src.ingestion import MempoolDataIngestion


def main():
    """Función principal"""
    import argparse

    parser = argparse.ArgumentParser(description="Fee Prediction Feature Engineering")
    parser.add_argument('--input', type=str, default=None, help='Input Parquet/CSV file')
    parser.add_argument('--config', type=str, default='config/config.yaml')
    parser.add_argument('--output', type=str, default=None, help='Output file path')

    args = parser.parse_args()

    print("\n" + "=" * 80)
    print("🚀 FASE 1: FEATURE ENGINEERING PARA PREDICCIÓN DE FEES")
    print("=" * 80)

    # Cargar datos
    print("\n📥 Cargando snapshots de mempool...")

    if args.input:
        if args.input.endswith('.parquet'):
            df = pd.read_parquet(args.input)
        else:
            df = pd.read_csv(args.input)
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
    else:
        # Try to load from collector daemon data
        ingestion = MempoolDataIngestion(config_path=args.config)

        # First try Parquet
        df = ingestion.load_snapshots()

        # If no Parquet, try individual JSONs
        if df is None:
            print("   No Parquet found, loading individual JSON snapshots...")
            df = ingestion.load_all_snapshots_from_json()

    if df is None or len(df) == 0:
        print("❌ Error: No hay datos disponibles")
        print("   Ejecuta primero el collector daemon:")
        print("   python scripts/collector_daemon.py --test-run")
        return 1

    print(f"   Total snapshots: {len(df):,}")
    if 'timestamp' in df.columns:
        print(f"   Rango: {df['timestamp'].min()} → {df['timestamp'].max()}")

    # Crear ingeniero de features
    engineer = FeatureEngineer(config_path=args.config)

    # Calcular features
    print("\n🔧 CALCULANDO FEATURES DE CONGESTIÓN")
    print("=" * 80)

    df_features = engineer.create_all_features(df)
    feature_cols = engineer.get_feature_columns(df_features)

    print(f"\n✅ Features calculadas: {len(feature_cols)}")

    # Crear targets
    print("\n🎯 CREANDO TARGETS DE FEE POR HORIZONTE DE BLOQUES")
    print("=" * 80)

    df_final = engineer.create_block_horizon_targets(df_features)

    # Validar features
    print("\n🔍 VALIDANDO CALIDAD DE FEATURES")
    print("=" * 80)

    # Check NaN
    nan_counts = df_final[feature_cols].isna().sum()
    features_with_nan = nan_counts[nan_counts > 0]

    if len(features_with_nan) > 0:
        print(f"\n⚠️  Features con NaN: {len(features_with_nan)}")
        for feat, count in features_with_nan.head(10).items():
            pct = (count / len(df_final)) * 100
            print(f"   {feat}: {count:,} ({pct:.2f}%)")
    else:
        print("\n✅ Sin valores NaN")

    # Check constant features
    constant = [col for col in feature_cols if df_final[col].nunique() <= 1]
    if constant:
        print(f"\n⚠️  Features constantes: {constant}")
    else:
        print("✅ Sin features constantes")

    # Key statistics
    print(f"\n📊 Estadísticas de features clave:")
    key_features = ['fee_fastest', 'fee_spread', 'mempool_vsize_mb',
                    'congestion_index', 'fee_pressure']
    available_keys = [f for f in key_features if f in df_final.columns]
    if available_keys:
        stats = df_final[available_keys].describe()
        print(stats.to_string())

    # Target statistics
    print(f"\n🎯 Estadísticas de targets:")
    target_cols = [col for col in df_final.columns if col.startswith('target_')]
    if target_cols:
        target_stats = df_final[target_cols].describe()
        print(target_stats.to_string())

    # Guardar dataset
    if args.output:
        output_file = args.output
    else:
        output_file = f"data/processed/features_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)

    if output_file.endswith('.parquet'):
        df_final.to_parquet(output_file, index=False)
    else:
        df_final.to_csv(output_file, index=False)

    print(f"\n💾 Dataset guardado: {output_file}")
    print(f"   Tamaño: {df_final.shape}")
    print(f"   Features: {len(feature_cols)}")
    print(f"   Targets: {len(target_cols)}")

    print("\n" + "=" * 80)
    print("✅ FASE 1 COMPLETADA")
    print("=" * 80)
    print("\n📋 Próximos pasos:")
    print("   1. Revisar calidad de features")
    print("   2. Entrenar modelos: python -m src.train --all")
    print("   3. Entrenar LightGBM: python -m src.train_lightgbm --all")
    print("   4. Iniciar predicciones live: python scripts/live_predict.py")

    return 0


if __name__ == '__main__':
    sys.exit(main())
