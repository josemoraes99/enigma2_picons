#!/bin/python2
# -*- coding: utf-8 -*-

__version__ = "0.3.9"


import argparse
import sys
import logging
import os
import io
import re
import unicodedata
import json
import urllib2
import threading
import time
import uuid
import urllib
from functools import wraps
import socket
__progress__ = 0

reload(sys)
sys.setdefaultencoding('utf-8')

DEBUG_MODE = False

CONFIG = {
    'updateurl': "https://raw.githubusercontent.com/josemoraes99/enigma2_picons/master/picons.py",
    'urlPicons': "https://hk319yfwbl.execute-api.sa-east-1.amazonaws.com/prod",
    'e2dir': '/etc/enigma2/',
    'lambedbFile': '/etc/enigma2/lamedb',
    'localPiconDirectory': '/usr/share/enigma2/picon/',
    'bouquetGroup': ["bouquets.radio", "bouquets.tv"],
    'tvheadendAddress': 'localhost',
    'tvheadendPort': '9981',
    'tvheadendPiconDirectory': '/home/root/tvheadend_picons/',
    'tvheadendChannelConfigDirectory': '/home/root/.hts/tvheadend/channel/config/',
    'tvheadendAuth': '',
    'dl_simultaneos': 14,
}

DEV_CONFIG = {
    'updateurl': CONFIG['updateurl'],
    'urlPicons': CONFIG['urlPicons'],
    'e2dir': 'etc/',
    'lambedbFile': 'etc/lamedb',
    'localPiconDirectory': 'picon/',
    'bouquetGroup': CONFIG['bouquetGroup'],
    'tvheadendAddress': 'e2.lan',
    'tvheadendPort': '9981',
    'tvheadendPiconDirectory': 'tvheadend_picons/',
    'tvheadendChannelConfigDirectory': 'etc/tvheadend/channel/config/',
    'tvheadendAuth': '',
    'dl_simultaneos': 14,
}


def update(dl_url, force_update=False):
    """
Attempts to download the update url in order to find if an update is needed.
If an update is needed, the current script is backed up and the update is
saved in its place.
"""
    def compare_versions(vA, vB):
        """
Compares two version number strings
@param vA: first version string to compare
@param vB: second version string to compare
@author <a href="http_stream://sebthom.de/136-comparing-version-numbers-in-jython-pytho/">Sebastian Thomschke</a>
@return negative if vA < vB, zero if vA == vB, positive if vA > vB.
"""
        if vA == vB:
            return 0

        def num(s):
            if s.isdigit():
                return int(s)
            return s

        seqA = map(num, re.findall('\d+|\w+', vA.replace('-SNAPSHOT', '')))
        seqB = map(num, re.findall('\d+|\w+', vB.replace('-SNAPSHOT', '')))

        # this is to ensure that 1.0 == 1.0.0 in cmp(..)
        lenA, lenB = len(seqA), len(seqB)
        for i in range(lenA, lenB):
            seqA += (0,)
        for i in range(lenB, lenA):
            seqB += (0,)

        rc = cmp(seqA, seqB)

        if rc == 0:
            if vA.endswith('-SNAPSHOT'):
                return -1
            if vB.endswith('-SNAPSHOT'):
                return 1
        return rc

    # dl the first 256 bytes and parse it for version number
    try:
        http_stream = urllib.urlopen(dl_url)
        # update_file = http_stream.read(256)
        update_file = http_stream.read(300)
        http_stream.close()

    except IOError, (errno, strerror):
        logging.info("Unable to retrieve version data")
        logging.info("Error %s: %s" % (errno, strerror))
        return

    match_regex = re.search(r'__version__ *= *"(\S+)"', update_file)
    if not match_regex:
        logging.info("No version info could be found")
        return
    update_version = match_regex.group(1)

    if not update_version:
        logging.info("Unable to parse version data")
        return

    if force_update:
        logging.info("Forcing update, downloading version %s..." %
                     update_version)

    else:
        cmp_result = compare_versions(__version__, update_version)
        if cmp_result < 0:
            logging.info("Newer version %s available, downloading..." %
                         update_version)
        elif cmp_result > 0:
            logging.info("Local version %s newer then available %s, not updating." % (
                __version__, update_version))
            return
        else:
            logging.info("You already have the latest version.")
            return

    # dl, backup, and save the updated script
    app_path = os.path.realpath(sys.argv[0])
    # if __asModule__ == True:
    #     app_path = __file__

    if not os.access(app_path, os.W_OK):
        logging.info("Cannot update -- unable to write to %s" % app_path)

    dl_path = app_path + ".new"
    backup_path = app_path + ".old"
    try:
        dl_file = open(dl_path, 'w')
        http_stream = urllib.urlopen(dl_url)
        total_size = None
        bytes_so_far = 0
        chunk_size = 8192
        try:
            total_size = int(http_stream.info().getheader(
                'Content-Length').strip())
        except:
            # The header is improper or missing Content-Length, just download
            dl_file.write(http_stream.read())

        while total_size:
            chunk = http_stream.read(chunk_size)
            dl_file.write(chunk)
            bytes_so_far += len(chunk)

            if not chunk:
                break

            percent = float(bytes_so_far) / total_size
            percent = round(percent*100, 2)
            sys.stdout.write("Downloaded %d of %d bytes (%0.2f%%)\r" %
                             (bytes_so_far, total_size, percent))

            if bytes_so_far >= total_size:
                sys.stdout.write('\n')

        http_stream.close()
        dl_file.close()
    except IOError, (errno, strerror):
        logging.info("Download failed")
        logging.info("Error %s: %s" % (errno, strerror))
        return

    try:
        os.rename(app_path, backup_path)
    except OSError, (errno, strerror):
        logging.info("Unable to rename %s to %s: (%d) %s" %
                     (app_path, backup_path, errno, strerror))
        return

    try:
        os.rename(dl_path, app_path)
    except OSError, (errno, strerror):
        logging.info("Unable to rename %s to %s: (%d) %s" %
                     (dl_path, app_path, errno, strerror))
        return

    try:
        import shutil
        shutil.copymode(backup_path, app_path)
    except:
        os.chmod(app_path, 0755)

    logging.info("New version installed as %s" % app_path)
    logging.info("(previous version backed up to %s)" % (backup_path))
    return True

