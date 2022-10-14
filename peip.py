# -- Projet PEIP - Python -- #
# -- Programme de collecte et de présentation d'informations système -- #
# -- Partie Backend : Python + Flask -- #

# Modules nécessaires
from flask import Flask, render_template, url_for
from turbo_flask import Turbo
from uptime import uptime
import threading
import platform
import distro
import re
import configparser
import subprocess
import psutil
from datetime import datetime
import time
import json

# Variables de base
serveur = Flask(__name__)
turbo = Turbo(serveur)
ostype = platform.system()
config = configparser.ConfigParser()

# debut() : création d'un thread pour lancer les mises à jour des variables dans le serveur
@serveur.before_first_request
def debut():
    threading.Thread(target=updatepage).start()
    threading.Thread(target=sauvegarde).start()

# path() : détermine le chemin du script pour gérer les lectures/écritures de fichiers
def path():
    if ostype == "Windows":
        return __file__.rsplit("\\",1)[0] + "\\"
    else:
        return __file__.rsplit("/",1)[0] + "/"


# lnxdist(): détermine le nom de la distribution Linux, sinon on renvoit None
def lnxdist():
    if ostype == "Linux":
        return distro.name()
    else:
        return None


# cpuinfo() : détermine le nom/type du CPU
def cpuinfo():
    if ostype == "Linux":
        # LC_ALL=C pour forcer lscpu à donner le retour en anglais, pour chercher le model name
        lscpu = subprocess.check_output("LC_ALL=C lscpu", shell=True).strip().decode()
        for line in lscpu.split("\n"):
            if "Model name" in line:
                return re.sub(".*Model name.*:\s+", "", line, 1)
    else:
        # On renvoit platform.processor() même si ce n'est pas la même information que le model name de lscpu.
        # Le module qui renvoie le cpu model (cpuinfo.get_cpu_info()) sous windows ralentit beaucoup mon application.
        return subprocess.check_output("wmic cpu get name", shell=True).strip().decode().split("  \r\r\n")[1]


# diskagent() : pour automatiser le comptage des partitions du système et récupérer leurs informations
def diskagent():
    nbpart = len(psutil.disk_partitions())
    partitions = psutil.disk_partitions()
    # Pour windows : par psutil
    if ostype == "Windows":
        listpart = {
            "nbpart": nbpart,
            "device0": partitions[0].device,
            "capacite0": str(round(psutil.disk_usage(partitions[0].device).total / 2**30, 1)) + "G",
            "libre0": str(round(psutil.disk_usage(partitions[0].device).free / 2**30, 1)) + "G",
            "pct0": round(100 - psutil.disk_usage(partitions[0].device).percent,1),
            "fs0": psutil.disk_partitions()[0].fstype
        }

        for i in range(1, nbpart):
            listpart["device"+str(i)] = partitions[i].device
            try:
                listpart["capacite" + str(i)] = str(round(psutil.disk_usage(partitions[i].device).total / 2**30, 1)) + "G"
                listpart["libre" + str(i)] = str(round(psutil.disk_usage(partitions[i].device).free / 2**30, 1)) + "G"
                listpart["pct" + str(i)] = round(100 - psutil.disk_usage(partitions[i].device).percent,1)
                listpart["fs" + str(i)] = psutil.disk_partitions()[i].fstype
            except:
                listpart["capacite" + str(i)] = None
                listpart["libre" + str(i)] = None
                listpart["pct" + str(i)] = None
                listpart["fs" + str(i)] = None

        return listpart

    # Pour linux : par df -h (psutil ne renvoie pas les bonnes données)
    else:
        dfh = subprocess.check_output("df -h "+partitions[0].device, shell=True).strip().decode()
        infodfh = dfh.split()
        listpart = {
            "nbpart": nbpart,
            "device0": partitions[0].device,
            "capacite0": infodfh[len(infodfh) - 5],
            "libre0": infodfh[len(infodfh) - 3],
            "pct0": 100 - int(infodfh[len(infodfh) - 2].strip("%")),
            "fs0": psutil.disk_partitions()[0].fstype,
            "pmontage0": infodfh[len(infodfh) - 1]
        }
        for i in range(1, nbpart):
            dfh = subprocess.check_output("df -h " + partitions[i].device, shell=True).strip().decode()
            infodfh = dfh.split()
            listpart["device"+str(i)] = partitions[i].device
            try:
                listpart["capacite" + str(i)] = infodfh[len(infodfh) - 5]
                listpart["libre" + str(i)] = infodfh[len(infodfh) - 3]
                listpart["pct" + str(i)] = 100 - int(infodfh[len(infodfh) - 2].strip("%"))
                listpart["fs" + str(i)] = psutil.disk_partitions()[i].fstype
                listpart["pmontage" + str(i)] = infodfh[len(infodfh) - 1]
            except:
                listpart["capacite" + str(i)] = None
                listpart["libre" + str(i)] = None
                listpart["pct" + str(i)] = None
                listpart["fs" + str(i)] = None
                listpart["pmontage" + str(i)] = None

        return listpart


