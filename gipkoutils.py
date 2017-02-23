#!/usr/bin/python
# -*- coding: UTF-8 -*-

from datetime import datetime, timedelta
import time

import sys
import socket
import ast
import logging
import logging.handlers
import re
import shlex
import threading
import inspect
import traceback

donneesrecueslock = None
fini = False
tempo1 = None
tempo2 = None
tempo3 = None


# -----------------------------------------------------------------------------------------------------------
class Recepteur:
    """
        Se met à l'écoute en tcp sur le port passé en paramètre et exécute un traitement en fonction
        des instructions reçues.

        Il y a des traitements de base intégrés, comme l'ordre d'arrêt ou le renvoi d'informations.

        Le message reçu est une liste (en fait une chaine de caractères découpée sur les espaces,
        en tenant compte des guillemets, pour la transformer en liste) d'arguments.

        Le premier argument est le nom du programme. C'est une sorte de confirmation.
        Si c'est "?" on renvoie la doc.

        Le deuxième argument :
            "stop", on positionne l'indicateur "fini" testé par les autres classes.

            "info", on renvoie les informations sur le programme en cours

            "logging", on définit le niveau de log

        Toutes les autres valeurs sont passées au programme de traitement

        Version 5 :
            Dans la version 4 si le programme principal s'arrête alors que le récepteur a été
            lancé dans un thread le thread du récepteur ne s'arrêtera que s'il en reçoit l'ordre.
            Pour un programme conçu pour tourner en boucle c'est bien, pour pouvoir arrêter sur demande
            un programme qui dure longtemps c'est pas terrible.
            On introduit donc la fonction "apoptose" qu'il suffit d'appeler en fin de programme principal,
            fonction qui s'auto-envoie un ordre d'arrêt.
            La gestion des tempos sur les sockets est vraiment trop compliquée pour ce qu'on veut faire ici

    """

    # -----------------------------------------------------------------------------------------------------------
    def trt(msgRecu):
        return ''

    # -----------------------------------------------------------------------------------------------------------
    def __init__(self, portEcoute, *, traitement=trt):
        logger = logging.getLogger()
        self.portEcoute = portEcoute
        self.donneesrecues = []
        self.moi = sys.argv[0]
        self.traitement = traitement
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(("", portEcoute))
        logger.info('%s Moi : %s en écoute sur le port %s' % (__name__, self.moi, portEcoute))

        self.doc = 'Syntaxe :\n<nom du programme destinataire> <commande> [ <valeurs des paramètres> ]\n'
        self.doc += 'Pour connaitre le nom du programme qui répond, envoyer "t\'es qui, toi ?"\n(AVEC les guillemets !)\n\n'
        self.doc += 'Commandes :\n'
        self.doc += 'info : pour obtenir des informations sur les divers paramètres du programme\n\n'
        self.doc += 'stop : pas besoin d\'explication. Pas d\'autre paramètre\n\n'
        self.doc += 'logging : le niveau du logger.\n'
        self.doc += '    CRITICAL 	50	ERROR 		40	WARNING 	30\n'
        self.doc += '    INFO 		20	DEBUG 		10	NOTSET 		0\n\n'
        self.doc += 'loghandler	: le niveau des loghandlers.\n'
        self.doc += '    lancer d\'abord la commande "info" pour avoir la liste des handlers et\n'
        self.doc += '    leurs caractéristiques.\n'
        self.doc += '    Cette commande prend deux paramètres, le premier est le numéro de handler,\n'
        self.doc += '    le deuxième est sa nouvelle valeur.\n\n'
        self.doc += 'tempo1 : la valeur de la tempo de la boucle principale.\n'
        self.doc += '    Le 3° paramètre est la valeur en secondes\n\n'
        self.doc += 'tempo2, tempo3 : tempos dépendant de l\'appli.\n'

        return

    # -----------------------------------------------------------------------------------------------------------
    def __trtStandard__(self, msgRecu):
        """
            Les messages standard sont des listes dont le premier élément est le nom du programme
            (self.moi), le deuxième une instruction et le 3° une valeur.
            Si c'est une liste à moins de 2 éléments on laisse tomber.
            Et si le 1° élément de la liste n'est pas "moi", on laisse tomber aussi.
        """
        global donneesrecueslock
        global fini
        global tempo1
        global tempo2
        global tempo3

        logger = logging.getLogger()
        reponse = ''
        logger.debug('__trtStandard__, msgRecu = %s', msgRecu)

        # Le gars paumé qui sait pas ce qu'il faut faire...
        if len(msgRecu) >= 1 and msgRecu[0] == '?':
            return self.doc

        if len(msgRecu) >= 1 and msgRecu[0].lower() == "t'es qui, toi ?":
            reponse = self.moi
            return reponse

        if len(msgRecu) < 2 or msgRecu[0] != self.moi:
            return reponse

        # Maintenant on a un message qui a la bonne structure.
        if msgRecu[1].lower() == 'stop':
            # C'est un ordre d'arrêt
            logger.debug('%s Reçu un ordre d\'arrêt', __name__)

            logger.debug('Ligne %s, demande lock', inspect.getframeinfo(inspect.currentframe())[1])
            try:
                donneesrecueslock.acquire()
                #   self.lock.acquire()
                logger.debug('Ligne %s, lock obtenu', inspect.getframeinfo(inspect.currentframe())[1])
            except:
                logger.warning('Attention, pas de verrou disponible. Il est souhaitable d\'utiliser "donneesrecueslock" pour éviter les problèmes')

            fini = True
            logger.debug('Ligne %s, ordre relâche lock', inspect.getframeinfo(inspect.currentframe())[1])
            try:
                donneesrecueslock.release()
                #   self.lock.release()
                logger.debug('Ligne %s, lock relâché', inspect.getframeinfo(inspect.currentframe())[1])
            except:
                pass
            logger.debug('%s fini = %s' % (__name__, fini))

            reponse = 'stop'
            return reponse

        if msgRecu[1] == '?':
            reponse = self.doc + self.traitement(msgRecu)
            return reponse

        if msgRecu[1] == 'info':
            if tempo1 is not None:
                reponse = 'Tempo 1 : %s' % tempo1
            else:
                reponse = ''

            if tempo2 is not None:
                reponse += '\nTempo 2 : %s' % tempo2

            if tempo3 is not None:
                reponse += '\nTempo 3 : %s' % tempo3

            reponse += '\nlogging : '
            if logger.hasHandlers():
                reponse += str(logger.level)
            else:
                reponse += 'Inactif'

            reponse += '\nloghandler : '
            if logger.hasHandlers():
                reponse += str(logger.handlers[0].level)
            else:
                reponse += 'Inactif'

            """
            reponse += '\nversion : '
            if version is not None:
                reponse += str(version)
            else :
                reponse += 'Pas définie'
            """

            # Le programme utilisateur peut avoir lui aussi ses propres infos à communiquer
            reponse2 = self.traitement(msgRecu)

            if reponse2 != '':
                reponse += '\n' + reponse2

            return reponse

        if msgRecu[1].lower() == 'logging':
            if len(msgRecu) >= 3:
                if msgRecu[2].isdecimal():
                    if logger.hasHandlers():
                        #   logger.setLevel(int(msgRecu[2]))
                        logger.handlers[0].setLevel(int(msgRecu[2]))
                        reponse = 'OK, nouveau niveau de logging = ' + str(logger.handlers[0].level)
                        logger.info('%s Nouveau niveau log : %d' % (__name__, logger.handlers[0].level))
                    else:
                        reponse = 'Logger inactif'
                else:
                    reponse = 'Valeur incorrecte, %s' % msgRecu[2]
            else:
                reponse = 'Il manque le 3° paramètre (valeur)'
            return reponse

        """
        if msgRecu[1].lower() == 'loghandler':
            if len(msgRecu)>= 3:
                if msgRecu[2].isdecimal():
                    if logger.hasHandlers():
                        logger.handlers[0].setLevel(int(msgRecu[2]))
                        reponse = 'OK, nouveau niveau de debug pour logger.handlers[0] = ' + str(logger.handlers[0].level)
                        logger.info('%s Nouveau niveau logger.handlers[0] : %d' % (__name__, logger.handlers[0].level))
                    else:
                        reponse = 'Logger inactif'
                else:
                    reponse = 'Valeur incorrecte, %s' % msgRecu[2]
            else:
                reponse = 'Il manque le 3° paramètre (valeur)'
            return reponse
        """

        if msgRecu[1].lower() == 'tempo1':
            if len(msgRecu) >= 3:
                if msgRecu[2].isdecimal():
                    logger.debug('Ligne %s, demande lock', inspect.getframeinfo(inspect.currentframe())[1])
                    try:
                        donneesrecueslock.acquire()
                        logger.debug('Ligne %s, lock obtenu', inspect.getframeinfo(inspect.currentframe())[1])
                    except:
                        logger.warning('Attention, pas de verrou disponible. Il est souhaitable d\'utiliser "donneesrecueslock" pour éviter les problèmes')

                    tempo1 = float(msgRecu[2])
                    logger.debug('Ligne %s, ordre relâche lock', inspect.getframeinfo(inspect.currentframe())[1])
                    try:
                        donneesrecueslock.release()
                        logger.debug('Ligne %s, lock relâché', inspect.getframeinfo(inspect.currentframe())[1])
                    except:
                        pass

                    reponse = 'OK, nouvelle tempo 1 = ' + str(tempo1)

                    logger.info('%s Nouvelle tempo 1 : %d' % (__name__, tempo1))
                else:
                    reponse = 'Valeur incorrecte, %s' % msgRecu[2]
            else:
                reponse = 'Il manque le 3° paramètre (valeur)'
            return reponse

        if msgRecu[1].lower() == 'tempo2':
            if len(msgRecu) >= 3:
                if msgRecu[2].isdecimal():
                    if tempo2 is None:
                        reponse = 'tempo 2 n\'est pas utilisée '
                    else:
                        logger.debug('Ligne %s, demande lock', inspect.getframeinfo(inspect.currentframe())[1])
                        try:
                            donneesrecueslock.acquire()
                            logger.debug('Ligne %s, lock obtenu', inspect.getframeinfo(inspect.currentframe())[1])
                        except:
                            logger.warning('Attention, pas de verrou disponible. Il est souhaitable d\'utiliser "donneesrecueslock" pour éviter les problèmes')

                        tempo2 = float(msgRecu[2])
                        logger.debug('Ligne %s, ordre relâche lock', inspect.getframeinfo(inspect.currentframe())[1])
                        try:
                            donneesrecueslock.release()
                            logger.debug('Ligne %s, lock relâché', inspect.getframeinfo(inspect.currentframe())[1])
                        except:
                            pass

                        reponse = 'OK, nouvelle tempo 2 = ' + str(tempo2)

                        logger.info('%s Nouvelle tempo 2 : %d' % (__name__, tempo2))
                else:
                    reponse = 'Valeur incorrecte, %s' % msgRecu[2]
            else:
                reponse = 'Il manque le 3° paramètre (valeur)'
            return reponse

        if msgRecu[1].lower() == 'tempo3':
            if len(msgRecu) >= 3:
                if msgRecu[2].isdecimal():
                    if tempo3 is None:
                        reponse = 'tempo 3 n\'est pas utilisée '
                    else:
                        logger.debug('Ligne %s, demande lock', inspect.getframeinfo(inspect.currentframe())[1])
                        try:
                            donneesrecueslock.acquire()
                            logger.debug('Ligne %s, lock obtenu', inspect.getframeinfo(inspect.currentframe())[1])
                        except:
                            logger.warning('Attention, pas de verrou disponible. Il est souhaitable d\'utiliser "donneesrecueslock" pour éviter les problèmes')

                        tempo3 = float(msgRecu[2])
                        logger.debug('Ligne %s, ordre relâche lock', inspect.getframeinfo(inspect.currentframe())[1])
                        try:
                            donneesrecueslock.release()
                            logger.debug('Ligne %s, lock relâché', inspect.getframeinfo(inspect.currentframe())[1])
                        except:
                            pass

                        reponse = 'OK, nouvelle tempo 3 = ' + str(tempo3)

                        logger.info('%s Nouvelle tempo 3 : %d' % (__name__, tempo3))
                else:
                    reponse = 'Valeur incorrecte, %s' % msgRecu[2]
            else:
                reponse = 'Il manque le 3° paramètre (valeur)'
            return reponse

        return reponse

    # -----------------------------------------------------------------------------------

    def __call__(self):
        """
            À COMPLÉTER !


            Version 2: Si le traitement standard intégré n'a pas pu traiter le message, il le passe à un
            module de traitement passé par le programme appelant. Ça permet de personnaliser le traitement.
            On appelle aussi le traitement externe si le message consiste en une demande d'information.

            À améliorer selon http://www.binarytides.com/receive-full-data-with-the-recv-socket-function-in-python/ pour le timeout

                def recv_timeout(the_socket,timeout=2):
                #make socket non blocking
                the_socket.setblocking(0)

                #total data partwise in an array
                total_data=[];
                data='';

                #beginning time
                begin=time.time()
                while 1:
                    #if you got some data, then break after timeout
                    if total_data and time.time()-begin > timeout:
                        break

                    #if you got no data at all, wait a little longer, twice the timeout
                    elif time.time()-begin > timeout*2:
                        break

                    #recv something
                    try:
                        data = the_socket.recv(8192)
                        if data:
                            total_data.append(data)
                            #change the beginning time for measurement
                            begin = time.time()
                        else:
                            #sleep for sometime to indicate a gap
                            time.sleep(0.1)
                    except:
                        pass

                #join all parts to make final string
                return ''.join(total_data)

        """
        global donneesrecueslock
        global fini
        global tempo1
        global tempo2
        global tempo3

        logger = logging.getLogger()
        self.server_socket.listen(5)
        continuer = True

        while continuer:
            client_socket, address = self.server_socket.accept()
            self.server_socket.settimeout(0.0)
            self.server_socket.settimeout(None)
            logger.info('%s Connexion reçue de %s' % (__name__, address[0]))
            data = 1

            while data:
                try:
                    data = client_socket.recv(512)
                except:
                    break

                self.donneesrecues.append(data.decode())
                donneesatraiter = self.donneesrecues.pop(0)
                logger.debug('%s Données reçues : %s' % (__name__, donneesatraiter))

                if donneesatraiter != '':
                    try:
                        v = shlex.split(donneesatraiter)
                    except:
                        v = None
                        reponse = 'Désolé, j\'ai pas compris...'

                if v is not None:
                    reponse = self.__trtStandard__(v)
                    logger.debug('%s Réponse de self.__trtStandard__ : %s', __name__, reponse)

                    if reponse == 'stop':
                        r = 'OK, capito, je m\'arrête'
                        client_socket.send(r.encode())
                        # On peut aussi prévenir le client...
                        reponse = self.traitement(v)
                        break

                    if reponse == '':
                        # Le traitement standard n'a pas traité le message.
                        # On le passe donc au programme passé en paramètre
                        reponse = self.traitement(v)

                if reponse == '':
                    logger.info('%s Reçu ça : %s. Je sais pas quoi en faire.' % (__name__, donneesatraiter))
                    reponse = 'Désolé, j\'ai pas compris...'

                try:
                    # Ben oui, si l'émetteur coupe la connexion avant qu'on ne réponde, ça plante.
                    client_socket.send(reponse.encode())
                except Exception as e:
                    print('Ouh, j\'ai bien fait de mettre un try !')
                    pass

            continuer = not(fini)
            self.server_socket.settimeout(None)

        client_socket.close()
        return

    # -----------------------------------------------------------------------------
    def __del___(self):
        print('Rhââââh, je meurs...')
        logger.info('%s : Reçu l\'ordre de sabordage.', __name__)

    # -----------------------------------------------------------------------------
    def apoptose(self):
        #   https://fr.wikipedia.org/wiki/Apoptose
        global fini

        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect(('localhost', self.portEcoute))
        fini = True
        data = '%s stop' % self.moi
        client_socket.send(data.encode())

        try:
            client_socket.close()
        except:
            pass


# -----------------------------------------------------------------------------------------------------------
def chrono_trace(fonction):
    """
        Un petit décorateur pour voir le temps passé dans une fonction.
    """
    def func_wrapper(*args, **kwargs):
        debut = datetime.now()
        print('\n##\t%s, entrée dans %s' % (debut.strftime('%H:%M:%S,%f'), fonction.__name__))

        resultat = fonction(*args, **kwargs)

        fin = datetime.now()
        print('\n##\t%s, sortie de %s' % (fin.strftime('%H:%M:%S,%f'), fonction.__name__))
        print('Durée : %s\n' % (datetime.now() - debut))
        return resultat

    return func_wrapper


# -----------------------------------------------------------------------------------------------------------
def expurge(texte, remplacement='¶'):
    #   Pour pas être emmerdé aver les noms de fichiers à la con avec de l'unicode exotique.
    #   Y'a pourtant des abrutis qui pour la simple apostrophe utilisent 'u\2051'...
    return ''.join([texte[i] if ord(texte[i]) < 255 else remplacement for i in range(len(texte))])


# -----------------------------------------------------------------------------------------------------------