# def convert_size(size_bytes):
#     if size_bytes == 0:
#         return "0B"
#     size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
#     i = int(math.floor(math.log(size_bytes, 1024)))
#     p = math.pow(1024, i)
#     s = round(size_bytes / p, 2)
#     return "%s %s" % (s, size_name[i])

# update_progress() : Displays or updates a console progress bar
# Accepts a float between 0 and 1. Any int will be converted to a float.
# A value under 0 represents a 'halt'.
# A value at 1 or bigger represents 100%


def update_progress(progress):
    if DEBUG_MODE:
        return

    barLength = 50  # Modify this to change the length of the progress bar
    status = ""
    if isinstance(progress, int):
        progress = float(progress)
    if not isinstance(progress, float):
        progress = 0
        status = "error: progress var must be float\r\n"
    if progress < 0:
        progress = 0
        status = "Halt...\r\n"
    if progress >= 1:
        progress = 1
        status = "\r\n"
        # status = "Done...\r\n"
    block = int(round(barLength*progress))
    text = "\rProgresso: [{0}] {1}% {2}".format(
        "="*block + " "*(barLength-block), int(progress*100), status)
    # text = "\rPercent: [{0}] {1}% {2}".format( "="*block + " "*(barLength-block), int(progress*100), status)
    sys.stdout.write(text)
    sys.stdout.flush()


def retry(ExceptionToCheck, tries=4, delay=3, backoff=2, logger=None):
    """Retry calling the decorated function using an exponential backoff.

    http://www.saltycrane.com/blog/2009/11/trying-out-retry-decorator-python/
    original from: http://wiki.python.org/moin/PythonDecoratorLibrary#Retry

    :param ExceptionToCheck: the exception to check. may be a tuple of
        exceptions to check
    :type ExceptionToCheck: Exception or tuple
    :param tries: number of times to try (not retry) before giving up
    :type tries: int
    :param delay: initial delay between retries in seconds
    :type delay: int
    :param backoff: backoff multiplier e.g. value of 2 will double the delay
        each retry
    :type backoff: int
    :param logger: logger to use. If None, print
    :type logger: logging.Logger instance
    """
    def deco_retry(f):

        @wraps(f)
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return f(*args, **kwargs)
                except ExceptionToCheck, e:
                    msg = "%s, Retrying in %d seconds..." % (str(e), mdelay)
                    if logger:
                        logger.warning(msg)
                    else:
                        print msg
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return f(*args, **kwargs)

        return f_retry  # true decorator

    return deco_retry


