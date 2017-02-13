#!/usr/bin/python
# -*- coding: UTF-8 -*-
"""
    Exemple d'utilisation du module "recepteur"

    Contexte :
    J'ai une très vieille appli qUi utilise une base de données MS Access 97 (!...). On s'est trouvés un jour
    avec cette base vérolée, et on ne s'en est rendus compte que plusieurs semaines plus tard.
    Donc pour éviter tout le travail de réparation, ou du moins le limiter, un serveur S1 fait des sauvegardes
    régulières de la base, puis envoie au serveur S2 un ordre de vérification. Ce programme tourne sur le serveur S2

    Principe :
    On lance un recepteur avec comme fonction traitementCommandeRecue. Cette fonction analyse le message reçu,
    valorise quelques variables globales et monte un évènement.

    Le programme principal, lui, boucle avec une tempo sur la réception de message. Quand il a reçu un message
    et que la fonction traitementCommandeRecue a renseigné les variables attendues (évènement "on") il lance un
    thread en passant toutes les infos à la fonction verifBase, et il attend, toujours avec une tempo, qu'elle se termine.
    La fonction de vérification envoie un message pour dire que ça s'est bien -ou mal- passé, et si la tempo du
    programme principal a expiré il envoie lui aussi un message d'alerte.

    Ça peut paraître un peu compliqué, mais comme ça si la vérification plante ou boucle on garde la main
    sur le programme.

    Utilisation pour test :
    Adapter les variables "sender" et "serveur".
    Lancer le programme.
    Dans un autre terminal lancer la commande "python controleur.py -d localhost -p 5001" pour ouvrir la communication,
    puis au prompt :
    "exemple_recepteur.py zyva" pour simuler une vérification
    "exemple_recepteur.py stop" pour arrêter ce programme
    Regarder les logs.

    Réutilisation IRL :
    Activez vos méninges et adaptez !
"""
import sys
import os
import configparser
import datetime
import locale
import logging
import multiprocessing
import smtplib
import socket
import time
import threading
import random
import pyodbc
import gipkomail
import gipkoutils as gu

logger = logging.getLogger()


# ------------------------------------------------------------------------------------
def LireParametres():
    erreur = []
    Fpgm = os.path.realpath(__file__)
    nomFichierIni = os.path.join(os.path.dirname(Fpgm), os.path.splitext(os.path.basename(Fpgm))[0]) + '.ini'
    nomFichierLog = os.path.join(os.path.dirname(Fpgm), os.path.splitext(os.path.basename(Fpgm))[0]) + '.log'

    config = configparser.RawConfigParser()
    config.read(nomFichierIni)

    try:
        nomBase = config.get('Fichiers', 'BdD')
    except Exception as e:
        erreur.append('Erreur lecture nom base de données, %s' % e)
        nomBase = ''

    try:
        destinataire = config.get('Destinataires', 'A')
    except Exception as e:
        erreur.append('Erreur lecture destinataire, %s' % e)
        destinataire = ''

    try:
        copies = config.get('Destinataires', 'CC')
        listeCopies = copies.split(',')
    except Exception as e:
        listeCopies = []

    try:
        tempo1 = config.getfloat('General', 'tempo1')
    except Exception as e:
        tempo1 = 10.0

    try:
        tempo2 = config.getfloat('General', 'tempo2')
    except Exception as e:
        tempo2 = 120.0

    try:
        portEcoute = int(config.get('Communication', 'port'))
    except:
        portEcoute = 5999

    try:
        niveauLog = int(config.get('General', 'niveauLog'))
    except:
        niveauLog = logging.INFO

    return nomBase, nomFichierLog, niveauLog, destinataire, listeCopies, tempo1, tempo2, portEcoute, erreur


# ------------------------------------------------------------------------------------
def verifBase(**kwargs):
    # C'est chiant, comme on est dans un autre thread il faut lui créer son propre logger...
    niveauLog = kwargs['loggerLevel']
    nomFichierLog = kwargs['nomFichierLog']
    loggerlocal = logging.getLogger()
    loggerlocal.setLevel(niveauLog)
    formatter = logging.Formatter('%(asctime)s\t%(levelname)s\t%(message)s')
    Handler = logging.handlers.WatchedFileHandler(nomFichierLog)
    Handler.setLevel(niveauLog)
    Handler.setFormatter(formatter)
    Handler.set_name('Normal')
    loggerlocal.addHandler(Handler)

    nomBase = kwargs['nomBase']
    queue = kwargs['q']
    serveur = kwargs['serveur']
    sender = kwargs['sender']
    destinataire = kwargs['destinataire']
    listeCopies = kwargs['listeCopies']

    loggerlocal.info('\tDébut verifBase %s' % nomBase)

    baseEnBonEtat = (random.randint(0, 4) != 0)
    delai = random.random() * 10
    loggerlocal.debug('verifBase, sleep %s' % delai)

    # Appel fonction de vérification. On simule ça par un sleep...
    time.sleep(delai)

    texte = 'Fonction verifBase terminée résultat = %s, delai = %s' % (baseEnBonEtat, delai)
    gipkomail.envoyer_message(serveur, sender, destinataire, 'BdD', contenu_texte=texte)

    queue.put(baseEnBonEtat)

    loggerlocal.info('\tFin verifBase %s' % nomBase)
    del(loggerlocal)
    return


