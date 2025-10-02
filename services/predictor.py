import pandas as pd
from prophet import Prophet
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class DemandPredictor:
    """Motor de predicción de demanda usando Prophet"""
    
    def __init__(self):
        self.model = None
    
    def prepare_data(self, data):
        """
        Prepara datos para Prophet
        data: lista de dicts con {producto, anio, mes, demanda}
        retorna: DataFrame con columnas 'ds' (fecha) y 'y' (demanda)
        """
        if not data:
            return None
        
        # Convertir a DataFrame
        df = pd.DataFrame(data)
        
        # Crear columna de fecha
        df['ds'] = pd.to_datetime(
            df['anio'].astype(str) + '-' + df['mes'].astype(str).str.zfill(2) + '-01'
        )
        
        # Renombrar columna de demanda a 'y' (requerido por Prophet)
        df['y'] = df['demanda']
        
        # Ordenar por fecha
        df = df.sort_values('ds')
        
        # Seleccionar solo columnas necesarias
        df = df[['ds', 'y']]
        
        return df
    
    def train_and_predict(self, historical_data, periods=3):
        """
        Entrena modelo y genera predicciones
        historical_data: lista de dicts con datos históricos
        periods: número de meses a predecir
        retorna: dict con predicciones y métricas
        """
        try:
            # Preparar datos
            df = self.prepare_data(historical_data)
            
            if df is None or len(df) < 12:
                return {
                    "success": False,
                    "error": "Se requieren al menos 12 meses de datos históricos"
                }
            
            # Configurar y entrenar modelo Prophet
            self.model = Prophet(
                seasonality_mode='multiplicative',  # Mejor para datos agrícolas
                yearly_seasonality=True,
                weekly_seasonality=False,
                daily_seasonality=False,
                changepoint_prior_scale=0.05  # Sensibilidad a cambios
            )
            
            self.model.fit(df)
            
            # Crear dataframe para predicciones futuras
            future = self.model.make_future_dataframe(periods=periods, freq='MS')
            
            # Generar predicciones
            forecast = self.model.predict(future)
            
            # Extraer solo las predicciones futuras
            predictions = forecast.tail(periods)
            
            # Formatear resultados
            results = []
            for _, row in predictions.iterrows():
                results.append({
                    'fecha': row['ds'].strftime('%Y-%m'),
                    'anio': row['ds'].year,
                    'mes': row['ds'].month,
                    'prediccion': round(max(0, row['yhat']), 2),  # No permitir negativos
                    'limite_inferior': round(max(0, row['yhat_lower']), 2),
                    'limite_superior': round(max(0, row['yhat_upper']), 2)
                })
            
            # Calcular métricas de confianza
            confidence = self._calculate_confidence(df, forecast)
            
            return {
                "success": True,
                "predictions": results,
                "historical": self._format_historical(df),
                "confidence": confidence,
                "total_data_points": len(df)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error en predicción: {str(e)}"
            }
    
    def _format_historical(self, df):
        """Formatea datos históricos para respuesta"""
        historical = []
        for _, row in df.iterrows():
            historical.append({
                'fecha': row['ds'].strftime('%Y-%m'),
                'anio': row['ds'].year,
                'mes': row['ds'].month,
                'demanda': round(row['y'], 2)
            })
        return historical
    
    def _calculate_confidence(self, historical_df, forecast_df):
        """Calcula nivel de confianza basado en variabilidad de datos"""
        # Calcular variabilidad de datos históricos
        variability = historical_df['y'].std() / historical_df['y'].mean()
        
        # Nivel de confianza inverso a variabilidad (escala 0-100)
        confidence = max(0, min(100, 100 * (1 - variability)))
        
        return {
            "score": round(confidence, 2),
            "level": "Alta" if confidence > 70 else "Media" if confidence > 40 else "Baja"
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