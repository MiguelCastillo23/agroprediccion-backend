import firebase_admin
from firebase_admin import credentials, firestore
from config import Config
from datetime import datetime

class FirebaseService:
    """Servicio para interactuar con Firebase Firestore"""
    
    def __init__(self):
        if not firebase_admin._apps:
            cred = credentials.Certificate(Config.FIREBASE_CONFIG)
            firebase_admin.initialize_app(cred)
        
        self.db = firestore.client()
    
    def save_demand_data(self, data):
        """
        Guarda datos de demanda en Firestore
        data: lista de diccionarios con {producto, anio, mes, demanda}
        """
        try:
            batch = self.db.batch()
            collection_ref = self.db.collection('demandas')
            
            for record in data:
                doc_ref = collection_ref.document()
                record['timestamp'] = datetime.now()
                batch.set(doc_ref, record)
            
            batch.commit()
            return {"success": True, "message": f"{len(data)} registros guardados"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_product_data(self, producto):
        """Obtiene todos los datos de un producto específico"""
        try:
            docs = self.db.collection('demandas')\
                .where('producto', '==', producto)\
                .stream()
            
            data = []
            for doc in docs:
                data.append(doc.to_dict())
            
            # Ordenar manualmente en Python
            data.sort(key=lambda x: (x.get('anio', 0), x.get('mes', 0)))
            
            return data
        except Exception as e:
            print(f"Error obteniendo datos: {str(e)}")
            return []
    
    def get_all_products(self):
        """Obtiene lista de todos los productos únicos"""
        try:
            docs = self.db.collection('demandas').stream()
            products = set()
            
            for doc in docs:
                data = doc.to_dict()
                if 'producto' in data:
                    products.add(data['producto'])
            
            return sorted(list(products))
        except Exception as e:
            print(f"Error obteniendo productos: {str(e)}")
            return []
    
    def delete_all_data(self):
        """Elimina todos los datos de demanda (útil para testing)"""
        try:
            docs = self.db.collection('demandas').stream()
            batch = self.db.batch()
            
            for doc in docs:
                batch.delete(doc.reference)
            
            batch.commit()
            return {"success": True, "message": "Datos eliminados"}
        except Exception as e:
            return {"success": False, "error": str(e)}