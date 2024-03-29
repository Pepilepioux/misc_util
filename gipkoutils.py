#!/usr/bin/python
# -*- coding: UTF-8 -*-

from datetime import datetime, timedelta
import time

import os
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
import _io

try:
    import globalvars
except Exception as excpt:
    pass


# -----------------------------------------------------------------------------------------------------------
class Recepteur:
    """
        Se met à l'écoute en tcp sur le port passé en paramètre et exécute un traitement en fonction
        des instructions reçues.

        Prend deux arguments :
            1 - obligatoire
                un kwarg nommé 'vars' qui est une classe contenant au moins les variables tempo1 (float),
                fini (boolean), et donnees_recues_lock (threading.RLock)
            2 - facultatif
                une fonction qui fera un traitement spécifique sur le message reçu.

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
    def __init__(self, portEcoute, *, traitement=trt, Vars_appelant=None):
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
    def __verif_message__(self, msgRecu, Vars_appelant):
        #   logger = logging.getLogger()
        globalvars.logger.debug('Entrée dans __verif_message__\n\n')
        reponse = ''

        # Le gars paumé qui sait pas ce qu'il faut faire...
        if len(msgRecu) >= 1 and msgRecu[0] == '?':
            globalvars.logger.debug('Ligne %s, len(msgRecu) >= 1 and msgRecu[0] == ?', inspect.getframeinfo(inspect.currentframe())[1])
            reponse = self.doc

        if len(msgRecu) >= 1 and msgRecu[0].lower() == "t'es qui, toi ?":
            globalvars.logger.debug('Ligne %s, len(msgRecu) >= 1 and msgRecu[0].lower() == "t\'es qui, toi ?"', inspect.getframeinfo(inspect.currentframe())[1])
            reponse = self.moi

        if reponse == '' and len(msgRecu) >= 1 and msgRecu[0] != self.moi:
            globalvars.logger.debug('Ligne %s, reponse == \'\' and len(msgRecu) >= 1 and msgRecu[0] != self.moi', inspect.getframeinfo(inspect.currentframe())[1])
            reponse = '{0} : c\'est pas pour moi.'.format(msgRecu[0])

        if reponse == '' and len(msgRecu) < 2:
            globalvars.logger.debug('Ligne %s, reponse == \'\' and len(msgRecu) < 2', inspect.getframeinfo(inspect.currentframe())[1])
            reponse = 'Pas assez d\'arguments'

        globalvars.logger.debug('Ligne {0}, sortie vérif message = "{1}"'.format(inspect.getframeinfo(inspect.currentframe())[1], '"' + reponse + '"'))
        return reponse

    # -----------------------------------------------------------------------------------------------------------
    def __trtStandard__(self, msgRecu, Vars_appelant):
        """
            Les messages standard sont des listes dont le premier élément est le nom du programme
            (self.moi), le deuxième une instruction et le 3° une valeur.
            Si c'est une liste à moins de 2 éléments on laisse tomber.
            Et si le 1° élément de la liste n'est pas "moi", on laisse tomber aussi.
        """

        #   logger = logging.getLogger()
        globalvars.logger.debug('__trtStandard__, msgRecu = %s', msgRecu)

        reponse = self.__verif_message__(msgRecu, Vars_appelant)
        globalvars.logger.debug('Ligne %s, après vérif message, réponse :', inspect.getframeinfo(inspect.currentframe())[1])
        globalvars.logger.debug(reponse)

        # Maintenant on a un message qui a la bonne structure.
        if reponse == '':
            if msgRecu[1].lower() == 'stop':
                # C'est un ordre d'arrêt
                globalvars.logger.debug('%s Reçu un ordre d\'arrêt', __name__)

                globalvars.logger.debug('Ligne %s, demande lock', inspect.getframeinfo(inspect.currentframe())[1])
                try:
                    Vars_appelant.donnees_recues_lock.acquire()
                    #   self.lock.acquire()
                    globalvars.logger.debug('Ligne %s, lock obtenu', inspect.getframeinfo(inspect.currentframe())[1])
                except Exception as e:
                    globalvars.logger.warning('Attention, pas de verrou disponible. Il est souhaitable d\'utiliser "Vars_appelant.donnees_recues_lock" pour éviter les problèmes')

                Vars_appelant.fini = True
                globalvars.logger.debug('Ligne %s, ordre relâche lock', inspect.getframeinfo(inspect.currentframe())[1])
                try:
                    Vars_appelant.donnees_recues_lock.release()
                    #   self.lock.release()
                    globalvars.logger.debug('Ligne %s, lock relâché', inspect.getframeinfo(inspect.currentframe())[1])
                except Exception as e:
                    pass
                globalvars.logger.debug('%s fini = %s' % (__name__, Vars_appelant.fini))

                reponse = 'stop'
                return reponse

            if msgRecu[1] == '?':
                globalvars.logger.debug('Ligne %s, appel self.traitement(msgRecu)', inspect.getframeinfo(inspect.currentframe())[1])
                reponse = self.doc + self.traitement(msgRecu)
                return reponse

            if msgRecu[1] == 'info':
                if Vars_appelant.tempo1 is not None:
                    reponse = 'Tempo 1 : %s' % Vars_appelant.tempo1
                else:
                    reponse = ''

                try:
                    if Vars_appelant.tempo2 is not None:
                        reponse += '\nTempo 2 : %s' % Vars_appelant.tempo2
                except Exception as e:
                    pass

                try:
                    if Vars_appelant.tempo3 is not None:
                        reponse += '\nTempo 3 : %s' % Vars_appelant.tempo3
                except Exception as e:
                    pass

                reponse += '\nlogging : '
                if globalvars.logger.hasHandlers():
                    reponse += str(globalvars.logger.level)
                else:
                    reponse += 'Inactif'

                reponse += '\nloghandler : '
                if globalvars.logger.hasHandlers():
                    reponse += str(globalvars.logger.handlers[0].level)
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
                globalvars.logger.debug('Ligne %s, reponse2 = self.traitement(msgRecu)', inspect.getframeinfo(inspect.currentframe())[1])
                reponse2 = self.traitement(msgRecu)

                if reponse2 != '':
                    reponse += '\n' + reponse2

                return reponse

            if msgRecu[1].lower() == 'logging':
                if len(msgRecu) >= 3:
                    if msgRecu[2].isdecimal():
                        if globalvars.logger.hasHandlers():
                            #   logger.setLevel(int(msgRecu[2]))
                            globalvars.logger.setLevel(int(msgRecu[2]))
                            globalvars.logger.handlers[0].setLevel(int(msgRecu[2]))
                            try:
                                globalvars.logger.handlers[1].setLevel(int(msgRecu[2]))
                                reponse = 'OK, nouveau niveau de logging = ' + str(globalvars.logger.handlers[0].level)
                                globalvars.logger.info('%s Nouveau niveau log : %d' % (__name__, globalvars.logger.handlers[0].level))
                            except Exception as e:
                                globalvars.logger.warning('Il n\'y a pas de logger.handler[1]')
                        else:
                            reponse = 'Logger inactif'
                    else:
                        reponse = 'Valeur incorrecte, %s' % msgRecu[2]
                else:
                    reponse = 'Il manque le 3° paramètre (valeur)'
                return reponse

            if msgRecu[1].lower() == 'tempo1':
                if len(msgRecu) >= 3:
                    if msgRecu[2].isdecimal():
                        globalvars.logger.debug('Ligne %s, demande lock', inspect.getframeinfo(inspect.currentframe())[1])
                        try:
                            Vars_appelant.donnees_recues_lock.acquire()
                            globalvars.logger.debug('Ligne %s, lock obtenu', inspect.getframeinfo(inspect.currentframe())[1])
                        except Exception as e:
                            globalvars.logger.warning('Attention, pas de verrou disponible. Il est souhaitable d\'utiliser "Vars_appelant.donnees_recues_lock" pour éviter les problèmes')

                        Vars_appelant.tempo1 = float(msgRecu[2])
                        globalvars.logger.debug('Ligne %s, ordre relâche lock', inspect.getframeinfo(inspect.currentframe())[1])
                        try:
                            Vars_appelant.donnees_recues_lock.release()
                            globalvars.logger.debug('Ligne %s, lock relâché', inspect.getframeinfo(inspect.currentframe())[1])
                        except Exception as e:
                            pass

                        reponse = 'OK, nouvelle tempo 1 = ' + str(Vars_appelant.tempo1)

                        globalvars.logger.info('%s Nouvelle tempo 1 : %d' % (__name__, Vars_appelant.tempo1))
                    else:
                        reponse = 'Valeur incorrecte, %s' % msgRecu[2]
                else:
                    reponse = 'Il manque le 3° paramètre (valeur)'
                return reponse

            if msgRecu[1].lower() == 'tempo2':
                if len(msgRecu) >= 3:
                    if msgRecu[2].isdecimal():
                        globalvars.logger.debug('Ligne %s, demande lock', inspect.getframeinfo(inspect.currentframe())[1])
                        try:
                            Vars_appelant.donnees_recues_lock.acquire()
                            globalvars.logger.debug('Ligne %s, lock obtenu', inspect.getframeinfo(inspect.currentframe())[1])
                        except Exception as e:
                            globalvars.logger.warning('Attention, pas de verrou disponible. Il est souhaitable d\'utiliser "Vars_appelant.donnees_recues_lock" pour éviter les problèmes')

                        try:
                            Vars_appelant.tempo2 = float(msgRecu[2])
                            reponse = 'OK, nouvelle tempo 2 = ' + str(Vars_appelant.tempo2)
                        except Exception as e:
                            reponse = 'tempo 2 n\'est pas utilisée '

                        globalvars.logger.debug('Ligne %s, ordre relâche lock', inspect.getframeinfo(inspect.currentframe())[1])
                        try:
                            Vars_appelant.donnees_recues_lock.release()
                            globalvars.logger.debug('Ligne %s, lock relâché', inspect.getframeinfo(inspect.currentframe())[1])
                        except Exception as e:
                            pass

                        globalvars.logger.info('%s Nouvelle tempo 2 : %d' % (__name__, Vars_appelant.tempo2))
                    else:
                        reponse = 'Valeur incorrecte, %s' % msgRecu[2]
                else:
                    reponse = 'Il manque le 3° paramètre (valeur)'
                return reponse

            if msgRecu[1].lower() == 'tempo3':
                if len(msgRecu) >= 3:
                    if msgRecu[2].isdecimal():
                        globalvars.logger.debug('Ligne %s, demande lock', inspect.getframeinfo(inspect.currentframe())[1])
                        try:
                            Vars_appelant.donnees_recues_lock.acquire()
                            globalvars.logger.debug('Ligne %s, lock obtenu', inspect.getframeinfo(inspect.currentframe())[1])
                        except Exception as e:
                            globalvars.logger.warning('Attention, pas de verrou disponible. Il est souhaitable d\'utiliser "Vars_appelant.donnees_recues_lock" pour éviter les problèmes')

                        try:
                            Vars_appelant.tempo3 = float(msgRecu[2])
                            reponse = 'OK, nouvelle tempo 2 = ' + str(Vars_appelant.tempo3)
                        except Exception as e:
                            reponse = 'tempo 3 n\'est pas utilisée '

                        globalvars.logger.debug('Ligne %s, ordre relâche lock', inspect.getframeinfo(inspect.currentframe())[1])
                        try:
                            Vars_appelant.donnees_recues_lock.release()
                            globalvars.logger.debug('Ligne %s, lock relâché', inspect.getframeinfo(inspect.currentframe())[1])
                        except Exception as e:
                            pass

                        globalvars.logger.info('%s Nouvelle tempo 2 : %d' % (__name__, Vars_appelant.tempo3))
                    else:
                        reponse = 'Valeur incorrecte, %s' % msgRecu[2]
                else:
                    reponse = 'Il manque le 3° paramètre (valeur)'
                return reponse

        return reponse

    # -----------------------------------------------------------------------------------

    def __call__(self, **kwargs):
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
                    except Exception as e:
                        pass

                #join all parts to make final string
                return ''.join(total_data)

        """

        self.server_socket.listen(5)
        continuer = True

        while continuer:
            try:
                client_socket, address = self.server_socket.accept()
            except Exception as e:
                globalvars.logger.error('Erreur client_socket, address = self.server_socket.accept() : %s' % e)

            try:
                self.server_socket.settimeout(0.0)
                self.server_socket.settimeout(None)
            except Exception as e:
                globalvars.logger.error('Erreur self.server_socket.settimeout : %s' % e)

            globalvars.logger.info('%s Connexion reçue de %s' % (__name__, address[0]))
            data = 1

            while data:
                try:
                    data = client_socket.recv(512)
                except Exception as excpt:
                    globalvars.logger.error('Erreur data = client_socket.recv : %s ' % excpt)
                    break

                self.donneesrecues.append(data.decode())
                donneesatraiter = self.donneesrecues.pop(0)
                globalvars.logger.debug('%s Données reçues : %s' % (__name__, donneesatraiter))

                if donneesatraiter != '':
                    try:
                        v = shlex.split(donneesatraiter)
                    except Exception as e:
                        v = None
                        globalvars.logger.debug('Ligne %s, except du shlex', inspect.getframeinfo(inspect.currentframe())[1])
                        reponse = 'Désolé, j\'ai pas compris...'

                if v is not None:
                    reponse = self.__trtStandard__(v, kwargs['vars'])
                    globalvars.logger.debug('%s Réponse de self.__trtStandard__ : %s\n', __name__, '"' + reponse + '"')

                    if reponse == 'stop':
                        r = 'OK, capito, je m\'arrête'
                        client_socket.send(r.encode())
                        break

                    if reponse == '':
                        # Le traitement standard n'a pas traité le message.
                        # On le passe donc au programme passé en paramètre
                        globalvars.logger.debug('Ligne %s, appel self.traitement(msgRecu) parce que le traitement standard n\'a pas traité le message.', inspect.getframeinfo(inspect.currentframe())[1])
                        reponse = self.traitement(v)

                if reponse == '':
                    globalvars.logger.info('%s Reçu ça : %s. Je sais pas quoi en faire.' % (__name__, donneesatraiter))
                    reponse = 'Désolé, j\'ai pas compris...'

                try:
                    # Ben oui, si l'émetteur coupe la connexion avant qu'on ne réponde, ça plante.
                    envoyes = client_socket.send(reponse.encode())
                except Exception as e:
                    globalvars.logger.warning('Ouh, j\'ai bien fait de mettre un try !')
                    pass

            continuer = not(kwargs['vars'].fini)
            self.server_socket.settimeout(None)

        client_socket.close()
        return

    # -----------------------------------------------------------------------------
    def __del___(self):
        globalvars.logger.info('%s : Reçu l\'ordre de sabordage.', __name__)

    # -----------------------------------------------------------------------------
    def apoptose(self):
        #   https://fr.wikipedia.org/wiki/Apoptose

        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect(('localhost', self.portEcoute))
        #   kwargs['vars'].fini = True
        data = '%s stop' % self.moi
        client_socket.send(data.encode())

        try:
            client_socket.close()
        except Exception as e:
            pass


