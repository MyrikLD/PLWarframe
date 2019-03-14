#!/bin/python
import json
import logging
import os
from threading import Thread, Event

import gi

from config import (
    domain,
    index_url,
    index_local,
    def_conf,
    CURRDIR
)
from models import FileList, Line
from subproc import Proc, Subproc

gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gtk

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)


def filesize(size: int):
    power = 2 ** 10
    n = 0
    pn = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return f'{size:.2f} {pn[n]}B'


class Handler:
    status = 0
    thread = None
    _local_index = None
    ready = False
    log = logging.getLogger('HANDLER')

    def play_button(self, value: str, sensitive=True):
        self._play_button.set_label(value)
        self._play_button.set_sensitive(sensitive)

    def status_label(self, value: str):
        self._status_label.set_text(value)

    def bar1(self, value: int):
        self._bar1.set_fraction(value)

    def bar2(self, value: int):
        self._bar2.set_fraction(value)

    def __init__(self):
        self.window_is_hidden = False

        self._play_button = builder.get_object('PlayButton')
        self._status_label = builder.get_object('filePath')
        self._bar1 = builder.get_object('bar1')
        self._bar2 = builder.get_object('bar2')

        self.runner = Runner(self, self.local_index)

        self.conf = dict(def_conf)

        def create_conf():
            with open('config.json', 'w') as f:
                json.dump(self.conf, f, indent=True)

        try:
            with open('config.json', 'r') as f:
                file_conf = json.load(f)
                self.conf.update(file_conf)
        except (json.decoder.JSONDecodeError, FileNotFoundError):
            create_conf()

        self.cmd = Proc.gen(self.conf)

        self.process = None

    @property
    def local_index(self) -> FileList:
        if self._local_index:
            return self._local_index

        if os.path.exists(index_local):
            local_index = FileList.from_file(index_local)
        else:
            local_index = FileList()

        self._local_index = local_index

        return local_index

    def openSettings(self, button):
        settings_window = builder.get_object('SettingsWindow')
        settings_window.show_all()

        self.log.info(self.conf)
        conf = self.conf
        builder.get_object('dx10').set_active(conf['dx10'])
        builder.get_object('dx11').set_active(conf['dx10'])
        builder.get_object('threadedworker').set_active(conf['threadedworker'])

        builder.get_object('language').set_active_id(conf['language'])

        builder.get_object('wine_path').set_filename(conf['WINE_PATH'])
        builder.get_object('wine_exe').set_filename(conf['WINE_EXE'])
        builder.get_object('log').set_text(conf['log'])
        builder.get_object('cluster').set_text(conf['cluster'])

    def closeSettings(self, *args, **kwargs):
        settings_window = builder.get_object('SettingsWindow')
        settings_window.hide()
        return True

    def saveSettings(self, button):
        data = {
            'dx10': builder.get_object('dx10').get_active(),
            'dx11': builder.get_object('dx11').get_active(),
            'threadedworker': builder.get_object('threadedworker').get_active(),

            'language': builder.get_object('language').get_active_id(),

            'WINE_PATH': builder.get_object('wine_path').get_filename(),
            'WINE_EXE': builder.get_object('wine_exe').get_filename(),
            'log': builder.get_object('log').get_text(),
            'cluster': builder.get_object('cluster').get_text(),
        }

        self.log.info(f'Save conf: {data}')
        self.conf.update(data)
        with open('config.json', 'w') as f:
            json.dump(self.conf, f)

        self.cmd = Proc.gen(self.conf)

        settings_window = builder.get_object('SettingsWindow')
        settings_window.hide()

    def runClicked(self, button):
        if self.ready:
            self.status_label('Start game...')
            self.log.info(f'CMD: {self.cmd[2]}')
            self.process = Subproc(self.cmd[2], 'run')
            self.process.run()
            self.onQuit()
        elif self.thread and self.thread.is_alive():
            self.play_button('Download', False)

            self.runner.kill_event.set()
            self.thread.join()
            self.runner.kill_event.clear()

            self.bar1(0)
            self.bar2(0)
            self.status_label('Ready')

            self.play_button('Download', True)
        else:
            self.play_button('Stop', False)

            self.thread = Thread(target=self.runner.run)
            self.thread.daemon = True
            self.thread.start()

            self.play_button('Stop', True)

    def onQuit(self, *args):
        if self.process:
            self.process.kill()
        Gtk.main_quit()
        exit(0)


