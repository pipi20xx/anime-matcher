from . import anitopy

class AnitopyWrapper:
    @staticmethod
    def parse(filename: str) -> dict:
        return anitopy.parse(filename)

