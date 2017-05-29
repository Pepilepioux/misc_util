#!/usr/bin/python
# -*- coding: UTF-8 -*-
"""
    vivant.
    Écoute sur un port TCP et répond simplement "OK"(ou autre texte passé en paramètre).
    But: pouvoir vérifier à distance que la machine est toujours vivante.
"""
import sys
import socket
import time
import argparse
import re

# -----------------------------------------------------------------------------------------------------------

parser = argparse.ArgumentParser(description='Programme qui répond simplement pour montrer qu\'il est vivant')

parser.add_argument('--reponse', '-r', action='store', help='Texte de la réponse. Défaut "OK"')
parser.add_argument('--port', '-p', action='store', type=int, help='Port sur lequel on écoute. Défaut 9000')
parser.add_argument('--tempo', '-t', action='store', type=float, help='tempo après réponse(pour éviter le DOS). Défaut 1 s')
parser.add_argument('--interface', '-i', action='store', help='interface(adresse) sur laquelle on écoute. Défaut toutes')


args = parser.parse_args()

if args.reponse is None:
    reponse = '\r\nOK\r\n'
else:
    reponse = '\r\n' + args.reponse + '\r\n'

if args.port is None:
    portEcoute = 9000
else:
    portEcoute = args.port

if args.tempo is None:
    tempo = 1.0
else:
    tempo = args.tempo

if args.interface is None:
    interface = ''
else:
    if re.match('^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', args.interface):
        interface = args.interface
    else:
        interface = ''


server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    server_socket.bind((interface, portEcoute))
except:
    server_socket.bind(('', portEcoute))

server_socket.listen(5)
continuer = True

while continuer:
    client_socket, address = server_socket.accept()
    server_socket.settimeout(0.0)
    server_socket.settimeout(None)
    data = 1

    while data:
        try:
            data = client_socket.recv(64)
        except:
            break

        if data == b'x':
            exit()

        try:
            # Ben oui, si l'émetteur coupe la connexion avant qu'on ne réponde, ça plante.
            client_socket.send(reponse.encode())
        except Exception as e:
            print('Ouh, j\'ai bien fait de mettre un try !')
            pass

        time.sleep(tempo)

    server_socket.settimeout(None)

client_socket.close()