class Runner:
    local_index = ''
    stage = 0
    log = logging.getLogger('RUNNER')

    def __init__(self, parent, index):
        self.parent = parent

        self.kill_event = Event()

        self.local_index = index
        self.local_index.prefix = CURRDIR + '/Downloaded/Public'

        self.remote_index = FileList.from_url(index_url, self.kill_event)
        self.remote_index.prefix = domain

    def run(self):
        index = self.local_index
        validated_index = self.validate_index(index)
        validated_index.to_file(index_local)

        validated_index = index.exclude('/Cache.Windows/')

        download_index = self.make_download_index(validated_index)
        download_index = download_index.exclude('/Cache.Windows/')
        download_index.prefix = domain

        for i in sorted(download_index, key=lambda x: x.size):
            self.log.info(f'{i.path} {filesize(i.size)}')

        self.log.info(f'Download size: {filesize(download_index.size)}')

        if download_index.size:
            self.dowlnoad_index(download_index)

        Subproc.on_line = lambda s, text, ts, m, lvl: GLib.idle_add(self.parent.status_label, text)

        # Run update
        if self.kill_event.is_set():
            GLib.idle_add(self.parent.bar1, 0)
            GLib.idle_add(self.parent.bar2, 0)
            GLib.idle_add(self.parent.status_label, 'Ready')
            return

        GLib.idle_add(self.parent.play_button, 'Stop', False)

        GLib.idle_add(self.parent.status_label, 'Start internal updater...')
        self.log.info(f"CMD: {self.parent.cmd[0]}")
        self.parent.process = Subproc(self.parent.cmd[0], 'update', self.kill_event)
        self.parent.process.run()

        # Run cache
        if self.kill_event.is_set():
            GLib.idle_add(self.parent.bar1, 0)
            GLib.idle_add(self.parent.bar2, 0)
            GLib.idle_add(self.parent.status_label, 'Ready')
            return
        GLib.idle_add(self.parent.status_label, 'Start internal cache...')
        self.log.info(f"CMD: {self.parent.cmd[1]}")
        self.parent.process = Subproc(self.parent.cmd[1], 'cache', self.kill_event)
        self.parent.process.run()

        # End
        GLib.idle_add(self.parent.status_label, 'Updated')
        GLib.idle_add(self.parent.play_button, 'Run')
        self.parent.ready = True

    def validate_index(self, index):
        log = logging.getLogger('CHECK_INDEX')
        new_index = FileList(index)

        for i in index:
            GLib.idle_add(self.parent.status_label, 'Check: ' + i.path)
            log.info(i.path)
            if not i.check(self.kill_event):
                log.warning(f'Not valid md5: {i.path}')
                new_index.remove(i)

        return new_index

    def make_download_index(self, local_index):
        download_index = FileList()

        for file in self.remote_index:
            local_file = local_index.get(file.path)
            if not local_file or local_file.md5 != file.md5:
                download_index.add(file)

        return download_index

    def dowlnoad_index(self, download_index):
        log = logging.getLogger('DOWNLOAD')

        def cb(x, y):
            GLib.idle_add(self.parent.bar1, y / x)

        to_download = self.remote_index.exclude('/Cache.Windows/')
        GLib.idle_add(self.parent.bar2, 1 - download_index.size / to_download.size)

        for file in sorted(download_index, key=lambda x: x.size):
            local = Line(str(file))
            local.prefix = self.local_index.prefix

            if self.kill_event.is_set():
                return

            GLib.idle_add(self.parent.status_label, 'Download: ' + file.path)

            file_dir = os.path.dirname(local.full_path)
            if not os.path.exists(file_dir):
                os.makedirs(file_dir)

            try:
                data = file.download(self.kill_event, cb)
            except Exception as e:
                log.error(f'Download error: {e}')
                continue
            if data:
                with open(local.full_path, 'wb+') as f:
                    f.write(data)

            if file not in self.local_index:
                self.local_index.add(file)
                self.local_index.to_file(index_local)

            download_index.remove(file)
            GLib.idle_add(self.parent.bar2, 1 - download_index.size / to_download.size)

        log.info('Download ended')


builder = Gtk.Builder()
builder.add_from_file('gtk.glade')
builder.connect_signals(Handler())

builder.get_object('bar1').set_fraction(0)
builder.get_object('bar2').set_fraction(0)
builder.get_object('filePath').set_text('Ready')

window = builder.get_object('GtkWindow')
window.show_all()
window.set_title("Warframe Launcher")

PlayButton = builder.get_object('PlayButton')
PlayButton.set_sensitive(True)
PlayButton.set_label('Download')

Gtk.main()
