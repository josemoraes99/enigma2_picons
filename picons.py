# -*- coding: utf-8 -*-

import sys
import logging
import os
import io
import re
import unicodedata
import json
import urllib2
import ast
import threading
import time
import uuid
import urllib
from functools import wraps

__version__             = "0.2.10"
__checkupdate__         = True
__updateurl__           = "https://raw.githubusercontent.com/josemoraes99/enigma2_picons/master/picons.py"
__e2dir__               = "/etc/enigma2/"
__lambedbFile__         = __e2dir__ + 'lamedb'
__urlPicons__           = "https://hk319yfwbl.execute-api.sa-east-1.amazonaws.com/prod"
__localPiconDirectory__ = "/usr/share/enigma2/picon/"
__bouquetGroup__        = ["bouquets.radio", "bouquets.tv"]
# __asModule__            = True
__progress__            = 0

reload(sys)
sys.setdefaultencoding('utf-8')

if len(sys.argv) > 1:
    for ar in sys.argv:
        if ar == 'debug':
            __checkupdate__ = False
            __e2dir__ = "etc/"
            __lambedbFile__ = __e2dir__ + 'lamedb'
            __localPiconDirectory__="picon/"

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
        if vA == vB: return 0

        def num(s):
            if s.isdigit(): return int(s)
            return s

        seqA = map(num, re.findall('\d+|\w+', vA.replace('-SNAPSHOT', '')))
        seqB = map(num, re.findall('\d+|\w+', vB.replace('-SNAPSHOT', '')))

        # this is to ensure that 1.0 == 1.0.0 in cmp(..)
        lenA, lenB = len(seqA), len(seqB)
        for i in range(lenA, lenB): seqA += (0,)
        for i in range(lenB, lenA): seqB += (0,)

        rc = cmp(seqA, seqB)

        if rc == 0:
            if vA.endswith('-SNAPSHOT'): return -1
            if vB.endswith('-SNAPSHOT'): return 1
        return rc

    # dl the first 256 bytes and parse it for version number
    try:
        http_stream = urllib.urlopen(dl_url)
        # update_file = http_stream.read(256)
        update_file = http_stream.read(300)
        http_stream.close()

    except IOError, (errno, strerror):
        logging.info( "Unable to retrieve version data" )
        logging.info( "Error %s: %s" % (errno, strerror) )
        return

    match_regex = re.search(r'__version__ *= *"(\S+)"', update_file)
    if not match_regex:
        logging.info( "No version info could be found" )
        return
    update_version = match_regex.group(1)

    if not update_version:
        logging.info( "Unable to parse version data" )
        return

    if force_update:
        logging.info( "Forcing update, downloading version %s..." % update_version )

    else:
        cmp_result = compare_versions(__version__, update_version)
        if cmp_result < 0:
            logging.info( "Newer version %s available, downloading..." % update_version )
        elif cmp_result > 0:
            logging.info( "Local version %s newer then available %s, not updating." % (__version__, update_version) )
            return
        else:
            logging.info( "You already have the latest version." )
            return

    # dl, backup, and save the updated script
    app_path = os.path.realpath(sys.argv[0])
    # if __asModule__ == True:
    #     app_path = __file__

    if not os.access(app_path, os.W_OK):
        logging.info( "Cannot update -- unable to write to %s" % app_path )

    dl_path = app_path + ".new"
    backup_path = app_path + ".old"
    try:
        dl_file = open(dl_path, 'w')
        http_stream = urllib.urlopen(dl_url)
        total_size = None
        bytes_so_far = 0
        chunk_size = 8192
        try:
            total_size = int(http_stream.info().getheader('Content-Length').strip())
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
        logging.info( "Download failed" )
        logging.info( "Error %s: %s" % (errno, strerror) )
        return

    try:
        os.rename(app_path, backup_path)
    except OSError, (errno, strerror):
        logging.info( "Unable to rename %s to %s: (%d) %s" % (app_path, backup_path, errno, strerror) )
        return

    try:
        os.rename(dl_path, app_path)
    except OSError, (errno, strerror):
        logging.info( "Unable to rename %s to %s: (%d) %s" % (dl_path, app_path, errno, strerror) )
        return

    try:
        import shutil
        shutil.copymode(backup_path, app_path)
    except:
        os.chmod(app_path, 0755)

    logging.info( "New version installed as %s" % app_path )
    logging.info( "(previous version backed up to %s)" % (backup_path) )
    return True

def convert_size(size_bytes):
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return "%s %s" % (s, size_name[i])

# update_progress() : Displays or updates a console progress bar
## Accepts a float between 0 and 1. Any int will be converted to a float.
## A value under 0 represents a 'halt'.
## A value at 1 or bigger represents 100%
def update_progress(progress):
    barLength = 50 # Modify this to change the length of the progress bar
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
        status = "Done...\r\n"
    block = int(round(barLength*progress))
    text = "\rPercent: [{0}] {1}% {2}".format( "="*block + " "*(barLength-block), int(progress*100), status)
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

@retry(urllib2.URLError, tries=4, delay=3, backoff=2)
def urlopen_with_retry(url):
    return urllib2.urlopen(url)

def downloadFile(url,file):
    global __progress__
    # print(file + " " + url)
    # imgdata = urllib2.urlopen(url).read()
    imgdata = urlopen_with_retry(url).read()
    # img = Image.open(cStringIO.StringIO(imgdata))
    with open(__localPiconDirectory__ + file, 'wb') as f:  
        f.write(imgdata)
    __progress__ += 1

