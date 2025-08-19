""""
全局变量类
"""
class GlobalState(object):
    """
    全局变量类
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
       self.file_parts = 0
       self.total_parts = 0

    def done_read(self):
       """
       count down 1
       """
       self.file_parts -= 1

    def get_left_count(self):
       """
       get all part count
       """
       return self.file_parts
    
    def set_total_parts(self, file_parts):
        """
        init value
        """
        self.file_parts = file_parts
        self.total_parts = file_parts

    def is_1st_part(self):
        """
        whether is first part
        """
        if self.file_parts == self.total_parts:
            return True
        else:
            return False
        