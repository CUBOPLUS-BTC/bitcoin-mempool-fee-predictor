#!/usr/bin/env python3
"""
Automated Monitoring Dashboard for BTC Prediction Models
Generates daily/weekly reports and sends alerts
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class ModelMonitor:
    """Monitor de rendimiento de modelos"""
    
    def __init__(self, log_file='bitacora_new_models.csv'):
        self.log_file = log_file
        self.alerts = []
    
    def load_data(self, days=7):
        """Carga datos recientes"""
        df = pd.read_csv(self.log_file)
        df['timestamp_pred'] = pd.to_datetime(df['timestamp_pred'])
        
        # Filtrar últimos N días
        cutoff_date = datetime.now() - timedelta(days=days)
        df = df[df['timestamp_pred'] >= cutoff_date]
        
        return df
    
    def calculate_metrics(self, df):
        """Calcula métricas clave"""
        df_completed = df[df['status'] == 'COMPLETED'].copy()
        
        if len(df_completed) == 0:
            return None
        
        df_completed['error_pct'] = (df_completed['error_abs'] / df_completed['entry_price']) * 100
        
        metrics = {
            'total_predictions':len(df),
            'completed': len(df_completed),
            'pending': len(df[df['status'] == 'PENDING']),
            'avg_error_pct': df_completed['error_pct'].mean(),
            'max_error_pct': df_completed['error_pct'].max(),
            'outliers': len(df_completed[df_completed['error_pct'] > 5.0]),
            'timeframe_stats': {}
        }
        
        # Por timeframe
        for tf in ['30m', '1h', '3h', '6h', '12h']:
            df_tf = df_completed[df_completed['timeframe'] == tf]
            if len(df_tf) > 0:
                win_rate = (df_tf['error_pct'] < 2.0).sum() / len(df_tf) * 100
                metrics['timeframe_stats'][tf] = {
                    'count': len(df_tf),
                    'win_rate': win_rate,
                    'avg_error': df_tf['error_pct'].mean()
                }
        
        return metrics
    
    def check_alerts(self, metrics):
        """Verifica condiciones de alerta"""
        if metrics is None:
            return
        
        # Alert 1: Win rate bajo en 3h
        if '3h' in metrics['timeframe_stats']:
            win_rate_3h = metrics['timeframe_stats']['3h']['win_rate']
            if win_rate_3h < 70:
                self.alerts.append({
                    'severity': 'WARNING',
                    'message': f"Win rate 3h muy bajo: {win_rate_3h:.1f}%",
                    'recommendation': 'Revisar modelo 3h urgentemente'
                })
        
        # Alert 2: Demasiados outliers
        outlier_rate = (metrics['outliers'] / metrics['completed']) * 100
        if outlier_rate > 1.0:
            self.alerts.append({
                'severity': 'WARNING',
                'message': f"Tasa alta de outliers: {outlier_rate:.2f}%",
                'recommendation': 'Verificar filtro de volatilidad'
            })
        
        # Alert 3: Error promedio alto
        if metrics['avg_error_pct'] > 2.0:
            self.alerts.append({
                'severity': 'INFO',
                'message': f"Error promedio elevado: {metrics['avg_error_pct']:.2f}%",
                'recommendation': 'Considerar reentrenamiento'
            })
    
    def generate_daily_report(self):
        """Genera reporte diario"""
        print("\n" + "="*80)
        print("📊 REPORTE DIARIO DE MONITOREO")
        print("="*80)
        print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Cargar datos de últimas 24 horas
        df = self.load_data(days=1)
        
        if df.empty:
            print("\n⚠️  No hay datos para reportar")
            return
        
        metrics = self.calculate_metrics(df)
        
        if metrics:
            print(f"\n📈 Métricas (últimas 24 horas):")
            print(f"   Total predicciones: {metrics['total_predictions']}")
            print(f"   Completadas: {metrics['completed']}")
            print(f"   Pendientes: {metrics['pending']}")
            print(f"   Error promedio: {metrics['avg_error_pct']:.2f}%")
            print(f"   Outliers: {metrics['outliers']}")
            
            print(f"\n🎯 Win Rate por Timeframe:")
            for tf, stats in metrics['timeframe_stats'].items():
                status = "✅" if stats['win_rate'] > 90 else "⚠️" if stats['win_rate'] > 70 else "🔴"
                print(f"   {status} {tf}: {stats['win_rate']:.1f}% ({stats['count']} ops)")
        
        # Verificar alertas
        self.check_alerts(metrics)
        
        if self.alerts:
            print(f"\n⚠️  ALERTAS ({len(self.alerts)}):")
            for alert in self.alerts:
                print(f"   [{alert['severity']}] {alert['message']}")
                print(f"       → {alert['recommendation']}")
        else:
            print(f"\n✅ No hay alertas")
        
        print("\n" + "="*80)
        
        return metrics
    
    def generate_weekly_report(self):
        """Genera reporte semanal"""
        print("\n" + "="*80)
        print("📊 REPORTE SEMANAL DE RENDIMIENTO")
        print("="*80)
        print(f"Semana del: {(datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')}")
        print(f"al: {datetime.now().strftime('%Y-%m-%d')}")
        
        df = self.load_data(days=7)
        
        if df.empty:
            print("\n⚠️  No hay datos para reportar")
            return
        
        metrics = self.calculate_metrics(df)
        
        if metrics:
            print(f"\n📈 Métricas Semanales:")
            print(f"   Total predicciones: {metrics['total_predictions']}")
            print(f"   Completadas: {metrics['completed']}")
            print(f"   Error promedio: {metrics['avg_error_pct']:.2f}%")
            print(f"   Outliers: {metrics['outliers']} ({metrics['outliers']/metrics['completed']*100:.2f}%)")
            
            print(f"\n🎯 Rendimiento por Timeframe (7 días):")
            best_tf = None
            best_wr = 0
            
            for tf, stats in metrics['timeframe_stats'].items():
                if stats['win_rate'] > best_wr:
                    best_wr = stats['win_rate']
                    best_tf = tf
                
                status = "⭐" if stats['win_rate'] > 95 else "✅" if stats['win_rate'] > 85 else "⚠️"
                print(f"   {status} {tf}:")
                print(f"       Win Rate: {stats['win_rate']:.2f}%")
                print(f"       Predicciones: {stats['count']}")
                print(f"       Error promedio: {stats['avg_error']:.2f}%")
            
            if best_tf:
                print(f"\n🏆 Mejor timeframe: {best_tf} ({best_wr:.2f}% win rate)")
            
            # Tendencia
            print(f"\n📈 Tendencia:")
            df_week1 = self.load_data(days=3)  # Primeros 3 días
            df_week2 = self.load_data(days=7)
            df_week2 = df_week2[df_week2['timestamp_pred'] < (datetime.now() - timedelta(days=3))]
            
            if len(df_week1) > 0 and len(df_week2) > 0:
                m1 = self.calculate_metrics(df_week1)
                m2 = self.calculate_metrics(df_week2)
                
                if m1 and m2:
                    trend = m1['avg_error_pct'] - m2['avg_error_pct']
                    if trend < 0:
                        print(f"   ✅ Mejorando ({trend:.2f}% menos error)")
                    else:
                        print(f"   ⚠️  Deteriorando (+{trend:.2f}% más error)")
        
        print("\n" + "="*80)
        
        return metrics
    
    def save_metrics_log(self, metrics, log_type='daily'):
        """Guarda métricas en log JSON"""
        if metrics is None:
            return
        
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'log_type': log_type,
            'metrics': metrics,
            'alerts': self.alerts
        }
        
        log_filename = 'monitoring_log.jsonl'
        with open(log_filename, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
        
        print(f"💾 Métricas guardadas en: {log_filename}")

def main():
    """Función principal"""
    monitor = ModelMonitor()
    
    # Generar reporte diario
    daily_metrics = monitor.generate_daily_report()
    
    # Guardar métricas
    if daily_metrics:
        monitor.save_metrics_log(daily_metrics, 'daily')
    
    # Si es lunes, generar reporte semanal también
    if datetime.now().weekday() == 0:  # 0 = Monday
        print("\n" + "🗓️  ES LUNES - GENERANDO REPORTE SEMANAL\n")
        weekly_metrics = monitor.generate_weekly_report()
        if weekly_metrics:
            monitor.save_metrics_log(weekly_metrics, 'weekly')

if __name__ == '__main__':
    main()