def downloadPicons(f):
    logging.info( "Enviando lista dos picons" )
    global __progress__
    piconsList = []
    numDownloads = 0

    for file in f:
        # print(file)
        if file[1].strip() != "":
            piconsList.append(file[1])
            numDownloads += 1

    uuidOne = uuid.getnode()
    piconsList = list(dict.fromkeys(piconsList))
    data = {'src': 'e2','node': uuidOne,'listChannel': piconsList}
    data = json.dumps( data )
    # print(data)
    req = urllib2.Request(__urlPicons__, data, {'Content-Type': 'application/json'})
    fil = urllib2.urlopen(req)
    response = json.load(fil)
    fil.close()
    listURL = ast.literal_eval(response)  # procurar alternativa

    logging.info( "Download dos arquivos" )
    
    threads = []

    update_progress(float(0))

    for file in f:
        for l in listURL:
            if file[1] == l[0]:
                if numDownloads > 0:
                    prog = float(__progress__) / float(numDownloads)
                    update_progress(prog)
                t = threading.Thread(target=downloadFile, args=(l[1], file[0]))
                t.start()
                threads.append(t)
                while threading.active_count() > 10:
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
    logging.info( "Lendo arquivo " + f )
    if os.path.isfile(f):
        lDb = []
        finalList = []
        with io.open(f, encoding='utf-8', errors='ignore') as f:
            for line in f:
                lDb.append(line)

        for x in range(0, len(lDb)):
            # print x
            if lDb[x].startswith( "p:" ):
                nomeCanal = lDb[x - 1].strip()
                tmpId = lDb[x - 2].strip().split(":")
                oPosit = format( int( tmpId[4] ),'x' )
                if oPosit == "80":
                    oPosit = "1"

                idChannel = "1:0:" + oPosit + ":" + tmpId[0].lstrip("0") + ":" + tmpId[2].lstrip("0") + ":" + tmpId[3].lstrip("0") + ":" + tmpId[1] + ":0:0:0"

                canalclean = re.sub(re.compile('\W'), '', ''.join(c.lower() for c in unicodedata.normalize('NFKD', nomeCanal.replace("+", "mais")).encode('ascii', 'ignore') if not c.isspace()))

                filenameE2 = idChannel.replace(":", "_").upper() + '.png'
                if canalclean != "":
                    # print filenameE2 + " " + canalclean

                    finalList.append([filenameE2,canalclean])

        return finalList
    else:
        logging.info( "Arquivo nao encontrado" )
        exit()

def lerBouquetGroup(g):
    bResult = []
    for b in g:
        bResult = bResult + lerArquivoBouquet( b )

    listChan = []
    for f in bResult:
        listChan = listChan + lerArquivoUserBouquet( f )

    listChClean = []
    for l in listChan:
        if l not in listChClean:
            listChClean.append(l)

    # print listChClean
    return listChClean

def lerArquivoBouquet(f):
    fileR = __e2dir__ + f
    logging.info( "Lendo arquivo " + fileR )
    if os.path.isfile( fileR ):
        with io.open( fileR , encoding='utf-8', errors='ignore') as f:
            resp = []
            for line in f:
                if line.startswith( "#SERVICE" ):
                    resp.append( line.split('BOUQUET "')[1].split('" ')[0] )
            return resp

    else:
        logging.info( "Arquivo nao encontrado" )
        exit()

def lerArquivoUserBouquet(f):
    excludeBouquets=["1:0:CA","1:320:0"] # tres primeiros
    fileR = __e2dir__ + f
    channels = []
    logging.info( "Lendo arquivo " + fileR )
    if os.path.isfile( fileR ):
        with io.open( fileR , encoding='utf-8', errors='ignore') as f:
            resp = []
            for line in f:
                if line.startswith( "#SERVICE" ):
                    lineSpl = line.split('#SERVICE ')[1].strip()
                    if "::" in lineSpl:
                        tmpChannel = lineSpl.split("::")
                        canalclean = re.sub(re.compile('\W'), '', ''.join(c.lower() for c in unicodedata.normalize('NFKD', tmpChannel[1].replace("+", "mais")).encode('ascii', 'ignore') if not c.isspace()))

                        filenameE2 = tmpChannel[0].replace(":", "_").upper() + '.png'
                        # print filenameE2 + " " + canalclean
                        # print lineSpl
                        channels.append([filenameE2,canalclean])

                    # srvc = ":".join(lineSpl.split(":", 10)[:10])
                    # strSrvc = ":".join(srvc.split(":", 3)[:3])
                    # if not strSrvc in excludeBouquets:
                    #     channels.append(srvc)
            return channels

def remove_dup(a):
    finalList = []
    for item in a:
        # print item
        found = False
        for curItem in finalList:
            if item[0] == curItem[0] and item[1] == curItem[1]:
                # print item
                found = True

        if found == False:
            finalList.append(item)
    # print finalList
    return finalList

def iniciaDownloadPicons():
    if __checkupdate__:
        updateReturn = update(__updateurl__)
        if updateReturn:
            logging.info( "Reiniciando script" )
            python = sys.executable
            os.execl(python, python, *sys.argv)

    logging.info( "version " + __version__ )

    listFiles = lerLameDb(__lambedbFile__)

    channelList = lerBouquetGroup( __bouquetGroup__ )

    listMerged = listFiles + channelList

    listMerged = remove_dup(listMerged)

    downloadPicons(listMerged)

    logging.info( "Pronto." )

def main():
    # __asModule__ = False
    logging.basicConfig(format='%(asctime)s %(message)s', level=logging.DEBUG)
    iniciaDownloadPicons()

if __name__ == "__main__":
    main()
