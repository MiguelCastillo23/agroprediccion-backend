from flask import Blueprint, request, jsonify
from services.firebase_service import FirebaseService
from services.predictor import DemandPredictor
from config import Config
import pandas as pd
import io

api_bp = Blueprint('api', __name__)
firebase = FirebaseService()
predictor = DemandPredictor()

@api_bp.route('/health', methods=['GET'])
def health_check():
    """Endpoint para verificar que el servidor está corriendo"""
    return jsonify({
        "status": "ok",
        "message": "AgroPredicción API funcionando correctamente"
    })

@api_bp.route('/upload', methods=['POST'])
def upload_data():
    """
    Endpoint para subir datos de demanda desde Excel o TXT
    Espera archivo con columnas: PRODUCTO, ANIO, MES, DEMANDA
    """
    try:
        # Verificar que se envió un archivo
        if 'file' not in request.files:
            return jsonify({"error": "No se envió ningún archivo"}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({"error": "Nombre de archivo vacío"}), 400
        
        # Leer archivo según extensión
        filename = file.filename.lower()
        
        if filename.endswith('.xlsx') or filename.endswith('.xls'):
            df = pd.read_excel(io.BytesIO(file.read()))
        elif filename.endswith('.txt') or filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(file.read()))
        else:
            return jsonify({"error": "Formato de archivo no soportado. Use Excel o TXT"}), 400
        
        # Normalizar nombres de columnas
        df.columns = df.columns.str.strip().str.upper()
        
        # Verificar columnas requeridas
        required_cols = ['PRODUCTO', 'ANIO', 'MES', 'DEMANDA']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            # Intentar con nombres alternativos
            col_mapping = {
                'DEMANDA (TN)': 'DEMANDA',
                'DEMANDA(TN)': 'DEMANDA',
                'AÑO': 'ANIO',
                'ANO': 'ANIO'
            }
            df.rename(columns=col_mapping, inplace=True)
            
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                return jsonify({
                    "error": f"Faltan columnas requeridas: {', '.join(missing_cols)}"
                }), 400
        
        # Limpiar y validar datos
        df['PRODUCTO'] = df['PRODUCTO'].str.strip().str.upper()
        df['ANIO'] = pd.to_numeric(df['ANIO'], errors='coerce')
        df['MES'] = pd.to_numeric(df['MES'], errors='coerce')
        df['DEMANDA'] = pd.to_numeric(df['DEMANDA'], errors='coerce')
        
        # Eliminar filas con datos inválidos
        df = df.dropna(subset=['PRODUCTO', 'ANIO', 'MES', 'DEMANDA'])
        
        if len(df) == 0:
            return jsonify({"error": "No hay datos válidos en el archivo"}), 400
        
        # Convertir a lista de diccionarios
        data_to_save = []
        for _, row in df.iterrows():
            data_to_save.append({
                'producto': row['PRODUCTO'],
                'anio': int(row['ANIO']),
                'mes': int(row['MES']),
                'demanda': float(row['DEMANDA'])
            })
        
        # Guardar en Firebase
        result = firebase.save_demand_data(data_to_save)
        
        if result['success']:
            # Obtener estadísticas
            products = df['PRODUCTO'].unique().tolist()
            date_range = {
                'inicio': f"{int(df['ANIO'].min())}-{int(df['MES'].min()):02d}",
                'fin': f"{int(df['ANIO'].max())}-{int(df['MES'].max()):02d}"
            }
            
            return jsonify({
                "success": True,
                "message": result['message'],
                "stats": {
                    "total_registros": len(data_to_save),
                    "productos": products,
                    "num_productos": len(products),
                    "rango_fechas": date_range
                }
            })
        else:
            return jsonify({"error": result['error']}), 500
            
    except Exception as e:
        return jsonify({"error": f"Error procesando archivo: {str(e)}"}), 500

@api_bp.route('/products', methods=['GET'])
def get_products():
    """Obtiene lista de todos los productos disponibles"""
    try:
        products = firebase.get_all_products()
        return jsonify({
            "success": True,
            "products": products,
            "total": len(products)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/predict/<producto>', methods=['GET'])
def predict_product(producto):
    """
    Genera predicción para un producto específico
    Parámetros opcionales: ?periods=3
    """
    try:
        # Obtener número de períodos a predecir
        periods = request.args.get('periods', Config.FORECAST_PERIODS, type=int)
        
        # Validar períodos
        if periods < 1 or periods > 12:
            return jsonify({"error": "Los períodos deben estar entre 1 y 12"}), 400
        
        # Obtener datos históricos del producto
        producto_upper = producto.upper()
        historical_data = firebase.get_product_data(producto_upper)
        
        if not historical_data:
            return jsonify({
                "error": f"No se encontraron datos para el producto: {producto}"
            }), 404
        
        # Generar predicción
        result = predictor.train_and_predict(historical_data, periods)
        
        if result['success']:
            return jsonify({
                "success": True,
                "producto": producto_upper,
                "prediccion": result['predictions'],
                "historico": result['historical'],
                "confianza": result['confidence'],
                "total_meses_historicos": result['total_data_points']
            })
        else:
            return jsonify({"error": result['error']}), 400
            
    except Exception as e:
        return jsonify({"error": f"Error generando predicción: {str(e)}"}), 500

@api_bp.route('/predict-all', methods=['GET'])
def predict_all_products():
    """Genera predicciones para todos los productos"""
    try:
        periods = request.args.get('periods', Config.FORECAST_PERIODS, type=int)
        
        # Obtener todos los productos
        products = firebase.get_all_products()
        
        if not products:
            return jsonify({
                "error": "No hay productos disponibles. Sube datos primero."
            }), 404
        
        # Obtener datos y predecir para cada producto
        results = {}
        for product in products:
            historical_data = firebase.get_product_data(product)
            prediction = predictor.train_and_predict(historical_data, periods)
            results[product] = prediction
        
        return jsonify({
            "success": True,
            "predicciones": results,
            "total_productos": len(results)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/data/<producto>', methods=['GET'])
def get_product_data(producto):
    """Obtiene todos los datos históricos de un producto"""
    try:
        producto_upper = producto.upper()
        data = firebase.get_product_data(producto_upper)
        
        if not data:
            return jsonify({
                "error": f"No se encontraron datos para: {producto}"
            }), 404
        
        return jsonify({
            "success": True,
            "producto": producto_upper,
            "data": data,
            "total": len(data)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/clear-data', methods=['DELETE'])
def clear_all_data():
    """Elimina todos los datos (útil para testing)"""
    try:
        result = firebase.delete_all_data()
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({"error": result['error']}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500