# -----------------------------------------------------------------------------------------------------------
def chrono_trace_V0(fonction):
    """
        Un petit décorateur pour voir le temps passé dans une fonction.

        Évolution 2018-10-23 : on utilise la clé '__fichierLog__' de kwargs.
            Si elle n'existe pas, les infos sont affichées par un 'print'
            Si c'est un fichier (résultat d'un "open..."), on écrit les résultats
                dans ce fichier
            Si c'est une chaine de caractères, on considère que c'est un nom de fichier
                et on écrit les résultats dans ce fichier ouvert en mode 'append'
    """
    logger = logging.getLogger()

    def func_wrapper(*args, **kwargs):
        def output(texte, **kwargs):
            try:
                fic = kwargs['__fichierLog__']
                if type(fic) == _io.TextIOWrapper:
                    fic.write('{0}\n'.format(texte))
                else:
                    if type(fic) == str:
                        with open(fic, 'a') as f:
                            f.write('{0}\n'.format(texte))
                    else:
                        if type(fic) == logging.RootLogger:
                            logger.info(texte)
                        else:
                            print(texte)

            except Exception as e:
                print(texte)

        #   --------------------------------------------------
        debut = datetime.now()
        texte = '\n##\t%s, entrée dans %s' % (debut.strftime('%H:%M:%S,%f'), fonction.__name__)
        output(texte, **kwargs)

        resultat = fonction(*args, **kwargs)

        fin = datetime.now()
        texte = '\n##\t%s, sortie de %s\nDurée : %s\n' % (fin.strftime('%H:%M:%S,%f'), fonction.__name__, (datetime.now() - debut))
        output(texte, **kwargs)
        return resultat

    return func_wrapper


