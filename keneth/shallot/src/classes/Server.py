""" to use sockets"""
import socket
from random import *
from _thread import start_new_thread
from MessageFactory import MessageFactory, Object, MessageBase
from EllipticCurve import EllipticCurve, EllipticCurvePoint, EllipticCurveNeutralEl
from FiniteField import FiniteField
from Crypto.Cipher import AES


class Server:
    """ server class """

    def __init__(self, host, port):
        """ This is where the new socket instance is created.
            Parameters
            ----------
            host : string
                The host where the server will be bound.
            port : int
                The por where the server will be bound.
            Returns
            -------
            new Server Object
        """
        self.host = host
        self.port = port
        self.incoming_conn = None
        self.incoming_addr = None
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.bind((self.host, self.port))
        except socket.error as ex_message:
            print(str(ex_message))
        self.socket.listen(5)
        print("starting connection at: %s:%s" % (self.host, self.port))

        # Security object
        self.elliptic_curve = ''
        self.elliptic_point = ''
        self.A = ''
        self.B = ''
        self.C = ''

    def start_connection(self):
        """ starting connection """
        while True:
            self.incoming_conn, self.incoming_addr = self.socket.accept()
            print(
                'Connected to: %s:%i' % (
                    self.incoming_addr[0], self.incoming_addr[1])
            )
            start_new_thread(self.listen_for_messages, ())

    def listen_for_messages(self):
        """ reading message until no data"""
        while True:
            data = self.incoming_conn.recv(1024)
            if not data:
                break
            print(
                "I'm: %s:%i I've received a message from %s:%i" %
                (
                    self.host,
                    self.port,
                    self.incoming_addr[0],
                    self.incoming_addr[1]
                )
            )
            # Here we have to get the message and based on the type do something
            version, message_type, length = MessageBase.get_type_version_length(
                data[0:8].decode()
            )
            print(
                "The message version is: %s, type: %s, length: %s" %
                (version, message_type, length)
            )
            if message_type == 0:  # KEY_INIT
                self.send_key(data)
            elif message_type == 2:  # MESSAGE_RELAY
                self.respond(data)
            else:  # Build an error message
                self.send_error(data)

        self.close_connection()

    def close_connection(self):
        """ closing connection """
        self.incoming_conn.close()

    def decrypt(self, message):
        """ Use the own key and apply the AES decypher algorithm """
        c = self.C
        key = ''
        len_x = 8 if len(c.x.coeffs) > 8 else len(c.x.coeffs)
        len_y = 8 if len(c.y.coeffs) > 8 else len(c.y.coeffs)
        for i in range(len_x):
            key += str(c.x.coeffs[i])
        for i in range(len_y):
            key += str(c.y.coeffs[i])

        encoded_key = (MessageBase.add_padding(key, 16)).encode()  # The AES algorithm only manipulates bytes
        cipher = AES.new(encoded_key)

        #message = message.decode()
        decrypted_message = cipher.decrypt(message)
        for i in range(len(decrypted_message)):
            if decrypted_message[i:i+1] == b'|':
                next_message = decrypted_message[i+1:]
                break

        return next_message

    def send_key(self, message):
        """ reply with the key  """
        # generate the key
        message_shell = MessageFactory.get_empty_message('KEY_INIT')
        key_init_message = message_shell.decode(message)
        print('Key_init message')
        print(
            'type: %i, version: %i, key_id: %s, g:%s, p:%s, A:%s' %
            (
                key_init_message.type, key_init_message.version,
                key_init_message.key_id, key_init_message.g,
                key_init_message.p, key_init_message.A
            )
        )
        # Here we have to build a new message to reply to the client
        message_object = Object()
        message_object.version = 1
        message_object.key_id = key_init_message.key_id

        # We know want to calculate B
        # Let's workout the ellipticCurve and the elliptic point
        elliptic_curve_coeffs = key_init_message.p.split(':')
        a = FiniteField(FiniteField.get_coeffs_from_int(int(elliptic_curve_coeffs[0])))
        b = FiniteField(FiniteField.get_coeffs_from_int(int(elliptic_curve_coeffs[1])))

        elliptic_point_coeffs = key_init_message.g.split(':')
        x = FiniteField(FiniteField.get_coeffs_from_int(int(elliptic_point_coeffs[0])))
        y = FiniteField(FiniteField.get_coeffs_from_int(int(elliptic_point_coeffs[1])))
        self.elliptic_curve = EllipticCurve(a, x, y)
        self.elliptic_curve.b = b
        self.elliptic_point = EllipticCurvePoint(x, y, self.elliptic_curve)

        A_coeffs = key_init_message.A.split(':')
        A_x = FiniteField(FiniteField.get_coeffs_from_int(int(A_coeffs[0])))
        A_y = FiniteField(FiniteField.get_coeffs_from_int(int(A_coeffs[1])))
        self.A = EllipticCurvePoint(A_x, A_y, self.elliptic_curve)

        n = randint(1000, 5000)
        self.B = n * self.elliptic_point

        # let's calculate the key use to cipher
        self.C = n * self.A

        print(self.C)
        message_object.B = self.B.get_byte_string_from_coeffs()
        message = MessageFactory.get_message('KEY_REPLY', message_object)
        self.incoming_conn.send(message.encode())

    def send_error(self, message):
        """ reply with an error if the message is malformed """
        message_object = Object()
        message_object.version = 1
        message_object.error_code = 1
        message = MessageFactory.get_message('ERROR', message_object)
        self.incoming_conn.send(message.encode())

    def respond(self, message):
        """ decrypt the message and respond to the client """
        decrypted_message = self.decrypt(message[8:])
        print('I received this message')
        print(decrypted_message.decode())
        payload = ''
        response_message = "I've received the message"
        self.incoming_conn.send(response_message.encode())
