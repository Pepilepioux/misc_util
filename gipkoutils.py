#!/usr/bin/python
# -*- coding: UTF-8 -*-

from datetime import datetime, timedelta
import time


def chrono_trace(fonction):
    def func_wrapper(*args, **kwargs):
        debut = datetime.now()
        print('\n##\t%s, entrée dans %s' % (debut.strftime('%H:%M:%S,%f'), fonction.__name__))

        resultat = fonction(*args, **kwargs)

        fin = datetime.now()
        print('\n##\t%s, sortie de %s' % (fin.strftime('%H:%M:%S,%f'), fonction.__name__))
        print('Durée : %s\n' % (datetime.now() - debut))
        return resultat

    return func_wrapper