# ------------------------------------------------------------------------------------
def traitementCommandeRecue(messageRecu):
    global gblBaseATraiter
    global serveur
    global sender
    global destinataire
    global listeCopies
    global subject
    global moi
    global nomBase
    global nomFichierErr

    logger = logging.getLogger()

    logger.debug(messageRecu)
    reponse = ''

    if len(messageRecu) >= 2 \
            and messageRecu[0] == moi \
            and messageRecu[1].lower() == 'zyva':
        # Odre de lancement de la vérif.
        # baseATraiter = nomBase
        gblBaseATraiter = nomBase
        if len(messageRecu) >= 3 \
                and messageRecu[2] != '':
            # baseATraiter = messageRecu[2]
            gblBaseATraiter = messageRecu[2]

        logger.debug('traitementCommandeRecue, gblBaseATraiter = %s' % gblBaseATraiter)
        reponse = 'Thread de vérification lancé'
        logger.info(reponse)

    evtMsgRecu.set()

    return reponse

# ------------------------------------------------------------------------------------

if __name__ == '__main__':
    locale.setlocale(locale.LC_TIME, '')
    sender = 'moi@mon.domaine'
    subject = ''
    serveur = 'exchange.mon.domaine'
    moi = sys.argv[0]
    nomBase, nomFichierLog, niveauLog, destinataire, listeCopies, gu.tempo1, gu.tempo2, portEcoute, erreur = LireParametres()
    gblBaseATraiter = ''

    logger.setLevel(niveauLog)

    # Voir test100_logger_3_creer_handlers.py pour les différents handlers
    formatter = logging.Formatter('%(asctime)s\t%(levelname)s\t%(message)s')
    Handler = logging.handlers.WatchedFileHandler(nomFichierLog)
    Handler.setLevel(niveauLog)
    Handler.setFormatter(formatter)
    Handler.set_name('Normal')
    logger.addHandler(Handler)
    logger.info('Début du programme')

    if erreur:
        for e in erreur:
            logger.error('%s%s\n' % ('\t', e))
        exit()

    continuer = True
    logger.debug('Création evtMsgRecu')
    evtMsgRecu = threading.Event()

    if continuer:
        logger.debug('Création récepteur')
        try:
            reception = gu.Recepteur(portEcoute, traitement=traitementCommandeRecue)
            logger.debug('Création donneesrecueslock')
            gu.donneesrecueslock = threading.RLock()
            logger.debug('Création tReception')
            tReception = threading.Thread(target=reception)
            tReception.start()
            logger.debug('Création q0')
            q0 = multiprocessing.Queue()
            logger.debug('Clear events')
            evtMsgRecu.clear()
        except Exception as e:
            logger.error(e)
            continuer = False

            gipkomail.envoyer_message(serveur, sender, destinataire, 'Vérif BdD', contenu_texte='%s' % e)

    # Y'a p'têt' moyen de mettre ça dans une fonction à part...
    pRequeteKwargs = {}
    pRequeteKwargs['q'] = q0
    pRequeteKwargs['nomFichierLog'] = nomFichierLog
    pRequeteKwargs['niveauLog'] = niveauLog
    pRequeteKwargs['serveur'] = serveur
    pRequeteKwargs['sender'] = sender
    pRequeteKwargs['destinataire'] = destinataire
    pRequeteKwargs['listeCopies'] = listeCopies

    logger.debug('Début de la boucle')
    while continuer:
        recuUnMessage = evtMsgRecu.wait(gu.tempo1)
        logger.debug('recuUnMessage: %s' % recuUnMessage)
        logger.debug('tReception.is_alive: %s' % tReception.is_alive())

        if recuUnMessage:
            evtMsgRecu.clear()
            logger.debug('gblBaseATraiter : %s' % gblBaseATraiter)

            if gblBaseATraiter != '':
                pRequeteKwargs['nomBase'] = gblBaseATraiter

                try:
                    pRequeteKwargs['loggerLevel'] = logger.handlers[0].level
                    # Parce qu'il peut changer dynamiquement...
                    pRequete = multiprocessing.Process(target=verifBase, kwargs=pRequeteKwargs)
                    pRequete.start()
                    pRequetePid = pRequete.pid
                    logger.debug('pRequete lancée (pid = %s), on attend le q0.get' % pRequetePid)

                    try:
                        baseEnBonEtat = q0.get(block=True, timeout=gu.tempo2)
                        logger.debug('q0.get exécuté, baseEnBonEtat = %s' % baseEnBonEtat)
                    except Exception as e:
                        texteErreur = 'La vérification de la base %s ne s\'est pas terminée dans le temps imparti (%s secondes). Elle est vraisemblablement vérolée' % (gblBaseATraiter, gu.tempo2)
                        logger.error(texteErreur)
                        gipkomail.envoyer_message(serveur, sender, destinataire, 'Vérif Bdd', contenu_texte=texteErreur)
                        if pRequete.is_alive():
                            pRequete.terminate()

                except Exception as e:
                    logger.error('Planton dans le lancement du sous-process, %s' % e)

                gblBaseATraiter = ''

        gu.donneesrecueslock.acquire()
        continuer = not(gu.fini)
        gu.donneesrecueslock.release()

    logger.info('Fin du programme')
