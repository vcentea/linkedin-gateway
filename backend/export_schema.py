"""
Export database schema to SQL file
"""
import sys
from sqlalchemy import create_engine, MetaData
from sqlalchemy.schema import CreateTable, CreateIndex
from app.core.config import settings
from app.db.base import Base

def export_schema():
    """Export the database schema to a SQL file"""
    
    # Create engine
    engine = create_engine(settings.DB_URI)
    
    # Get metadata
    metadata = Base.metadata
    
    # Open output file
    with open('schema.sql', 'w', encoding='utf-8') as f:
        # Write header
        f.write("-- LinkedIn Gateway Database Schema\n")
        f.write("-- Generated automatically from SQLAlchemy models\n\n")
        
        # Write CREATE TABLE statements
        for table in metadata.sorted_tables:
            f.write(f"\n-- Table: {table.name}\n")
            create_table = CreateTable(table).compile(engine)
            f.write(f"{create_table};\n")
            
            # Write indexes
            for index in table.indexes:
                create_index = CreateIndex(index).compile(engine)
                f.write(f"{create_index};\n")
    
    print("✅ Schema exported to schema.sql")

if __name__ == "__main__":
    export_schema()

