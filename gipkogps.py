#!/usr/bin/python
# -*- coding: UTF-8 -*-

"""
    Un paquet de petits utilitaires pour exploiter les traces GPS. Calcul de distance entre deux points,
    recherche (dans une arborescence de fichiers traces) de traces passant à proximité d'un point donné, etc
"""


import argparse
import os
import sys
import time
import locale
import logging
import logging.handlers
import xml.etree.ElementTree
import math
import numpy as np

import monitoring

rEquat = 6378137
rPole = 6356752.3
rEquat2 = rEquat * rEquat
rPole2 = rPole * rPole

xml.etree.ElementTree.register_namespace('', 'http://www.topografix.com/GPX/1/1')
xml.etree.ElementTree.register_namespace('xsi', 'http://www.w3.org/2001/XMLSchema-instance')
xml.etree.ElementTree.register_namespace('xsi:schemaLocation', 'http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd')
locale.setlocale(locale.LC_ALL, '')
logger = logging.getLogger()


# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
class PointGPS(tuple):
    """
        Pour un point défini par ses coordonnées GPS (en degrés décimaux) et son altitude,
        définit en plus ses coordonnées cartésiennes et le vecteur entre le centre de la terre et ce point
    """
    def __init__(self, point: tuple):
        self.latDeg = point[0]
        self.lonDeg = point[1]
        self.alt = point[2]

        self.latRad = self.latDeg * math.pi / 180
        self.lonRad = self.lonDeg * math.pi / 180
        self.R = rayonTerre(self.latRad, True) + self.alt

        self.X = self.R * math.cos(self.latRad) * math.cos(self.lonRad)
        self.Y = self.R * math.cos(self.latRad) * math.sin(self.lonRad)
        self.Z = self.R * math.sin(self.latRad)
        self.vecteur = np.array([self.X, self.Y, self.Z])

    def vecteur(self):
        return self.vecteur

    def print(self):
        print('L = %s, l = %s, z = %s. R = %s\nX = %s Y= %s Z = %s' % (self.latDeg, self.lonDeg, self.alt, self.R, self.X, self.Y, self.Z))


# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
def rayonTerre(latitude, radians=False):
    """
        Retourne le rayon de la terre à la latitude donnée.
        Source: https://en.wikipedia.org/wiki/Earth_radius
    """
    if not radians:
        latitude = latitude  * math.pi / 180

    rayon = math.sqrt(
                      (((rEquat2 * math.cos(latitude)) * (rEquat2 * math.cos(latitude))) + ((rPole2 * math.sin(latitude)) * (rPole2 * math.sin(latitude)))) /
                      (((rEquat * math.cos(latitude)) * (rEquat * math.cos(latitude))) + ((rPole * math.sin(latitude)) * (rPole * math.sin(latitude))))
    )

    return rayon

# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
def rayonTerreV0(latitude, radians=False):
    """
        Retourne le rayon de la terre à la latitude donnée.
        Source: https://en.wikipedia.org/wiki/Earth_radius
    """
    if not radians:
        latitude = latitude  * math.pi / 180

    rayon = math.sqrt(
                      (((rEquat2 * math.cos(latitude)) ** 2) + ((rPole2 * math.sin(latitude)) ** 2)) /
                      (((rEquat * math.cos(latitude)) ** 2) + ((rPole * math.sin(latitude)) ** 2))
    )

    return rayon

