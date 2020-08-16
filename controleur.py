#!/usr/bin/env python
# -*- coding: UTF-8 -*-

"""
    Petit utilitaire interactif pour envoyer manuellement des commandes à un programme qui utilise
    le Recepteur de gipkoutils.
"""

import socket
import argparse

parser = argparse.ArgumentParser(description='Test d\'émission message tcp')

parser.add_argument('--destination', '-d', action='store', help='Nom ou adresse IP de la machine à laquelle on veut envoyer le message')
parser.add_argument('--port', '-p', action='store', type=int, help='Port sur lequel on veut communiquer')


args = parser.parse_args()

print(args)
print(args.destination, '\n')
print(args.port, '\n')

if args.destination is None:
    destination = input('Hôte auquel envoyer les messages ? ')
else:
    destination = args.destination

if args.port is None:
    port = '?'

    while (type(port).__name__ != 'int'):
        try:
            port = int(input('port ? '))
        except:
            print('Le port doit être un entier !')
else:
    port = args.port


try:
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
except:
    print('Erreur socket.socket')
    exit()

try:
    client_socket.connect((destination, port))
except:
    print('Erreur socket.connect')
    exit()

while 1:
    # data = raw_input("SEND(TYPE q or Q to Quit):") Si python 2
    data = input("Envoyer... (q ou Q pour terminer, ? pour la liste des commandes, ??? pour plus) :\n")
    if (data == '???'):
        print('Syntaxe :')
        print('<nom du programme destinataire> <commande> <valeur du paramètre>')

        print('Commandes :')
        print('\'stop\' : pas besoin d\'explication. Pas d\'autre paramètre')
        print('\'logging\' : le niveau de log.')
        print(' CRITICAL  50 ERROR   40 WARNING  30 ')
        print(' INFO   20 DEBUG   10 NOTSET   0 ')
        print('\'tempo1\' : la valeur de la tempo1. Dépend de l\'application. Il existe aussi tempo2 et tempo3.')
        print(' Le 3° paramètre dépend de l\'application. Pour les tempos c\'est la valeur en secondes')

        print('')

    else:
        if data.lower() == 'q':
            print('On ferme !')
            client_socket.close()
            break

        else:
            if data != '':
                client_socket.send(data.encode())
                client_socket.settimeout(5)

                try:
                    reponse = client_socket.recv(4096)
                    print('\nRéponse reçue :\n')
                    print(reponse.decode())
                    print('\n')

                except:
                    pass
