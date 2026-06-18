# name: 数据结构集合
# keywords: 栈, 队列, 链表, 二叉树, 堆, stack, queue, linked list, tree, heap


class Stack:
    """栈（LIFO）"""

    def __init__(self):
        self._items = []

    def push(self, item):
        """入栈"""
        self._items.append(item)

    def pop(self):
        """出栈"""
        if self.is_empty():
            raise IndexError('pop from empty stack')
        return self._items.pop()

    def peek(self):
        """查看栈顶"""
        if self.is_empty():
            raise IndexError('peek from empty stack')
        return self._items[-1]

    def is_empty(self):
        """是否为空"""
        return len(self._items) == 0

    def __len__(self):
        return len(self._items)


class Queue:
    """队列（FIFO）"""

    def __init__(self):
        self._items = []

    def enqueue(self, item):
        """入队"""
        self._items.append(item)

    def dequeue(self):
        """出队"""
        if self.is_empty():
            raise IndexError('dequeue from empty queue')
        return self._items.pop(0)

    def front(self):
        """查看队首"""
        if self.is_empty():
            raise IndexError('front from empty queue')
        return self._items[0]

    def is_empty(self):
        """是否为空"""
        return len(self._items) == 0

    def __len__(self):
        return len(self._items)


class ListNode:
    """链表节点"""

    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next


class LinkedList:
    """单链表"""

    def __init__(self):
        self.head = None

    def append(self, val):
        """追加节点"""
        if not self.head:
            self.head = ListNode(val)
        else:
            curr = self.head
            while curr.next:
                curr = curr.next
            curr.next = ListNode(val)

    def find(self, val):
        """查找节点"""
        curr = self.head
        while curr:
            if curr.val == val:
                return curr
            curr = curr.next
        return None

    def delete(self, val):
        """删除节点"""
        if not self.head:
            return
        if self.head.val == val:
            self.head = self.head.next
            return
        curr = self.head
        while curr.next:
            if curr.next.val == val:
                curr.next = curr.next.next
                return
            curr = curr.next

    def to_list(self):
        """转为列表"""
        result = []
        curr = self.head
        while curr:
            result.append(curr.val)
            curr = curr.next
        return result


class TreeNode:
    """二叉树节点"""

    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right


class BinaryTree:
    """二叉树"""

    def __init__(self):
        self.root = None

    def insert(self, val):
        """插入节点（BST）"""
        if not self.root:
            self.root = TreeNode(val)
        else:
            self._insert_recursive(self.root, val)

    def _insert_recursive(self, node, val):
        if val < node.val:
            if node.left is None:
                node.left = TreeNode(val)
            else:
                self._insert_recursive(node.left, val)
        else:
            if node.right is None:
                node.right = TreeNode(val)
            else:
                self._insert_recursive(node.right, val)

    def inorder(self):
        """中序遍历"""
        result = []
        self._inorder_recursive(self.root, result)
        return result

    def _inorder_recursive(self, node, result):
        if node:
            self._inorder_recursive(node.left, result)
            result.append(node.val)
            self._inorder_recursive(node.right, result)


class MinHeap:
    """最小堆"""

    def __init__(self):
        self._items = []

    def push(self, item):
        """入堆"""
        self._items.append(item)
        self._sift_up(len(self._items) - 1)

    def pop(self):
        """出堆"""
        if not self._items:
            raise IndexError('pop from empty heap')
        self._items[0], self._items[-1] = self._items[-1], self._items[0]
        item = self._items.pop()
        if self._items:
            self._sift_down(0)
        return item

    def peek(self):
        """查看堆顶"""
        if not self._items:
            raise IndexError('peek from empty heap')
        return self._items[0]

    def _sift_up(self, idx):
        while idx > 0:
            parent = (idx - 1) // 2
            if self._items[idx] < self._items[parent]:
                self._items[idx], self._items[parent] = self._items[parent], self._items[idx]
                idx = parent
            else:
                break

    def _sift_down(self, idx):
        n = len(self._items)
        while True:
            smallest = idx
            left = 2 * idx + 1
            right = 2 * idx + 2
            if left < n and self._items[left] < self._items[smallest]:
                smallest = left
            if right < n and self._items[right] < self._items[smallest]:
                smallest = right
            if smallest != idx:
                self._items[idx], self._items[smallest] = self._items[smallest], self._items[idx]
                idx = smallest
            else:
                break

    def __len__(self):
        return len(self._items)
