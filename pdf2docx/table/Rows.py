# -*- coding: utf-8 -*-

'''A group of Row objects in a table.
'''

from .Row import Row
from ..common.Collection import ElementCollection


class Rows(ElementCollection):
    '''A group of Rows.'''

    def restore(self, raws:list):
        """Restore Rows from source dicts.

        Args:
            raws (list): A list of source dicts representing each row.

        Returns:
            Rows: self
        """        
        for raw in raws:
            row = Row(raw)
            self.append(row)
        return self
