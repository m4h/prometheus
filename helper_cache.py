'''
simple key:value caching mechanism used for flask exporters
'''

class CacheItem(object):
    from time import time
    def __init__(self, name, value, timeout):
        self.name = name
        self.value = value
        self.timeout = timeout
        self.create_time = int(self.time())

    def is_expired(self):
        now = int(self.time())
        if (now - self.create_time) > self.timeout:
            return True
        return False

class CachePool(object):
    from time import time
    def __init__(self, timeout):
        self.timeout = timeout
        self.items = []

    def set(self, name, value, timeout=None):
        '''
        return - True if new item was set, False if item is exists and not expired
        '''
        if not timeout:
            timeout = self.timeout
        for item in self.items:
            if item.name == name:
                if item.is_expired(): # item is expired - re-add item
                    self.items.remove(item)
                    item = CacheItem(name, value, timeout)
                    self.items.append(item)
                    return True
                else: # item is not expired - can't add new item
                    return False
        item = CacheItem(name, value, timeout) # item does not exists in cache - add new item
        self.items.append(item)
        return True

    def get(self, name):
        '''
        return - item value or None if item wasn't found
        '''
        for item in self.items:
            if item.name == name:
                if item.is_expired():
                    self.items.remove(item)
                    return None
                else:
                    return item.value
        return None