# svcagent() : détermine si les services contenus dans services.ini sont démarrés ou non
def svcagent():
    linitial = config.read(path()+'services.ini')
    if ostype == "Windows":
        try:
            svcini = list(config.items('Windows'))
        except:
            listsvc = {
                "nbsvc": None,
                "nomsvc0": None,
                "status0": None
            }
            return listsvc
        nbsvc = len(svcini)
        listsvc = {
                    "nbsvc": nbsvc,
                    "nomsvc0": svcini[0][1],
                    "status0": psutil.win_service_get(svcini[0][1]).as_dict()['status']
             }
        for i in range(1, nbsvc):
            try:
                listsvc["nomsvc" + str(i)] = svcini[i][1]
                listsvc["status" + str(i)] = psutil.win_service_get(svcini[i][1]).as_dict()['status']
            except:
                listsvc["nomsvc" + str(i)] = None
                listsvc["status" + str(i)] = None
    else:
        try:
            svcini = list(config.items('Linux'))
        except:
            listsvc = {
                "nbsvc": None,
                "nomsvc0": None,
                "status0": None
            }
            return listsvc
        nbsvc = len(svcini)
        listsvc = {
                    "nbsvc": nbsvc,
                    "nomsvc0": svcini[0][1],
                    "status0": subprocess.call(["systemctl", "is-active", "--quiet", svcini[0][1]])
             }
        for i in range(1, nbsvc):
            try:
                listsvc["nomsvc" + str(i)] = svcini[i][1]
                listsvc["status" + str(i)] = subprocess.call(["systemctl", "is-active", "--quiet", svcini[i][1]])
            except:
                listsvc["nomsvc" + str(i)] = None
                listsvc["status" + str(i)] = None
    return listsvc


# agent() : récupère les informations du PC hôte
def agent():
    # On récupère d'abord la date et l'heure au format DD/MM/YYYY HH:MM:SS
    dateheure = str(datetime.now().strftime("%d-%m-%Y %H:%M:%S"))
    # On essaie de récupérer les buffer/cache RAM, qui fonctionne seulement sur linux
    try:
        buffer = round(psutil.virtual_memory().buffers / 2**20, 2)
        cache = round(psutil.virtual_memory().cached / 2**20, 2)
    except:
        buffer = None
        cache = None

    # On cherche si platform.machine() renvoie une architecture finissant par 64 (amd64, AMD64 ou x86_64)
    if (re.search('64$',platform.machine())):
        cputype = 64
    else:
        cputype = 32

    # Création d'un dictionnaire comportant toutes les informations de l'hôte
    informations = {
        "date": dateheure,
        "ostype": ostype,
        "osversion": platform.release(),
        "hostname": platform.uname()[1],
        "version": platform.version(),
        "kernel": platform.platform(),
        "distribution": lnxdist(),
        "uptime": int(uptime()),
        # Uptime au format dd:hh:mm:ss
        "ddhhmmss": str(int(uptime()) // 86400)+":"+time.strftime('%H:%M:%S', time.gmtime(int(uptime()))),
        "cpuinfo": cpuinfo(),
        "cputype": cputype,
        "cpufreq": round(psutil.cpu_freq()[0] / 1000, 1),
        "nbcoeurs":  psutil.cpu_count(),
        "usagecpu": psutil.cpu_percent(),
        "ram": round(psutil.virtual_memory().total / 2**30, 2),
        "ramlibre": round(psutil.virtual_memory().free / 2**30, 2),
        "ramocc": round(psutil.virtual_memory().used / 2**30, 2),
        "rampct": psutil.virtual_memory().percent,
        "buffer": buffer,
        "cache": cache
    }
    # On récupère les n partitions et leurs infos
    listpart = diskagent()
    listsvc = svcagent()
    # rajout du dictionnaire partitions aux infos
    informations.update(listpart)
    informations.update(listsvc)
    # On peut mettre le tout au format json
    with open(path()+'static/infos-'+informations['hostname']+'.json', 'w') as jsonf:
        json.dump(informations, jsonf, indent=2)
    return informations


# index() : affiche l'index. Utile si on a plusieurs hosts, pour les centraliser et pouvoir les choisir
@serveur.route("/")
def index():
    return "<a href='"+agent()['hostname']+"'>Informations de "+agent()['hostname']+"</a>"


# page() :  affiche la page de base
@serveur.route("/"+agent()['hostname'])
def page():
    infos = agent()
    return render_template('index.html', **locals())


# updatepage() : renvoie la page infos.html avec ses variables actualisées toutes les secondes dans le serveur
def updatepage():
    with serveur.app_context():
        while True:
            infos = agent()
            turbo.push(turbo.replace(render_template('infos.html', **locals()), 'infos'))
            time.sleep(1)

def sauvegarde():
    for i in range(1, 65535):
        infos = agent()
        with open(path() + 'static/sauvegardes/infos'+str(i)+'-'+infos['hostname']+'.json', 'w') as jsonf:
            json.dump(infos, jsonf, indent=2)
        time.sleep(60)



# Lancement du serveur sur toutes les cartes, sur le port 5000
serveur.run(host="0.0.0.0", port=5000, debug=True)
