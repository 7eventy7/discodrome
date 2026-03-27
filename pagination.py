import math


class ListPaginator:
    def __init__(self, items, items_per_page=10):
        self.pages = []
        self.items_per_page = items_per_page
        self.num_pages = math.ceil(len(items) / items_per_page)
        for i in range(self.num_pages):
            self.pages.append([])
        for i in range(len(items)):
            self.pages[math.floor(i / items_per_page)].append({
                'input_index': i,
                'data': items.pop(0),
            })