#   ---------------------------------------------------------------------------------------------
def calculerBounds(nomFic, et, root, majBounds):
    """
        Certains fichiers GPX ont un élément "bounds" qui donne les latitudes et longitude nini et maxi de la trace.
        Ça peut être utile.
        Cette fonction calcule ces bornes si l'information ne se trouve pas dans le fichier, et sur demande (argument
        majBounds) ajoute l'info au fichier d'origine (après en avoir fait une copie de sauvegarde)
    """
    maxlat = -90.0
    minlat = 90.0
    minlon = 180.0
    maxlon = -180.0

    for trkpt in root.iter('{http://www.topografix.com/GPX/1/1}trkpt'):
        if float(trkpt.attrib['lon']) < minlon:
            minlon = float(trkpt.attrib['lon'])

        if float(trkpt.attrib['lon']) > maxlon:
            maxlon = float(trkpt.attrib['lon'])

        if float(trkpt.attrib['lat']) < minlat:
            minlat = float(trkpt.attrib['lat'])

        if float(trkpt.attrib['lat']) > maxlat:
            maxlat = float(trkpt.attrib['lat'])

    bounds = {'maxlat': maxlat, 'minlat': minlat, 'minlon': minlon, 'maxlon': maxlon}

    if majBounds:
        try:
            os.rename(nomFic, nomFic + '_V0')

            metadataTag = xml.etree.ElementTree.SubElement(root, '{http://www.topografix.com/GPX/1/1}metadata')
            boundsTag = xml.etree.ElementTree.SubElement(metadataTag, '{http://www.topografix.com/GPX/1/1}bounds')

            boundsTag.attrib['minlat'] = '{0}'.format(minlat)
            boundsTag.attrib['maxlat'] = '{0}'.format(maxlat)
            boundsTag.attrib['minlon'] = '{0}'.format(minlon)
            boundsTag.attrib['maxlon'] = '{0}'.format(maxlon)

            try:
                et.write(nomFic, xml_declaration=True, encoding='utf-8', method='xml')
                print('Fichier {0} réécrit avec ajout bounds'.format(nomFic))
            except:
                print('Pas pu écrire bounds dans {0}'.format(nomFic))

        except:
            print('Pas pu renommer {0}'.format(nomFic))

    return bounds


# -----------------------------------------------------------------------------------------------------------------------------------------------------------
def chercherTraces_V0(nomRepBase, latitude, longitude, delta, majBounds):
    listeFichiers = []

    for D, dirs, fics in os.walk(nomRepBase):
        for fic in fics:
            if os.path.splitext(fic)[1].lower() != '.gpx':
                #   print('\tFichier {0} ignoré'.format(fic))
                continue

            nomComplet = os.path.join(D, fic)
            if selectionnerFichier(nomComplet, latitude, longitude, delta, majBounds):
                listeFichiers.append(nomComplet)

    return listeFichiers


# -----------------------------------------------------------------------------------------------------------------------------------------------------------
def chercherTracesProches(nomRepBase, ptRef, dMax):
    """
        Renvoie la liste de tous les fichiers gpx de l'arborescence nomRepBase correspondant à une trace
        qui passe à moins de delta km du point (latitude, longitude)
    """
    listeFichiers = []

    for D, dirs, fics in os.walk(nomRepBase):
        for fic in fics:
            if os.path.splitext(fic)[1].lower() != '.gpx':
                #   print('\tFichier {0} ignoré'.format(fic))
                continue

            nomComplet = os.path.join(D, fic)
            try:
                logging.debug('On traite {0}'.format(nomComplet))
                listePts = extrairePoints(nomComplet)
                #   print('\nOn teste {0}'.format(nomComplet))
                if traceProche(listePts, ptRef, dMax):
                    #   print('C\'est bon')
                    listeFichiers.append(nomComplet)
                #   else:
                #       print('Raté, d = {0:2.5f}'.format(distancePointTrace(listePts, ptRef)[0]))
            except Exception as e:
                print('\tFichier {0} : y\'a un chni : {1}'.format(nomComplet, e))

    return listeFichiers


# -----------------------------------------------------------------------------------------------------------------------------------------------------------
def listeTraces(nomRepBase):
    """
        Renvoie la liste de tous les fichiers gpx de l'arborescence nomRepBase
    """
    listeFichiers = []

    for D, dirs, fics in os.walk(nomRepBase):
        for fic in fics:
            if os.path.splitext(fic)[1].lower() != '.gpx':
                #   print('\tFichier {0} ignoré'.format(fic))
                continue

            nomComplet = os.path.join(D, fic)
            listeFichiers.append(nomComplet)

    return listeFichiers
