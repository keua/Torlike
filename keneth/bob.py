""" server class """
from classes import server_class

bob = server_class.Server("127.0.0.1", 5010)
bob.start_connection()