def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


@retry(urllib2.URLError, tries=4, delay=3, backoff=2)
def urlopen_with_retry(url):
    return urllib2.urlopen(url)


def downloadFile(url, fileArr, conf):
    global __progress__
    if DEBUG_MODE:
        print("Downloading " + url)

    imgdata = urlopen_with_retry(url).read()

    for dlArr in fileArr:
        if dlArr[0] == "e2":
            filename = conf['localPiconDirectory'] + dlArr[1]
            with open(filename, 'wb') as f:
                if DEBUG_MODE:
                    print("Saving " + filename)
                f.write(imgdata)

        if dlArr[0] == "tvh":
            filename = conf['tvheadendPiconDirectory'] + dlArr[1]
            if not os.path.isdir(conf['tvheadendPiconDirectory']):
                os.mkdir(conf['tvheadendPiconDirectory'])

            with open(filename, 'wb') as f:
                if DEBUG_MODE:
                    print("Saving " + filename)
                f.write(imgdata)

    if DEBUG_MODE:
        print("concluido " + url)

    __progress__ += 1


def downloadPicons(listDw, conf):
    logging.info("Enviando lista dos picons")
    global __progress__
    piconsList = []
    receivedList = []
    downloadList = []
    numDownloads = 0

    for file in listDw:
        piconsList.append(file[0])

    uuidOne = uuid.getnode()
    piconsList = list(dict.fromkeys(piconsList))
    data = {'src': 'e2', 'node': uuidOne, 'listChannel': piconsList}
    data = json.dumps(data)
    # print(data)
    req = urllib2.Request(conf['urlPicons'], data, {
                          'Content-Type': 'application/json'})
    fil = urllib2.urlopen(req)
    # response = json.load(fil)
    # print(response)
    # data  = json.load(response)
    # print(response)
    # listURL = ast.literal_eval(response)  # procurar alternativa
    listURL = json.load(fil)
    fil.close()

    if DEBUG_MODE:
        print( json.dumps(listURL, sort_keys=True, indent=4) )
        print( "Downloads simultaneos: ",CONFIG['dl_simultaneos'])
        # time.sleep(5)

    for l in listURL:
        found = False
        for rl in receivedList:
            if l[1] == rl[0]:
                found = True
                rl[1].append(l[0])

        if found == False:
            receivedList.append([l[1], [l[0]]])

    for l in receivedList:
        for chan in l[1]:
            # print chan
            for file in listDw:
                if file[0] == chan:

                    found = False
                    for dl in downloadList:
                        if dl[0] == l[0]:
                            found = True
                            dl[1] = dl[1] + file[1]  # combine array

                    if found == False:
                        downloadList.append([l[0], file[1]])

    logging.info("Download dos arquivos")

    threads = []

    update_progress(float(0))

    numDownloads = len(downloadList)

    for dl in downloadList:
        if numDownloads > 0:
            prog = float(__progress__) / float(numDownloads)
            update_progress(prog)
        t = threading.Thread(target=downloadFile, args=(dl[0], dl[1], conf))
        t.start()
        threads.append(t)
        while threading.active_count() > CONFIG['dl_simultaneos']:
            # print(threading.active_count())
            time.sleep(0.1)


    while __progress__ < numDownloads:
        if threading.active_count() == 1:
            break
        prog = float(__progress__) / float(numDownloads)
        update_progress(prog)
        time.sleep(0.3)

    update_progress(float(1))

    map(lambda t: t.join(), threads)


