"""
Database operations - Generic CRUD functions for all collections
"""
from typing import List, Dict, Optional, Any
from bson import ObjectId
from app.config.database import db_config
from datetime import datetime

class DBOperations:
    """Generic database operations for MongoDB collections"""
    
    @staticmethod
    async def get_all(collection_name: str, filter_query: Dict = None, skip: int = 0, limit: int = 100) -> List[Dict]:
        """Get all documents from a collection with optional filtering"""
        collection = db_config.get_collection(collection_name)
        filter_query = filter_query or {}
        cursor = collection.find(filter_query).skip(skip).limit(limit)
        documents = await cursor.to_list(length=limit)
        return documents
    
    @staticmethod
    async def get_by_id(collection_name: str, doc_id: str) -> Optional[Dict]:
        """Get a single document by ID"""
        collection = db_config.get_collection(collection_name)
        try:
            document = await collection.find_one({"_id": ObjectId(doc_id)})
            return document
        except Exception:
            return None
    
    @staticmethod
    async def get_one(collection_name: str, filter_query: Dict) -> Optional[Dict]:
        """Get a single document by filter query"""
        collection = db_config.get_collection(collection_name)
        document = await collection.find_one(filter_query)
        return document
    
    @staticmethod
    async def create(collection_name: str, document: Dict) -> Dict:
        """Create a new document"""
        collection = db_config.get_collection(collection_name)
        document["created_at"] = datetime.utcnow()
        document["updated_at"] = datetime.utcnow()
        result = await collection.insert_one(document)
        document["_id"] = result.inserted_id
        return document
    
    @staticmethod
    async def update(collection_name: str, doc_id: str, update_data: Dict) -> Optional[Dict]:
        """Update a document by ID"""
        collection = db_config.get_collection(collection_name)
        update_data["updated_at"] = datetime.utcnow()
        try:
            result = await collection.find_one_and_update(
                {"_id": ObjectId(doc_id)},
                {"$set": update_data},
                return_document=True
            )
            return result
        except Exception:
            return None
    
    @staticmethod
    async def delete(collection_name: str, doc_id: str) -> bool:
        """Delete a document by ID"""
        collection = db_config.get_collection(collection_name)
        try:
            result = await collection.delete_one({"_id": ObjectId(doc_id)})
            return result.deleted_count > 0
        except Exception:
            return False
    
    @staticmethod
    async def count(collection_name: str, filter_query: Dict = None) -> int:
        """Count documents in a collection"""
        collection = db_config.get_collection(collection_name)
        filter_query = filter_query or {}
        count = await collection.count_documents(filter_query)
        return count
    
    @staticmethod
    async def aggregate(collection_name: str, pipeline: List[Dict]) -> List[Dict]:
        """Execute aggregation pipeline"""
        collection = db_config.get_collection(collection_name)
        cursor = collection.aggregate(pipeline)
        results = await cursor.to_list(length=None)
        return results

db_ops = DBOperations()
