import sqlite3
import threading
from typing import Any, Dict, List, Optional, Tuple, Type, Union


# Global connection and thread-local storage
DATABASE_PATH = ":memory:"
_connections = threading.local()


def get_connection() -> sqlite3.Connection:
    """Get a thread-local database connection."""
    if not hasattr(_connections, "conn") or _connections.conn is None:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        _connections.conn = conn
    return _connections.conn


def close_connection():
    """Close the current thread's database connection."""
    if hasattr(_connections, "conn") and _connections.conn is not None:
        _connections.conn.close()
        _connections.conn = None


def set_database(path: str):
    """Set the database file path. Must be called before any model usage."""
    global DATABASE_PATH
    DATABASE_PATH = path
    # Reset connections
    close_connection()


class Field:
    """Base class for model fields."""
    def __init__(self, db_type: str, **kwargs):
        self.db_type = db_type
        self.name: str = ""
        self.null: bool = kwargs.get("null", False)
        self.default = kwargs.get("default", None)
        self.primary_key: bool = kwargs.get("primary_key", False)

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.name}>"

    def to_db(self, value: Any) -> Any:
        """Convert Python value to database-compatible value."""
        return value

    def from_db(self, value: Any) -> Any:
        """Convert database value to Python value."""
        return value


class IntegerField(Field):
    """Integer field."""
    def __init__(self, **kwargs):
        super().__init__("INTEGER", **kwargs)

    def to_db(self, value: Any) -> Any:
        return int(value) if value is not None else None


class TextField(Field):
    """Text field."""
    def __init__(self, **kwargs):
        super().__init__("TEXT", **kwargs)

    def to_db(self, value: Any) -> Any:
        return str(value) if value is not None else None


class ModelMeta(type):
    """Metaclass for Model that collects fields and creates table."""
    def __new__(mcs, name: str, bases: Tuple[Type, ...], attrs: Dict[str, Any]):
        # Skip base Model class
        if name == "Model":
            return super().__new__(mcs, name, bases, attrs)

        # Collect Field instances from class attributes
        fields: Dict[str, Field] = {}
        for key, value in attrs.items():
            if isinstance(value, Field):
                value.name = key
                fields[key] = value

        # Add a default 'id' primary key if not defined
        if "id" not in fields:
            id_field = IntegerField(primary_key=True)
            id_field.name = "id"
            fields["id"] = id_field

        cls = super().__new__(mcs, name, bases, attrs)
        cls._fields = fields
        cls._table_name = attrs.get("__tablename__", name.lower())

        # Auto-create table (if not exists)
        cls._create_table()
        return cls


class QuerySet:
    """Represents a database query for a model."""
    def __init__(self, model_cls: Type["Model"]):
        self.model_cls = model_cls
        self._filters: List[str] = []
        self._params: List[Any] = []
        self._order_by: Optional[str] = None
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None

    def filter(self, **kwargs) -> "QuerySet":
        """Add filter conditions. Supports lookups like field__gt, field__lt, etc."""
        for key, value in kwargs.items():
            parts = key.split("__", 1)
            field_name = parts[0]
            if field_name not in self.model_cls._fields:
                raise ValueError(f"Unknown field: {field_name}")
            if len(parts) == 1:
                self._filters.append(f"{field_name} = ?")
                self._params.append(self.model_cls._fields[field_name].to_db(value))
            else:
                lookup = parts[1]
                field = self.model_cls._fields[field_name]
                if lookup == "gt":
                    self._filters.append(f"{field_name} > ?")
                    self._params.append(field.to_db(value))
                elif lookup == "lt":
                    self._filters.append(f"{field_name} < ?")
                    self._params.append(field.to_db(value))
                elif lookup == "gte":
                    self._filters.append(f"{field_name} >= ?")
                    self._params.append(field.to_db(value))
                elif lookup == "lte":
                    self._filters.append(f"{field_name} <= ?")
                    self._params.append(field.to_db(value))
                elif lookup == "ne":
                    self._filters.append(f"{field_name} != ?")
                    self._params.append(field.to_db(value))
                elif lookup == "contains":
                    self._filters.append(f"{field_name} LIKE ?")
                    self._params.append(f"%{field.to_db(value)}%")
                elif lookup == "startswith":
                    self._filters.append(f"{field_name} LIKE ?")
                    self._params.append(f"{field.to_db(value)}%")
                elif lookup == "endswith":
                    self._filters.append(f"{field_name} LIKE ?")
                    self._params.append(f"%{field.to_db(value)}")
                else:
                    raise ValueError(f"Unsupported lookup: {lookup}")
        return self

    def order_by(self, field: str) -> "QuerySet":
        """Set ordering. Prefix '-' for descending."""
        self._order_by = field
        return self

    def limit(self, n: int) -> "QuerySet":
        """Limit number of results."""
        self._limit = n
        return self

    def offset(self, n: int) -> "QuerySet":
        """Offset for pagination."""
        self._offset = n
        return self

    def _build_query(self, base_query: str) -> Tuple[str, list]:
        query = base_query
        params = []
        if self._filters:
            query += " WHERE " + " AND ".join(self._filters)
            params.extend(self._params)
        if self._order_by:
            if self._order_by.startswith("-"):
                order = f"{self._order_by[1:]} DESC"
            else:
                order = f"{self._order_by} ASC"
            query += f" ORDER BY {order}"
        if self._limit is not None:
            query += f" LIMIT {self._limit}"
        if self._offset is not None:
            query += f" OFFSET {self._offset}"
        return query, params

    def all(self) -> List["Model"]:
        """Return all results."""
        table = self.model_cls._table_name
        query, params = self._build_query(f"SELECT * FROM {table}")
        conn = get_connection()
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        return [self.model_cls._from_row(row) for row in rows]

    def first(self) -> Optional["Model"]:
        """Return first result or None."""
        results = self.limit(1).all()
        if results:
            return results[0]
        return None

    def count(self) -> int:
        """Return count of matching rows."""
        table = self.model_cls._table_name
        query, params = self._build_query(f"SELECT COUNT(*) FROM {table}")
        conn = get_connection()
        cursor = conn.execute(query, params)
        return cursor.fetchone()[0]

    def delete(self):
        """Delete matching rows."""
        table = self.model_cls._table_name
        query, params = self._build_query(f"DELETE FROM {table}")
        conn = get_connection()
        conn.execute(query, params)
        conn.commit()

    def update(self, **kwargs) -> int:
        """Update matching rows with given field values."""
        table = self.model_cls._table_name
        set_clause = ", ".join([f"{k} = ?" for k in kwargs])
        params = [self.model_cls._fields[k].to_db(v) for k, v in kwargs.items()]
        query = f"UPDATE {table} SET {set_clause}"
        if self._filters:
            query += " WHERE " + " AND ".join(self._filters)
            params.extend(self._params)
        conn = get_connection()
        cursor = conn.execute(query, params)
        conn.commit()
        return cursor.rowcount

    def values_list(self, *fields, flat=False) -> List:
        """Return list of tuples/values for given fields."""
        table = self.model_cls._table_name
        field_names = fields
        query, params = self._build_query(f"SELECT {', '.join(field_names)} FROM {table}")
        conn = get_connection()
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        if flat and len(fields) == 1:
            return [row[0] for row in rows]
        return [tuple(row) for row in rows]


