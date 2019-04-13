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

__version__             = "0.2.2"
__checkupdate__         = True
__updateurl__           = "https://raw.githubusercontent.com/josemoraes99/enigma2_picons/master/picons.py"
__e2dir__               = "/etc/enigma2/"
__lambedbFile__         = __e2dir__ + 'lamedb5'
__urlPicons__           = "https://hk319yfwbl.execute-api.sa-east-1.amazonaws.com/prod"
__localPiconDirectory__ = "/usr/share/enigma2/picon/"
__bouquetGroup__        = ["bouquets.radio", "bouquets.tv"]
__ignoreChannels__      = ['SID 0x']

__progress__            = 0

reload(sys)
sys.setdefaultencoding('utf-8')

logging.basicConfig(format='%(asctime)s %(message)s', level=logging.DEBUG)

if len(sys.argv) > 1:
    for ar in sys.argv:
        if ar == 'debug':
            __checkupdate__ = False
            __e2dir__ = "etc/"
            __lambedbFile__ = __e2dir__ + 'lamedb5'
            __localPiconDirectory__="picon/"

def update(dl_url, force_update=False):
    """
Attempts to download the update url in order to find if an update is needed.
If an update is needed, the current script is backed up and the update is
saved in its place.
"""
    import urllib
    import re
    from subprocess import call
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
        update_file = http_stream.read(256)
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
                    lineSpl = line.split('#SERVICE ')[1]
                    srvc = ":".join(lineSpl.split(":", 10)[:10])
                    strSrvc = ":".join(srvc.split(":", 3)[:3])
                    if not strSrvc in excludeBouquets:
                        channels.append(srvc)
            return channels

def lerLameDb(f):
    logging.info( "Lendo arquivo " + f )
    if os.path.isfile(f):
        with io.open(f, encoding='utf-8', errors='ignore') as f:
            lDb = []
            for line in f:
                if line.startswith( "s:" ):
                    chName = line.split(",")[1].strip().strip('"')
                    if chName != '':
                        lDb.append(line.strip())
            return lDb
    else:
        logging.info( "Arquivo nao encontrado" )
        exit()

def gerarLista(c,l,ign):
    logging.info( "Processando lista" )
    chan =[]
    for item in c:
        for lis in l:
            lt = lis.split(",")[0].upper()
            if item.split(":")[3] == lt.split(":")[1].lstrip("0") and item.split(":")[5] == lt.split(":")[4].lstrip("0"):
                nomeCanal = lis.split(",")[1].lstrip('""').rstrip('""')
                for i in ign:
                    if i not in nomeCanal:
                        canalclean = re.sub(re.compile('\W'), '', ''.join(c.lower() for c in unicodedata.normalize('NFKD', lis.split(",")[1].replace("+", "mais")).encode('ascii', 'ignore') if not c.isspace()))
                        # canalFinal = 'canal' + canalclean + '.png'

                        filenameE2 = item.replace(":", "_").upper() + '.png'
                        chan.append([filenameE2,canalclean])

    return chan

def downloadFile(url,file):
    global __progress__
    # print(file + " " + url)
    imgdata = urllib2.urlopen(url).read()
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
        if file.strip() != "":
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
                while threading.active_count() > 5:
                    time.sleep(0.1)

    while __progress__ < numDownloads:
        if threading.active_count() == 1:
            break
        prog = float(__progress__) / float(numDownloads)
        update_progress(prog)
        time.sleep(0.3)

    update_progress(float(1))

    map(lambda t: t.join(), threads)


if __checkupdate__:
    updateReturn = update(__updateurl__)
    if updateReturn:
        logging.info( "Reiniciando script" )
        python = sys.executable
        os.execl(python, python, *sys.argv)

logging.info( "version " + __version__ )

channelList = lerBouquetGroup( __bouquetGroup__ )

lameDb = lerLameDb(__lambedbFile__)

listFiles = gerarLista(channelList,lameDb,__ignoreChannels__)

downloadPicons(listFiles)

logging.info( "Pronto." )

