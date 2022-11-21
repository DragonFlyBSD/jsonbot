# jsb/utils/statdict.py
#
#

""" dictionairy to keep stats. """

# jsb imports

from jsb.utils.lazydict import LazyDict

# classes


class StatDict(LazyDict):

    """dictionary to hold stats"""

    def set(self, item, value):
        """set item to value"""
        self[item] = value

    def upitem(self, item, value=1):
        """increase item"""
        if item not in self:
            self[item] = value
            return
        self[item] += value

    def downitem(self, item, value=1):
        """decrease item"""
        if item not in self:
            self[item] = value
            return
        self[item] -= value

    def top(self, start=1, limit=None):
        """return highest items"""
        result = []
        for item, value in self.items():
            if value >= start:
                result.append((item, value))
        result.sort(key=lambda a: a[1])
        if limit:
            result = result[:limit]
        return result

    def down(self, end=100, limit=None):
        """return lowest items"""
        result = []
        for item, value in self.items():
            if value <= end:
                result.append((item, value))
        result.sort(key=lambda a: a[1])
        if limit:
            return result[:limit]
        else:
            return result