# -----------------------------------------------------------------------------------------------------------------------------------------------------------
def resumerTraces(nomRepBase, fichierSortie, separateur=';'):
    """
        Pour tous les fichiers gpx de l'arborescence nomRepBase donne les informations nom du fichier,
        nombre de points, distance entre le point 0 et les points situés au quart, à la moitié, aux trois
        quarts, et le point final.
        Met tout ça dans un fichier csv
    """
    listeFichiers = listeTraces(nomRepBase)
    listeResultats = []
    enTete = ['Fichier', 'Nb points', '1 / 4', '1 / 2', '3 / 4', 'distance totale']
    listeResultats.append(separateur.join(enTete))
    for fic in listeFichiers:
        print(fic)
        try:
            listePts = extrairePoints(fic)
            listeValeurs = [fic, locale.format('%d',len(listePts))]
            for i in range(1,4):
                listeValeurs.append(locale.format('%.3f', distanceP(listePts[0], listePts[int(len(listePts) * i / 4)])))
            listeValeurs.append(locale.format('%.3f', distanceP(listePts[0], listePts[-1])))
            listeResultats.append(separateur.join(listeValeurs))
        except Exception as e:
            print('\tOups ! {0}'.format(e))
            continue

    with open(fichierSortie, 'w') as s:
        for e in listeResultats:
            s.write('{0}\n'.format(e))


# -----------------------------------------------------------------------------------------------------------------------------------------------------------
def selectionnerFichierParBounds(nomFic, latitude, longitude, delta, majBounds):
    """
        Indique si le point (latitude, longitude) se trouve dans le rectangle contenant la trace
        décrite par le fichier nomFic
    """
    et = xml.etree.ElementTree.parse(nomFic)
    root = et.getroot()

    boundsTag = root.iter('{http://www.topografix.com/GPX/1/1}bounds')
    bounds = None
    for elt in boundsTag:
        bounds = {cle: float(elt.attrib[cle]) for cle in elt.attrib}
        break

    if not bounds:
        bounds = calculerBounds(nomFic, et, root, majBounds)

    hauteur = bounds['maxlat'] - bounds['minlat']
    largeur = bounds['maxlon'] - bounds['minlon']

    bounds['maxlat'] += (hauteur * delta)
    bounds['minlat'] -= (hauteur * delta)
    bounds['maxlon'] += (largeur * delta)
    bounds['minlon'] -= (largeur * delta)

    return ((bounds['minlat'] <= latitude <= bounds['maxlat']) and (bounds['minlon'] <= longitude <= bounds['maxlon']))


# -----------------------------------------------------------------------------------------------------------------------------------------------------------
def selectionnerFichier(nomFic, latitude, longitude, delta, majBounds):
    """
        À voir..
    """
    et = xml.etree.ElementTree.parse(nomFic)
    root = et.getroot()

    boundsTag = root.iter('{http://www.topografix.com/GPX/1/1}bounds')
    bounds = None
    for elt in boundsTag:
        bounds = {cle: float(elt.attrib[cle]) for cle in elt.attrib}
        break

    if not bounds:
        bounds = calculerBounds(nomFic, et, root, majBounds)

    hauteur = bounds['maxlat'] - bounds['minlat']
    largeur = bounds['maxlon'] - bounds['minlon']

    bounds['maxlat'] += (hauteur * delta)
    bounds['minlat'] -= (hauteur * delta)
    bounds['maxlon'] += (largeur * delta)
    bounds['minlon'] -= (largeur * delta)

    return ((bounds['minlat'] <= latitude <= bounds['maxlat']) and (bounds['minlon'] <= longitude <= bounds['maxlon']))