def lerLameDb(f):
    logging.info("Lendo arquivo " + f)
    if os.path.isfile(f):
        lDb = []
        finalList = []
        with io.open(f, encoding='utf-8', errors='ignore') as f:
            for line in f:
                lDb.append(line)

        for x in range(0, len(lDb)):
            # print x
            if lDb[x].startswith("p:"):
                nomeCanal = lDb[x - 1].strip()
                tmpId = lDb[x - 2].strip().split(":")
                oPosit = format(int(tmpId[4]), 'x')
                if oPosit == "80":
                    oPosit = "1"

                idChannel = "1:0:" + oPosit + ":" + tmpId[0].lstrip("0") + ":" + tmpId[2].lstrip(
                    "0") + ":" + tmpId[3].lstrip("0") + ":" + tmpId[1] + ":0:0:0"

                canalclean = re.sub(re.compile('\W'), '', ''.join(c.lower() for c in unicodedata.normalize(
                    'NFKD', nomeCanal.replace("+", "mais")).encode('ascii', 'ignore') if not c.isspace()))

                filenameE2 = idChannel.replace(":", "_").upper() + '.png'
                if canalclean != "":
                    finalList.append([filenameE2, canalclean])

        return finalList
    else:
        logging.info("Arquivo nao encontrado")
        return False


def lerBouquetGroup(conf):
    g = conf['bouquetGroup']
    bResult = []
    for b in g:
        bResult = bResult + lerArquivoBouquet(b, conf)

    listChan = []
    for f in bResult:
        listChan = listChan + lerArquivoUserBouquet(f, conf)

    listChClean = []
    for l in listChan:
        if l not in listChClean:
            listChClean.append(l)

    return listChClean


def lerArquivoBouquet(f, conf):
    fileR = conf['e2dir'] + f
    logging.info("Lendo arquivo " + fileR)
    if os.path.isfile(fileR):
        with io.open(fileR, encoding='utf-8', errors='ignore') as f:
            resp = []
            for line in f:
                if line.startswith("#SERVICE"):
                    resp.append(line.split('BOUQUET "')[1].split('" ')[0])
            return resp

    else:
        logging.info("Arquivo nao encontrado")
        return False


def lerArquivoUserBouquet(f, conf):
    excludeBouquets = ["1:0:CA", "1:320:0"]  # tres primeiros
    fileR = conf['e2dir'] + f
    channels = []
    logging.info("Lendo arquivo " + fileR)
    if os.path.isfile(fileR):
        with io.open(fileR, encoding='utf-8', errors='ignore') as f:
            resp = []
            for line in f:
                if line.startswith("#SERVICE"):
                    lineSpl = line.split('#SERVICE ')[1].strip()
                    if "::" in lineSpl:
                        tmpChannel = lineSpl.split("::")
                        canalclean = re.sub(re.compile('\W'), '', ''.join(c.lower() for c in unicodedata.normalize(
                            'NFKD', tmpChannel[1].replace("+", "mais")).encode('ascii', 'ignore') if not c.isspace()))

                        filenameE2 = tmpChannel[0].replace(
                            ":", "_").upper() + '.png'
                        channels.append([filenameE2, canalclean])

            return channels


def remove_duplicates(a):
    tmpList = []
    finalList = []
    for item in a:
        found = False
        if item[1].strip() != "":
            for curItem in tmpList:
                if item[0] == curItem[0] and item[1] == curItem[1]:
                    found = True

            if found == False:
                # tmpList.append([item[1],[["e2", item[0]]]])
                tmpList.append([item[0], item[1]])

    for i in tmpList:
        found = False
        for f in finalList:
            if i[1] == f[0]:
                found = True
                f[1].append(["e2", i[0]])

        if found == False:
            # i[1].append(["e2", i[1]])
            # else:
            finalList.append([i[1], [["e2", i[0]]]])

    return finalList


def mergeLists(listE2, listTvh):
    finalList = []
    for item in listE2:
        for itemTvh in listTvh:
            if item[0] == itemTvh[1]:
                # print "found " + itemTvh[0]
                item[1].append(["tvh", itemTvh[0]])

        finalList.append(item)

    for itemTvh in listTvh:
        itemFound = False
        for itemFinal in finalList:
            if itemTvh[1] == itemFinal[0]:
                itemFound = True

        if itemFound == False:
            # print "new item " + itemTvh[1]
            finalList.append([itemTvh[1], [["tvh", itemTvh[0]]]])

    return finalList