class Manager:
    """Descriptor that returns a QuerySet for the model class."""
    def __get__(self, instance, owner):
        if instance is not None:
            # Instance access (e.g., self.objects) should not be used.
            raise AttributeError("Manager is not accessible via instances")
        return QuerySet(owner)


class Model(metaclass=ModelMeta):
    """Base class for all models."""
    objects = Manager()

    def __init__(self, **kwargs):
        # Set field values
        for field_name, field in self._fields.items():
            if field_name in kwargs:
                setattr(self, field_name, field.to_db(kwargs[field_name]))
            else:
                if field.default is not None:
                    setattr(self, field_name, field.to_db(field.default))
                else:
                    setattr(self, field_name, None)

    @classmethod
    def _create_table(cls):
        """Create the table for this model if it does not exist."""
        columns = []
        for name, field in cls._fields.items():
            col_def = f"{name} {field.db_type}"
            if field.primary_key:
                col_def += " PRIMARY KEY AUTOINCREMENT"
            if not field.null and not field.primary_key:
                col_def += " NOT NULL"
            columns.append(col_def)
        sql = f"CREATE TABLE IF NOT EXISTS {cls._table_name} ({', '.join(columns)})"
        conn = get_connection()
        conn.execute(sql)
        conn.commit()

    @classmethod
    def _from_row(cls, row: sqlite3.Row) -> "Model":
        """Create a model instance from a sqlite3.Row."""
        instance = cls.__new__(cls)
        for key in row.keys():
            field = cls._fields.get(key)
            if field:
                setattr(instance, key, field.from_db(row[key]))
            else:
                setattr(instance, key, row[key])
        return instance

    def save(self):
        """Insert or update the instance."""
        fields = {}
        for name in self._fields:
            if name == "id" and self._fields[name].primary_key:
                continue
            fields[name] = getattr(self, name, None)

        if getattr(self, "id", None) is not None:
            # Update
            set_clause = ", ".join([f"{k} = ?" for k in fields])
            params = [self._fields[k].to_db(v) for k, v in fields.items()]
            query = f"UPDATE {self._table_name} SET {set_clause} WHERE id = ?"
            params.append(self.id)
            conn = get_connection()
            conn.execute(query, params)
            conn.commit()
        else:
            # Insert
            columns = ", ".join(fields.keys())
            placeholders = ", ".join(["?" for _ in fields])
            params = [self._fields[k].to_db(v) for k, v in fields.items()]
            query = f"INSERT INTO {self._table_name} ({columns}) VALUES ({placeholders})"
            conn = get_connection()
            cursor = conn.execute(query, params)
            conn.commit()
            setattr(self, "id", cursor.lastrowid)

    def delete(self):
        """Delete this instance from the database."""