# -----------------------------------------------------------------------------------------------------------
def chrono_trace(fonction):
    """
        Un petit décorateur pour voir le temps passé dans une fonction.

        Évolution 2018-10-23 : on utilise la clé '__fichierLog__' de kwargs.
            Si elle n'existe pas, les infos sont affichées par un 'print'
            Si c'est un fichier (résultat d'un "open..."), on écrit les résultats
                dans ce fichier
            Si c'est une chaine de caractères, on considère que c'est un nom de fichier
                et on écrit les résultats dans ce fichier ouvert en mode 'append'

        Évolution 2018-11-15 :
            la clé '__fichierLog__' de kwargs peut aussi être un logger.

            Modification de la présentation : au lieu d'écrire une ligne au début, une ligne
            avec l'heure de fin et une ligne pour la durée les 3 infos sont rassemblées sur une
            seule ligne, écrite à la sortie de la fonction.
    """
    logger = logging.getLogger()

    def func_wrapper(*args, **kwargs):
        def output(texte, **kwargs):
            try:
                fic = kwargs['__fichierLog__']
                if type(fic) == _io.TextIOWrapper:
                    fic.write('{0}\n'.format(texte))
                else:
                    if type(fic) == str:
                        with open(fic, 'a') as f:
                            f.write('{0}\n'.format(texte))
                    else:
                        if type(fic) == logging.RootLogger:
                            logger.info(texte)
                        else:
                            print(texte)

            except Exception as e:
                print(texte)

        #   --------------------------------------------------
        debut = datetime.now()
        resultat = fonction(*args, **kwargs)
        fin = datetime.now()

        texte = '{0}, entrée à {1}, sortie à {2}, durée : {3}'.format(fonction.__name__, debut.strftime('%H:%M:%S,%f'), fin.strftime('%H:%M:%S,%f'), (fin - debut))
        output(texte, **kwargs)
        return resultat

    return func_wrapper