def check_for_tvh(conf):
    """
    Verifica se tvh ok
    """

    logging.info("Verificando TVHeadend")

    resp = False

    logging.info("TVHeadend running")
    try:
        req = urllib2.Request(
            "http://" + conf['tvheadendAddress'] + ":" + conf['tvheadendPort'] + '/api/serverinfo')
        urllib2.urlopen(req)
    except urllib2.HTTPError as e_error:
        logging.info("TVHeadend com autenticação, utilize --help")
        logging.info('Error code: %s', e_error.code)
    except urllib2.URLError as e_error:
        logging.info("TVHeadend nao encontrado")
        logging.info('Reason: %s', e_error.reason)
    else:
        resp = True

    return resp


def getTvhChannelList(conf):
    logging.info("Obtendo lista de canais do TVHeadend")
    finalList = []
    req = urllib2.Request("http://" + conf['tvheadendAuth'] +
                          conf['tvheadendAddress'] + ":" + conf['tvheadendPort'] + '/api/channel/list')
    fil = urllib2.urlopen(req)
    listURL = json.load(fil)
    fil.close()

    for l in listURL['entries']:
        canalclean = re.sub(re.compile('\W'), '', ''.join(c.lower() for c in unicodedata.normalize(
            'NFKD', l['val'].replace("+", "mais")).encode('ascii', 'ignore') if not c.isspace()))
        canalTvh = re.sub(re.compile('\W'), '', ''.join(c.lower() for c in unicodedata.normalize(
            'NFKD', l['val'].replace("+", "plus").replace("&", "and")).encode('ascii', 'ignore') if not c.isspace()))

        if canalclean == 'namenotset':
            continue

        item = []
        item.append(canalTvh + ".png")
        item.append(canalclean)
        found = False
        for it in finalList:
            if it[1] == canalclean:
                found = True
        if found == False and canalclean != "":
            finalList.append(item)
    return finalList


def changeTvhConfig(conf):
    logging.info("Alterando configuracao do TVHeadend")
    tvhreq = urllib.urlopen("http://" + conf['tvheadendAuth'] + conf['tvheadendAddress'] + ":" + conf['tvheadendPort'] +
                            '/api/config/save?node={"chiconpath":"file:///home/root/tvheadend_picons/%25c.png", "prefer_picon":"False", "chiconscheme":"2"}')

    # if  os.path.isdir(conf['tvheadendChannelConfigDirectory']):
    #     logging.info( "Reset Icon dos canais do TVHeadend" )
    #     path = conf['tvheadendChannelConfigDirectory']
    #     files = []
    #     # r=root, d=directories, f = files
    #     for r, d, f in os.walk(path):
    #         for file in f:
    #             files.append(os.path.join(r, file))

    #     for f in files:
    #         with open(f, "r+") as jsonFile:
    #             data = json.load(jsonFile)
    #             if data['icon'] != "":
    #                 data['icon'] = ""
    #                 jsonFile.seek(0)  # rewind
    #                 json.dump(data, jsonFile, indent=4)
    #                 jsonFile.truncate()

    req = urllib2.Request("http://" + conf['tvheadendAuth'] +
                          conf['tvheadendAddress'] + ":" + conf['tvheadendPort'] + '/api/channel/list')
    fil = urllib2.urlopen(req)
    listURL = json.load(fil)
    fil.close()
    logging.info("'Reset Icon' dos canais do TVHeadend")
    for l in listURL['entries']:
        req1 = urllib2.Request("http://" + conf['tvheadendAuth'] + conf['tvheadendAddress'] + ":" +
                               conf['tvheadendPort'] + '/api/idnode/save?node={"uuid":"' + l['key'] + '","icon":""}')
        fil1 = urllib2.urlopen(req1)


def reconfigure_image_cache(conf):
    logging.info("Reconfigurando imagecache do TVHeadend")

    req = urllib2.Request("http://" + conf['tvheadendAddress'] +
                          ":" + conf['tvheadendPort'] + '/api/imagecache/config/load')
    fil = urllib2.urlopen(req)
    listURL = json.load(fil)
    fil.close()

    imagecache_enabled = False
    for l in listURL['entries'][0]['params']:
        if l['id'].lower() == "enabled":
            if l['value'] == True:
                imagecache_enabled = True

    if not imagecache_enabled:
        req = urllib2.Request("http://" + conf['tvheadendAddress'] + ":" +
                              conf['tvheadendPort'] + '/api/imagecache/config/save?node={"enabled":"true"}')
        fil = urllib2.urlopen(req)
        fil.close()
        time.sleep(1)

    req = urllib2.Request("http://" + conf['tvheadendAddress'] + ":" +
                          conf['tvheadendPort'] + '/api/imagecache/config/clean?clean=1')
    fil = urllib2.urlopen(req)
    fil.close()

    # executa automaticamente com o clean
    # req = urllib2.Request( "http://" + conf['tvheadendAddress'] + ":" + conf['tvheadendPort'] + '/api/imagecache/config/trigger?trigger=1' )
    # fil = urllib2.urlopen(req)
    # fil.close()


