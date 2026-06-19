"""LRU Cache implementation."""
from collections import OrderedDict
from typing import Any, Optional


class LRUCache:
    """A simple LRU (Least Recently Used) cache.

    Attributes:
        capacity: Maximum number of items the cache can hold.
        cache: Internal OrderedDict storing the items.
    """

    def __init__(self, capacity: int) -> None:
        """Initialize the LRU cache with a given capacity.

        Args:
            capacity: Maximum number of items to store.

        Raises:
            ValueError: If capacity is not a positive integer.
        """
        if not isinstance(capacity, int) or capacity <= 0:
            raise ValueError("Capacity must be a positive integer.")
        self.capacity: int = capacity
        self.cache: OrderedDict = OrderedDict()

    def get(self, key: Any) -> Optional[Any]:
        """Retrieve the value for a key, marking it as recently used.

        Args:
            key: The key to look up.

        Returns:
            The value associated with the key, or None if not found.
        """
        if key not in self.cache:
            return None
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key: Any, value: Any) -> None:
        """Insert or update a key-value pair in the cache.

        If the key already exists, the value is updated and the key
        becomes the most recently used. If the cache is at capacity,
        the least recently used item is evicted.

        Args:
            key: The cache key.
            value: The cache value.
        """
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

    def __contains__(self, key: Any) -> bool:
        """Check if a key is in the cache without affecting usage order.

        Args:
            key: The key to check.

        Returns:
            True if the key is present, False otherwise.
        """
        return key in self.cache

    def __len__(self) -> int:
        """Return the number of items currently in the cache."""
        return len(self.cache)

    def clear(self) -> None:
        """Remove all items from the cache."""
        self.cache.clear()