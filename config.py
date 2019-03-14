import os

CURRDIR = os.path.dirname(os.path.abspath(__file__))
domain = 'http://origin.warframe.com'
index_url = domain + '/index.txt.lzma'
index_local = 'local_index.test.txt'
local_path = './Downloaded/Public2'
def_conf = {
    'WIN_EXE': 'Downloaded/Public/Warframe.x64.exe',
    'WINE_EXE': '/home/myrik/.local/share/lutris/runners/wine/esync-staging-pba-3.18-x86_64/bin/wine',
    'WINE_PATH': os.path.expanduser("~/.wine"),

    'log': '/Preprocessing.log',
    'dx10': 1,
    'dx11': 1,
    'threadedworker': 1,
    'cluster': 'public',
    'language': 'en',
}
