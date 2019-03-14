import os

CURRDIR = os.path.dirname(os.path.abspath(__file__))
domain = 'http://origin.warframe.com'
index_url = domain + '/index.txt.lzma'
index_local = 'local_index.test.txt'
local_path = 'Downloaded/Public'
def_conf = {
    'WINE_EXE': '/usr/bin/wine',
    'WINE_PATH': os.path.expanduser("~/.wine"),

    'log': '/Preprocessing.log',
    'dx10': 1,
    'dx11': 1,
    'threadedworker': 1,
    'cluster': 'public',
    'language': 'en',
}
