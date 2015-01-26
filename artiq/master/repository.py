class Repository:
    def get_data(self, filename):
        with open(filename) as f:
            return f.read()