# -----------------------------------------------------------------------------------------------------------------------------------------------------------
def extrairePoints(nomFic):
    """
        Renvoie la liste des points de trace du fichier nomFic sous la forme d'une liste de
        tuples (latitude, longitude, altitude).
    """
    et = xml.etree.ElementTree.parse(nomFic)
    root = et.getroot()
    listePoints = []

    for trkpt in root.iter('{http://www.topografix.com/GPX/1/1}trkpt'):
        lat = float(trkpt.attrib['lat'])
        lon = float(trkpt.attrib['lon'])
        ele = trkpt.find('{http://www.topografix.com/GPX/1/1}ele')
        alt = 0.0 if ele is None else float(ele.text)
        listePoints.append((lat, lon, alt))

    return listePoints


# -----------------------------------------------------------------------------------------------------------------------------------------------------------
def traceProcheBourrin(trk: list, ptRef: tuple, dMax: float):
    """
        Détermine si dans la liste de points trk il y en a au moins un qui est à
        moins de dMax km du point ptRef.
        Par la méthode bourrin, c'est à dire qu'on calcule la distance de ptRef à tous les points
        de la liste.
    """
    i = 0
    trouve = False
    while i < len(trk):
        dist = distanceP(trk[i], ptRef)
        #   print('Point {0}. On est à {1} km.'.format(i, dist))
        if dist <= dMax:
            #   print('bingo ! Après {0} essais'.format(nbEssais))
            trouve = True
            break

        i += 1
        #   print('Avec un pas de {2} km, il faut faire au moins {3} étapes. On saute au point {0}'.format(i, dist, pas, nbPasMin))

    return trouve


# -----------------------------------------------------------------------------------------------------------------------------------------------------------
def traceProche_V0(trk: list, ptRef: tuple, dMax: float, echantillons=20):
    """
        Détermine si dans la liste de points trk il y en a au moins un qui est à
        moins de dMax km du point ptRef.
    """
    dMax2 = dMax * dMax
    proche = False
    #   print('dMax2 : {0:5.3f}'.format(dMax2))

    if len(trk) <= echantillons:
        #   On y va pour un calcul pour chaque point. Après tout y'en n'a plus tant que ça...
        for pt in trk:
            dist2 = distanceP2(pt, ptRef)
            if dist2 <= dMax2:
                proche = True
                break

    else:
        #   liste de points échantillons
        lEch = [int(i * (len(trk) / echantillons)) for i in range(echantillons)] + [len(trk) -1]
        #   Liste des distances entre le point échantillon et le point de référence
        ldist = []
        ildist = 0
        for ipt in lEch:
            dist2 = distanceP2(trk[ipt], ptRef)
            if dist2 <= dMax2:
                proche = True
                #   print('Trouvé d2 à {0:5.3f}'.format(dist2))
                break   #   Oui, je sais, on pourrait mettre ici "return True", mais c'est vraiment dégueulasse.

            ldist.append([ildist, ipt, dist2])
            ildist += 1

        if not proche:
            ldist.sort(key=lambda x: x[2])
            """
                En tête de cette liste on a donc les deux points de la trace qui sont les plus proches
                du point de référence. Normalement ils sont consécutifs, mais c'est pas garanti.

                LE point de la trace le plus proche du point de référence se trouve vraisemblablement entre
                ces deux points.
                Pour conjurer le mauvais sort on va considérer qu'il doit être entre le point précédant le
                premier et le point suivant le deuxième.
            """
            #   print(ldist)
            #   for ipt in range(len(lEch)):
            #       print('{0} : pt {1}, d² = {2:5.3f}'.format(ldist[ipt][0],  ldist[ipt][1],  ldist[ipt][2]))

            ltemp = ldist[:2]
            ltemp.sort()    #   Bin oui, on n'est pas sûr que le point le plus proche soit, dans la trace, avant le suivant...
            if any(e.level <= logging.DEBUG for e in logger.handlers):
                for e in ldist[:4]:
                    print(e)

            i1 = max(ltemp[0][0] - 1, 0)
            i2 = min(ltemp[1][0] + 1, len(lEch) - 1)

            #   Et on récurse sur le nouveau segment
            if abs(lEch[i2] - lEch[i1] + 1) == len(trk):
                #   Les deux points les plus proches sont les extrémités de la trace
                logging.debug('Les deux points les plus proches sont les extrémités de la trace')
                if distanceP2(trk[lEch[i2]], ptRef) <= dMax2 or distanceP2(trk[lEch[i1]], ptRef) <= dMax2:
                    proche = True
                    logging.debug('C\'est bon.')
                else:
                    proche = False
                    logging.debug('C\'est foutu !')
            else:
                logging.debug('La liste a {0} points'.format(len(trk)))
                logging.debug('On récurse entre les points {0} et {1}'.format(lEch[i1], lEch[i2]))
                proche = traceProche(trk[lEch[i1]:lEch[i2]], ptRef, dMax, echantillons=echantillons)

    return proche