def iniciaDownloadPicons(conf):
    listMerged = []
    listFiles = lerLameDb(conf['lambedbFile'])

    if listFiles:
        channelList = lerBouquetGroup(conf)
        if channelList:
            listMerged = listFiles + channelList
            listMerged = remove_duplicates(listMerged)

    hasTvh = check_for_tvh(conf)

    if (hasTvh):
        tvhChannelList = getTvhChannelList(conf)
        listMerged = mergeLists(listMerged, tvhChannelList)

    downloadPicons(listMerged, conf)

    if (hasTvh):
        changeTvhConfig(conf)

        reconfigure_image_cache(conf)

        logging.info("Atencao, recomendado reiniciar o serviço do TVHeadend")

    logging.info("Pronto.")


def main():
    global CONFIG, DEV_CONFIG
    global DEBUG_MODE

    parser = argparse.ArgumentParser(
        description='Download de picons para o e2.')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--no-update', action='store_true',
                       help='não verifica por atualização')
    group.add_argument('--force-update', action='store_true',
                       help='força atualização')

    groupDebug = parser.add_mutually_exclusive_group()
    groupDebug.add_argument(
        '--debug', action='store_true', help='modo de testes')

    groupDev = parser.add_mutually_exclusive_group()
    groupDev.add_argument(
        '--dev', action='store_true', help='modo de testes')

    # groupTvhAuth = parser.add_mutually_exclusive_group()
    # groupTvhAuth.add_argument('--tvh-user', action='store_true', help = 'usuario admin do Tvheadend')
    # groupTvhAuth.add_argument('--tvh-password', action='store_true', help = 'senha do Tvheadend')
    parser.add_argument('--tvh-user', type=str,
                        help='usuario admin do Tvheadend')
    parser.add_argument('--tvh-password', type=str, help='senha do Tvheadend')

    parser.add_argument('--downloads-simultaneos', type=int, help='quantidade de downloads simultaneos, entre 1 e 20')

    args = parser.parse_args()

    # workaround tvheadend localhost
    CONFIG['tvheadendAddress'] = get_ip()
    # print CONFIG['tvheadendAddress']

    logging.basicConfig(format='%(asctime)s %(message)s', level=logging.DEBUG)
    logging.info("version " + __version__)

    ckUpdates = True
    if args.no_update or args.dev:
        ckUpdates = False

    if args.dev:
        print(args)
        CONFIG = DEV_CONFIG

    if args.debug:
        print("Debug mode ativo.")
        DEBUG_MODE = True

    if (args.tvh_user and not args.tvh_password) or (not args.tvh_user and args.tvh_password):
        print("Necessário --tvh-user e --tvh-password juntos")
        sys.exit()

    if args.tvh_user and args.tvh_password:
        # CONFIG['tvheadendAuth'] = args.tvh_user + ":" + args.tvh_password + "@"
        # print CONFIG['tvheadendAuth']
        print("Autenticação não implementado ainda, sorry.")
        sys.exit()

    if args.downloads_simultaneos:
        if args.downloads_simultaneos > 0 and args.downloads_simultaneos < 20:
            CONFIG['dl_simultaneos'] = args.downloads_simultaneos
 
    if args.force_update:
        update(CONFIG['updateurl'], True)
        logging.info("Pronto.")
        sys.exit()

    if ckUpdates:
        updateReturn = update(CONFIG['updateurl'])
        if updateReturn:
            logging.info("Reiniciando script")
            python = sys.executable
            os.execl(python, python, *sys.argv)

    iniciaDownloadPicons(CONFIG)


if __name__ == "__main__":
    main()
