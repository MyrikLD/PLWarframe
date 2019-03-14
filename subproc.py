import subprocess
import re
import logging
import os
import signal
from threading import Event


class Proc:
    # WORK
    start = False
    silent = True
    applet = ''

    # CONF
    WINE_PATH = ''
    WIN_EXE = ''
    WINE_EXE = ''

    log = ''
    dx10 = 1
    dx11 = 1
    threadedworker = 1
    cluster = ''
    language = ''

    def __init__(self, conf, start: bool, silent: bool, applet=''):
        self.start = start
        self.silent = silent
        self.applet = applet

        for k, v in conf.items():
            self.__setattr__(k, v)

    class Applets:
        update = '/EE/Types/Framework/ContentUpdate'
        cache = '/EE/Types/Framework/CacheDefraggerAsync'

    @property
    def cmd(self):
        cmd = f'env WINEPREFIX="{self.WINE_PATH}" {self.WINE_EXE} cmd /C'

        if self.start:
            cmd += ' start /b ""'

        cmd += f' "{self.WIN_EXE}" -log:{self.log} -dx10:{int(self.dx10)} -dx11:{int(self.dx11)} ' \
               f'-threadedworker:{int(self.threadedworker)} -cluster:{self.cluster} -language:{self.language}'
        if self.silent:
            cmd += ' -silent'
        if self.applet:
            cmd += f' -applet:{self.applet}'

        return cmd

    @classmethod
    def gen(cls, conf):
        cmd_update = cls(conf, silent=True, start=False, applet=Proc.Applets.update).cmd
        cmd_cache = cls(conf, silent=True, start=False, applet=Proc.Applets.cache).cmd
        cmd_run = cls(conf, silent=False, start=True).cmd
        return cmd_update, cmd_cache, cmd_run


class Subproc:
    proc = None
    lvls = {
        'Diag': 10,
        'Info': 20,
        'Warning': 30,
        'Error': 40,
    }

    def __init__(self, cmd, name='', kill_event=Event()):
        self.cmd = cmd
        self.name = name
        self.logs = {}
        self.kill_event = kill_event

    def on_line(self, text, timestamp, m, lvl):
        pass

    def run(self):
        self.proc = subprocess.Popen('exec ' + self.cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(self.proc.pid)
        for line in self.proc.stdout:
            text = line.decode(errors='ignore')
            data = re.findall(r'(\d+\.\d+) (\w+) \[(\w+)\]: (.*)', text)
            if data:
                ts, m, lvl, text = data[0]
                ts = float(ts)
                m = self.name.upper() + '_' + m.upper()
                lvl = self.lvls[lvl]

                if m not in self.logs:
                    self.logs[m] = logging.getLogger(m)
                self.logs[m].log(lvl, text)
                self.on_line(text, ts, m, lvl)

                if self.kill_event.is_set():
                    self.kill()
                    break

    def kill(self):
        if self.proc and self.proc.poll() is None:
            logging.info(f'kill: {self.proc.pid}')
            os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
            self.proc = None

    def __del__(self):
        self.kill()