# -----------------------------------------------------------------------------------------------------------------------------------------------------------
def traceProche(traceComplete: list, ptRef: tuple, dMax, sliceStart=None, sliceEnd=None, echantillons=20):
    """
        Renvoie la distance entre un point donné et une trace (C'est la distance minimale entre
        ce point et tous les points de la traceComplete) et les informations sur le point de la traceComplete le plus proche

        Le retour est un tuple :
        - distance mini
        - index du point de trace le plus proche du point de référence
        - tuple (latitude, longitude, altitude) du point en question
        - nombre de récursions. Intéressant en phase d'étude et de mise au point. On
            pourra le virer sans état d'âme.
    """
    logging.debug('distancePointTrace. {1} points de trace, echantillons = {0}'.format(echantillons, len(traceComplete)))
    dMax2 = dMax * dMax
    proche = False

    if sliceStart is None:
        sliceStart = 0
    if sliceEnd is None:
        sliceEnd = len(traceComplete)

    if sliceEnd - sliceStart <= echantillons:
        #   On y va pour un calcul pour chaque point. Après tout y'en n'a plus tant que ça...
        logging.debug('sliceEnd - sliceStart <= echantillons')
        for i in range(sliceStart, sliceEnd):
            dist2 = distanceP2(traceComplete[i], ptRef)
            if dist2 <= dMax2:
                proche = True
                logging.debug('Point {0} ({1} à {2} de ptRef'.format(i, traceComplete[i], dist2))
                break
        if not proche:
            logging.debug('Raté...')

    else:
        #   liste de points échantillons
        lEch = [int(i * ((sliceEnd - sliceStart) / echantillons)) + sliceStart for i in range(echantillons)] + [sliceEnd -1]
        if any(nl.level <= logging.DEBUG for nl in logger.handlers):
            logging.debug('Liste des points échantillons :')
            for e in lEch:
                logging.debug(e)

        #   Liste des distances entre le point échantillon et le point de référence
        ldist = []

        for (ildist, ipt) in enumerate(lEch):
            dist2 = distanceP2(traceComplete[ipt], ptRef)
            if dist2 <= dMax2:
                proche = True
                logging.debug('Point {0} ({1} à {2} de ptRef'.format(ipt, traceComplete[ipt], dist2))
                break   #   Oui, je sais, on pourrait mettre ici "return True", mais c'est vraiment dégueulasse.
            ldist.append([ildist, ipt, dist2])

        if not proche:
            ldist.sort(key=lambda x: x[2])
            if any(nl.level <= logging.DEBUG for nl in logger.handlers):
                logging.debug('ldist :')
                for e in ldist:
                    logging.debug(e)
            """
                En tête de cette liste on a donc les deux points de la trace qui sont les plus proches
                du point de référence. Normalement ils sont consécutifs, mais c'est pas garanti.

                LE point de la trace le plus proche du point de référence se trouve vraisemblablement entre
                ces deux points.
                Pour conjurer le mauvais sort on va considérer qu'il doit être entre le point précédant le
                premier et le point suivant le deuxième.
            """

            ltemp = ldist[:2]
            ltemp.sort()    #   Bin oui, on n'est pas sûr que le point le plus proche soit, dans la trace, avant le suivant...

            if any(nl.level <= logging.DEBUG for nl in logger.handlers):
                logging.debug('ltemp :')
                for e in ltemp:
                    logging.debug(e)

            i1 = max(ltemp[0][0] - 1, 0)
            i2 = min(ltemp[1][0] + 1, len(lEch) - 1)
            logging.debug('i1 : {0}. i2 : {1}'.format(i1, i2))
            logging.debug('On récurse entre les points {0} et {1}'.format(lEch[i1], lEch[i2] + 1))

            #   Et on récurse sur le nouveau segment
            #   Sauf...
            if lEch[i1] == sliceStart and lEch[i2] + 1 == sliceEnd:
                """
                    Les deux points les plus proches sont les extrémités du segment. Si on essaie de dichotomer
                    encore, on va boucler. Donc c'est fini.

                    Ça encore, c'est à creuser. Si on est tombé sur ces points directement, c'est sûr. Sinon, si
                    on récurse entre ces points parce qu'on a étendu la tranche (voir plus haut), ça vaut peut-être
                    le coup de tenter une récursion SANS extension de tranche...
                """

                logging.debug('Les deux points les plus proches sont les extrémités de la trace')
                proche = (ltemp[0][2] <= dMax2)
                logging.debug('OK' if proche else 'raté')
            else:
                #   proche = traceProche(trk[lEch[i1]:lEch[i2]], ptRef, dMax, echantillons=echantillons)
                proche = traceProche(traceComplete, ptRef, dMax, lEch[i1], lEch[i2] + 1, echantillons=echantillons)

    return proche