# -----------------------------------------------------------------------------------------------------------
def conserver_dates(fonction):
    """
        Un petit décorateur pour pouvoir faire des modifs dans un fichier en conservant la date de dernière
        modification originale.

        Contrainte : le premier argument passé à la fonction doit être le nom du fichier à modifier.
    """
    def func_wrapper(*args, **kwargs):
        nomfic = args[0]
        dates_fichier = {'a': os.path.getatime(nomfic), 'm': os.path.getmtime(nomfic)}

        resultat = fonction(*args, **kwargs)

        os.utime(nomfic, (dates_fichier['a'], dates_fichier['m']))
        return resultat
    return func_wrapper


# -----------------------------------------------------------------------------------------------------------
def expurge(texte, remplacement='¶'):
    #   Pour pas être emmerdé aver les noms de fichiers à la con avec de l'unicode exotique.
    #   Y'a pourtant des abrutis qui pour la simple apostrophe utilisent 'u\2051'...
    return ''.join([texte[i] if ord(texte[i]) < 255 else remplacement for i in range(len(texte))])


# -----------------------------------------------------------------------------------------------------------
def dateIsoVersTimestamp(date):
    return datetime.strptime(date, '%Y-%m-%d %H:%M:%S').timestamp()


# -----------------------------------------------------------------------------------------------------------
def dateIsoVersTs(date):
    return dateIsoVersTimestamp(date)


# -----------------------------------------------------------------------------------------------------------
def timestampVersDateIso(ts):
    return datetime.strftime(datetime.fromtimestamp(ts), '%Y-%m-%d %H:%M:%S')


# -----------------------------------------------------------------------------------------------------------
def tsVersDateIso(ts):
    return timestampVersDateIso(ts)
