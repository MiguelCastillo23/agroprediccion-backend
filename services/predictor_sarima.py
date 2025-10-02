import pandas as pd
import numpy as np
from statsmodels.tsa.statespace.sarimax import SARIMAX
from sklearn.metrics import mean_absolute_error
import warnings
warnings.filterwarnings('ignore')

class DemandPredictor:
    """Motor de predicción de demanda usando SARIMA"""
    
    def __init__(self):
        self.model = None
    
    def prepare_data(self, data):
        """
        Prepara datos para SARIMA
        data: lista de dicts con {producto, anio, mes, demanda}
        retorna: DataFrame con índice temporal y demanda
        """
        if not data:
            return None
        
        # Convertir a DataFrame
        df = pd.DataFrame(data)
        
        # Crear columna de fecha
        df['fecha'] = pd.to_datetime(
            df['anio'].astype(str) + '-' + df['mes'].astype(str).str.zfill(2) + '-01'
        )
        
        # Establecer fecha como índice
        df = df.set_index('fecha')
        
        # Ordenar por fecha
        df = df.sort_index()
        
        # Crear serie temporal con demanda
        ts = df['demanda']
        
        return ts
    
    def train_and_predict(self, historical_data, periods=3):
        """
        Entrena modelo SARIMA y genera predicciones
        historical_data: lista de dicts con datos históricos
        periods: número de meses a predecir
        retorna: dict con predicciones y métricas
        """
        try:
            # Preparar datos
            ts = self.prepare_data(historical_data)
            
            if ts is None or len(ts) < 12:
                return {
                    "success": False,
                    "error": "Se requieren al menos 12 meses de datos históricos"
                }
            
            # Configurar modelo SARIMA
            # (p,d,q) x (P,D,Q,s)
            # p,d,q: parámetros no estacionales
            # P,D,Q: parámetros estacionales
            # s: período estacional (12 para mensual anual)
            
            # Parámetros optimizados para series agrícolas
            order = (1, 1, 1)  # ARIMA(1,1,1)
            seasonal_order = (1, 1, 1, 12)  # Estacionalidad anual
            
            # Entrenar modelo
            self.model = SARIMAX(
                ts,
                order=order,
                seasonal_order=seasonal_order,
                enforce_stationarity=False,
                enforce_invertibility=False
            )
            
            model_fit = self.model.fit(disp=False)
            
            # Generar predicciones
            forecast = model_fit.forecast(steps=periods)
            
            # Calcular intervalos de confianza
            forecast_conf = model_fit.get_forecast(steps=periods)
            conf_int = forecast_conf.conf_int()
            
            # Formatear resultados
            results = []
            forecast_dates = pd.date_range(
                start=ts.index[-1] + pd.DateOffset(months=1),
                periods=periods,
                freq='MS'
            )
            
            for i, date in enumerate(forecast_dates):
                results.append({
                    'fecha': date.strftime('%Y-%m'),
                    'anio': date.year,
                    'mes': date.month,
                    'prediccion': round(max(0, forecast.iloc[i]), 2),
                    'limite_inferior': round(max(0, conf_int.iloc[i, 0]), 2),
                    'limite_superior': round(max(0, conf_int.iloc[i, 1]), 2)
                })
            
            # Calcular métricas de confianza
            confidence = self._calculate_confidence(ts, model_fit)
            
            return {
                "success": True,
                "predictions": results,
                "historical": self._format_historical(ts),
                "confidence": confidence,
                "total_data_points": len(ts)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error en predicción: {str(e)}"
            }
    
    def _format_historical(self, ts):
        """Formatea datos históricos para respuesta"""
        historical = []
        for date, value in ts.items():
            historical.append({
                'fecha': date.strftime('%Y-%m'),
                'anio': date.year,
                'mes': date.month,
                'demanda': round(value, 2)
            })
        return historical
    
    def _calculate_confidence(self, ts, model_fit):
        """Calcula nivel de confianza basado en error del modelo"""
        try:
            # Hacer predicciones in-sample para calcular error
            predictions = model_fit.fittedvalues
            
            # Calcular MAE (Mean Absolute Error)
            mae = mean_absolute_error(ts[1:], predictions[1:])
            
            # Calcular error relativo
            mean_demand = ts.mean()
            relative_error = mae / mean_demand if mean_demand > 0 else 1
            
            # Convertir a score de confianza (0-100)
            confidence = max(0, min(100, 100 * (1 - relative_error)))
            
            return {
                "score": round(confidence, 2),
                "level": "Alta" if confidence > 70 else "Media" if confidence > 40 else "Baja",
                "mae": round(mae, 2)
            }
        except:
            return {
                "score": 50,
                "level": "Media",
                "mae": 0
            }
    
    def predict_multiple_products(self, products_data, periods=3):
        """
        Predice demanda para múltiples productos
        products_data: dict con {nombre_producto: [datos]}
        """
        results = {}
        
        for product, data in products_data.items():
            prediction = self.train_and_predict(data, periods)
            results[product] = prediction
        
        return results