# -----------------------------------------------------------------------------------------------------------------------------------------------------------
def distancePointTrace(traceComplete: list, ptRef: tuple, sliceStart=None, sliceEnd=None, echantillons=20, nbPassages=None):
    """
        Renvoie la distance entre un point donné et une trace (C'est la distance minimale entre
        ce point et tous les points de la traceComplete) et les informations sur le point de la traceComplete le plus proche

        Le retour est un tuple :
        - distance mini
        - index du point de trace le plus proche du point de référence
        - tuple (latitude, longitude, altitude) du point en question
        - nombre de récursions. Intéressant en phase d'étude et de mise au point. On
            pourra le virer sans état d'âme.
    """
    logging.debug('distancePointTrace, echantillons = {0}'.format(echantillons))
    dmin2 = float('inf')
    if sliceStart is None:
        sliceStart = 0
    if sliceEnd is None:
        sliceEnd = len(traceComplete)

    if nbPassages is None:
        nbPassages = 1
    else:
        nbPassages += 1

    if sliceEnd - sliceStart <= echantillons:
        #   On y va pour un calcul pour chaque point. Après tout y'en n'a plus tant que ça...
        logging.debug('sliceEnd - sliceStart <= echantillons')
        for i in range(sliceStart, sliceEnd):
            dist2 = distanceP2(traceComplete[i], ptRef)
            if dist2 <= dmin2:
                dmin2 = dist2
                ptProche = traceComplete[i]
                iptProche = i
        dmin = math.sqrt(dmin2)
        retour = (dmin, iptProche, ptProche, nbPassages)

    else:
        #   liste de points échantillons
        lEch = [int(i * ((sliceEnd - sliceStart) / echantillons)) + sliceStart for i in range(echantillons)] + [sliceEnd -1]
        if any(nl.level <= logging.DEBUG for nl in logger.handlers):
            logging.debug('Liste des points échantillons :')
            for e in lEch:
                logging.debug(e)

        #   Liste des distances entre le point échantillon et le point de référence
        ldist = []
        """
        ildist = 0
        for ipt in lEch:
            dist2 = distanceP2(traceComplete[ipt], ptRef)
            ldist.append([ildist, ipt, dist2])
            ildist += 1
        """

        for (ildist, ipt) in enumerate(lEch):
            dist2 = distanceP2(traceComplete[ipt], ptRef)
            ldist.append([ildist, ipt, dist2])

        ldist.sort(key=lambda x: x[2])
        if any(nl.level <= logging.DEBUG for nl in logger.handlers):
            logging.debug('ldist :')
            for e in ldist:
                logging.debug(e)
        """
            En tête de cette liste on a donc les deux points de la trace qui sont les plus proches
            du point de référence. Normalement ils sont consécutifs, mais c'est pas garanti.

            LE point de la trace le plus proche du point de référence se trouve vraisemblablement entre
            ces deux points.
            Pour conjurer le mauvais sort on va considérer qu'il doit être entre le point précédant le
            premier et le point suivant le deuxième.
        """

        ltemp = ldist[:2]
        ltemp.sort()    #   Bin oui, on n'est pas sûr que le point le plus proche soit, dans la trace, avant le suivant...

        if any(nl.level <= logging.DEBUG for nl in logger.handlers):
            logging.debug('ltemp :')
            for e in ltemp:
                logging.debug(e)

        i1 = max(ltemp[0][0] - 1, 0)
        i2 = min(ltemp[1][0] + 1, len(lEch) - 1)
        logging.debug('i1 : {0}. i2 : {1}'.format(i1, i2))
        logging.debug('On récurse entre les points {0} et {1}'.format(lEch[i1], lEch[i2] + 1))

        #   Et on récurse sur le nouveau segment
        #   Sauf...
        if lEch[i1] == sliceStart and lEch[i2] + 1 == sliceEnd:
            """
                Les deux points les plus proches sont les extrémités du segment. Si on essaie de dichotomer
                encore, on va boucler. Donc c'est fini.

                Ça encore, c'est à creuser. Si on est tombé sur ces points directement, c'est sûr. Sinon, si
                on récurse entre ces points parce qu'on a étendu la tranche (voir plus haut), ça vaut peut-être
                le coup de tenter une récursion SANS extension de tranche...
            """
            logging.debug('Les deux points les plus proches sont les extrémités du segment, on sort.')
            ltemp.sort(key=lambda x: x[2])
            retour = (math.sqrt(ltemp[0][2]), ltemp[0][1], traceComplete[ltemp[0][1]], nbPassages)
        else:
            #   proche = traceProche(trk[lEch[i1]:lEch[i2]], ptRef, dMax, echantillons=echantillons)
            dmin, dummy1, dummy2, dummy3 = distancePointTrace(traceComplete, ptRef, lEch[i1], lEch[i2] + 1, echantillons=echantillons, nbPassages=nbPassages)
            retour = (dmin, dummy1, dummy2, dummy3)

    return retour


# -----------------------------------------------------------------------------------------------------------------------------------------------------------
def distanceP_V0(p1: tuple, p2: tuple, km=True)-> float:
    """
        renvoie la distance entre deux points (tuples latitude, longitude, altitude) calculée par le théorème 
        de Pythagore.
        Simple, mais utilisable seulement sur de courtes distances.

        Version initiale : on renvoie la vraie distance. Dans la version suivante on renvoie la racinne carrée
        du carré de la distance. C'est pareil, mais c'est décomposé en deux fonctions, parce que quand il s'agit
        simplement de faire des comparaisons les carrés suffisent, on économise en performances le coût de
        l'extraction de la racine carrée.
    """
    lat1 = p1[0]
    lon1 = p1[1]
    alt1 = p1[2]
    lat2 = p2[0]
    lon2 = p2[1]
    alt2 = p2[2]

    rLatDeg = rayonTerre((lat1 + lat2) / 2) + ((alt2 + alt2) / 2)

    distParallele = abs(rLatDeg * math.cos(((lat1 + lat2) / 2) * math.pi / 180) * ((lon2 - lon1) * math.pi / 180))
    distMeridien = abs(rLatDeg * (lat2 - lat1) * math.pi / 180)
    distVerticale = abs(alt2 - alt1)

    distTotale = math.sqrt((distParallele * distParallele) + (distMeridien *distMeridien) + (distVerticale * distVerticale))

    if km:
        distTotale = distTotale / 1000
    return distTotale


# -----------------------------------------------------------------------------------------------------------------------------------------------------------
def distanceP2(p1: tuple, p2: tuple, km=True)-> float:
    """
        renvoie le carré la distance entre deux points (tuples latitude, longitude, altitude) calculée par le théorème 
        de Pythagore.
        Simple, mais utilisable seulement sur de courtes distances.
        Carré parce que pour faire des comparaisons, supérieur ou inférieur, on peut travailler sur les carrés des
        distances plutôt que sur les distances elles-mêmes et ça évite une très gourmande extraction de racine carrée.
    """
    lat1 = p1[0]
    lon1 = p1[1]
    alt1 = p1[2]
    lat2 = p2[0]
    lon2 = p2[1]
    alt2 = p2[2]

    rLatDeg = rayonTerre((lat1 + lat2) / 2) + ((alt2 + alt2) / 2)

    distParallele = abs(rLatDeg * math.cos(((lat1 + lat2) / 2) * math.pi / 180) * ((lon2 - lon1) * math.pi / 180))
    distMeridien = abs(rLatDeg * (lat2 - lat1) * math.pi / 180)
    distVerticale = abs(alt2 - alt1)

    distTotale2 = (distParallele * distParallele) + (distMeridien *distMeridien) + (distVerticale * distVerticale)

    if km:
        distTotale2 = distTotale2 / 1000000
    return distTotale2


# -----------------------------------------------------------------------------------------------------------------------------------------------------------
def distanceP(p1: tuple, p2: tuple, km=True)-> float:
    """
        renvoie la distance entre deux points (tuples latitude, longitude, altitude) calculée par le théorème 
        de Pythagore.
        Simple, mais utilisable seulement sur de courtes distances.
    """
    return math.sqrt(distanceP2(p1, p2, km))


# ---------------------------------------------------------------------------------------------
def distanceV(v1: np.array, v2: np.array, km=True)-> float:
    """
        Renvoie la distance entre deux points par l'arc sinus du produit vectoriel de leurs vecteurs
        (voir la classe PointGPS)
    """
    # sinAlpha = np.linalg.norm(np.cross(v1, v2)) / (np.linalg.norm(v1)* np.linalg.norm(v2))
    alpha = math.asin(np.linalg.norm(np.cross(v1, v2)) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
    if np.dot(v1, v2) < 0:
        #   Cas alpha > pi / 2...
        alpha = math.pi - alpha

    D = alpha * ((np.linalg.norm(v1) + np.linalg.norm(v2)) / 2) 
    if km:
        D = D / 1000
    return D


# ---------------------------------------------------------------------------------------------
def degreDecimal_Vers_DegMinSec(dms: float)-> tuple:
    """
        Renvoie un tuple degrés, minutes, secondes, côté à partir d'une valeur en degrés décimaux.
        Selon que la valeur correspond à une latitude ou une longitude, côté vaut 1 pour est ou nord,
        -1 pour ouest ou sud
        """
    if dms < 0:
        signe = -1
        dms = dms * -1
    else:
        signe = 1

    degres = int(dms)
    decimales = dms - degres
    minDec = decimales * 60
    minutes = int(minDec)
    decimales = minDec - minutes
    secDec = decimales * 60
    secondes = int(secDec)
    decimales = int((secDec - secondes) * 10000)
    return(signe, degres, minutes, secondes, decimales)


# ---------------------------------------------------------------------------------------------
def DegMinSec_Vers_degreDecimal(dms: tuple)-> float:
    """
        Renvoie un réel degré décimal à partir d'une valeur en degrés, minutes, secondes.
        À améliorer pour qu'elle puisse prendre en entrée des trucs comme "44° 56' 41.77" 
    """

    return dms[0] + (dms[1] / 60) + (dms[2] / 3600)



# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
